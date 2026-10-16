#!/usr/bin/env python3
"""
FHIR Medication Dosage Text Generator

This script converts FHIR medication dosage instructions into human-readable German text.

It is an EXAMPLE implementation of the dosage text generation algorithm. The normative
definition is the "Dosierung: Textgenerierung" page of the German FHIR medication dosage
implementation guide; this script illustrates it.
`__version__` therefore names the version of the algorithm being implemented, not of the
script itself.

The script supports various dosage schemas:
- FreeText: User-provided text instructions
- AsNeeded: Pure as-needed dosage (e.g., "bei Kopfschmerzen: je 1 Stück")
- 4-Schema: Morning-noon-evening-night pattern (e.g., "täglich: 1-0-2-0 Stück")
- TimeOfDay: Specific times (e.g., "täglich: 08:00 Uhr, 20:00 Uhr — je 1 Stück")
- DayOfWeek: Specific weekdays (e.g., "montags — je 1 Stück; mittwochs — je 2 Stück")
- Interval: Regular intervals (e.g., "alle 8 Stunden: je 1 Stück")
- Combined schemas: DayOfWeek + Time/4-Schema, Interval + Time/4-Schema

Algorithm Priority (TimingOnlyOneType constraint):
1. FreeText (has text, no timing, no doseAndRate)
2. AsNeeded (asNeededBoolean=true, no timing)
3. 4-Schema ('when' codes without a non-daily period)
4. DayOfWeek (has dayOfWeek, no concrete times)
5. DayOfWeek + Time/4-Schema (legacy frequency/period/periodUnit are ignored)
6. TimeOfDay
7. Interval + Time/4-Schema (non-daily period)
8. Interval (pure interval without when/timeOfDay/dayOfWeek)

Eine nicht klassifizierbare Merkmalskombination führt zum Abbruch; es wird kein
Ersatztext erzeugt.
"""

import json
import re
import sys
import os
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

__version__ = "2.0.0-rc.1"
__language__ = "de-DE"

class MedicationDosageTextGenerator:
    """
    Converts FHIR medication dosage instructions to German text.

    This class implements the reference algorithm for generating human-readable
    dosage instructions from FHIR resources according to the German FHIR
    medication dosage implementation guide.
    """

    # Schema type constants for clarity
    SCHEMA_FREE_TEXT = "FreeText"
    SCHEMA_4_PATTERN = "4-Schema"
    SCHEMA_TIME_OF_DAY = "TimeOfDay"
    SCHEMA_DAY_OF_WEEK = "DayOfWeek"
    SCHEMA_INTERVAL = "Interval"
    SCHEMA_DAY_TIME_COMBO = "DayOfWeek and Time/4-Schema"
    SCHEMA_INTERVAL_TIME_COMBO = "Interval and Time/4-Schema"
    SCHEMA_AS_NEEDED = "AsNeeded"

    # FHIR timing codes for 4-schema (morning, noon, evening, night)
    WHEN_CODES_ORDER = ['MORN', 'NOON', 'EVE', 'NIGHT']
    WHEN_CODE_TRANSLATIONS = {
        'MORN': 'morgens',
        'NOON': 'mittags',
        'EVE': 'abends',
        'NIGHT': 'zur Nacht'
    }

    # Day of week mapping
    DAY_ORDER = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
    DAY_TRANSLATIONS = {
        'mon': 'montags',
        'tue': 'dienstags',
        'wed': 'mittwochs',
        'thu': 'donnerstags',
        'fri': 'freitags',
        'sat': 'samstags',
        'sun': 'sonntags'
    }

    # Time unit translations (singular/plural)
    TIME_UNITS_SINGULAR = {
        's': 'Sekunde',
        'min': 'Minute',
        'h': 'Stunde',
        'd': 'Tag',
        'wk': 'Woche',
        'mo': 'Monat',
        'a': 'Jahr'
    }
    TIME_UNITS_PLURAL = {
        's': 'Sekunden',
        'min': 'Minuten',
        'h': 'Stunden',
        'd': 'Tage',
        'wk': 'Wochen',
        'mo': 'Monate',
        'a': 'Jahre'
    }

    # Kanonische Extension-URLs (exakter Vergleich, kein Teilstring-Match)
    URL_AS_NEEDED_FOR = 'http://hl7.org/fhir/5.0/StructureDefinition/extension-Dosage.asNeededFor'
    URL_MINDESTABSTAND = 'http://ig.fhir.de/igs/medication/StructureDefinition/MinimumIntervalBetweenAdministrations'

    # Verbindliche IANA-Zielzeitzone für die Darstellung von boundsPeriod.
    OUTPUT_TIMEZONE_NAME = "Europe/Berlin"
    OUTPUT_TIMEZONE = ZoneInfo(OUTPUT_TIMEZONE_NAME)

    def __init__(self):
        """Initialize the dosage text generator with German language settings."""
        pass

    def generate_dosage_text(self, resource):
        """
        Generate human-readable German dosage text from a FHIR resource.

        This is the main entry point that orchestrates the text generation process:
        1. Extract dosage instructions from the resource
        2. Determine which dosage schema applies
        3. Generate appropriate text for that schema

        Args:
            resource (dict): FHIR MedicationRequest, MedicationDispense, or MedicationStatement

        Returns:
            str: German dosage text (e.g., "täglich: 1-0-2-0 Stück" or "täglich: 08:00 Uhr — je 1 Stück")

        Examples:
            4-Schema: "täglich: 1-0-2-0 Stück"
            TimeOfDay: "täglich: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück"
            DayOfWeek: "montags — je 1 Stück; mittwochs — je 2 Stück"
            Interval: "alle 8 Stunden: je 1 Stück"
        """
        # Step 1: Extract dosage instructions based on resource type
        dosage_instructions = self._extract_dosage_instructions(resource)
        if not dosage_instructions:
            return ""

        # Jedes gelesene Feld muss den JSON-Datentyp seines FHIR-Typs haben.
        # Ein falscher Typ würde sonst stillschweigend den Text verfälschen:
        # period "1" (String) erkennt kein Tagesmuster, asNeededBoolean "true"
        # ist nicht True, frequency true zählt als 1.
        for dosage in dosage_instructions:
            self._check_field_types(dosage)

        # timeOfDay und when schließen sich bereits auf Ebene des FHIR-Basisdatentyps
        # Timing aus (tim-10). Ohne diese Prüfung würde je nach Schema stillschweigend
        # eine der beiden Angaben verworfen.
        for dosage in dosage_instructions:
            repeat = (dosage.get("timing") or {}).get("repeat") or {}
            if repeat.get("timeOfDay") and repeat.get("when"):
                raise ValueError(
                    "timeOfDay und when dürfen nicht gemeinsam angegeben werden (tim-10)."
                )

        self._check_as_needed_preconditions(dosage_instructions)

        # Eine reine Bedarfsdosierung (asNeededBoolean=true ohne timing) ist
        # nicht aggregierbar und muss das einzige Dosage-Element sein. Diese
        # defensive Prüfung spiegelt AsNeededSingleDosageOnly auch für Input,
        # der vor der Textgenerierung nicht gegen das Profil validiert wurde.
        if (
            any(
                self._is_as_needed(dosage) and not dosage.get("timing")
                for dosage in dosage_instructions
            )
            and len(dosage_instructions) != 1
        ):
            raise ValueError(
                "Reine Bedarfsmedikation erlaubt genau ein Dosage-Element."
            )

        # Step 2: Determine which dosage schema applies (implements TimingOnlyOneType logic)
        schema_type = self._determine_dosage_schema(dosage_instructions)

        # Die Erkennung stützt sich auf das erste Dosage-Element. Gehörte ein
        # späteres Element zu einem anderen Schema, würde es bei der Textbildung
        # übergangen — und mit ihm eine vollständige Gabe: Aus „morgens 1 Stück"
        # plus „montags 2 Stück" entstünde kommentarlos „täglich: 1-0-0-0 Stück". Die
        # Invarianten TimingOnlyOneType und TimingOnlyWhenOrTimeOfDay schließen
        # das aus; der Algorithmus verlässt sich darauf nicht, weil eine
        # unterschlagene Dosis der gefährlichste Ausgang wäre.
        for position, dosage in enumerate(dosage_instructions[1:], start=2):
            other_schema = self._determine_dosage_schema([dosage])
            if other_schema != schema_type:
                raise ValueError(
                    "Alle Dosage-Elemente müssen demselben Schema folgen; "
                    f"Element 1 ergibt '{schema_type}', Element {position} "
                    f"'{other_schema}'."
                )

        # Step 3: Generate text using the appropriate schema-specific method
        text_generators = {
            self.SCHEMA_FREE_TEXT: self._generate_freetext_schema_text,
            self.SCHEMA_4_PATTERN: self._generate_4_schema_text,
            self.SCHEMA_TIME_OF_DAY: self._generate_time_of_day_text,
            self.SCHEMA_DAY_OF_WEEK: self._generate_day_of_week_text,
            self.SCHEMA_INTERVAL: self._generate_interval_text,
            self.SCHEMA_DAY_TIME_COMBO: self._generate_dayofweek_and_time_schema_text,
            self.SCHEMA_INTERVAL_TIME_COMBO: self._generate_interval_and_time_schema_text,
            self.SCHEMA_AS_NEEDED: self._generate_as_needed_text,
        }

        # Eine nicht klassifizierbare Merkmalskombination ist nicht darstellbar. Ein
        # Ersatztext würde als generierte Dosieranweisung publiziert werden und dort
        # eine Aussage vortäuschen, die der Algorithmus gar nicht treffen kann.
        generator_method = text_generators.get(schema_type)
        if not generator_method:
            raise ValueError(
                "Die Dosierung entspricht keinem unterstützten Dosierungsschema."
            )

        result = generator_method(dosage_instructions)

        # FreeText wird unverändert übernommen; alle anderen Schemata werden
        # abschließend normalisiert (Leerzeichen).
        if schema_type != self.SCHEMA_FREE_TEXT:
            result = self._finalize_text(result)
        return result

    # ============================================================================
    # RESOURCE PROCESSING - Extract dosage data from FHIR resources
    # ============================================================================

    def _extract_dosage_instructions(self, resource):
        """
        Extract dosage instructions from different FHIR resource types.

        Different FHIR resources store dosage instructions in different fields:
        - MedicationRequest/MedicationDispense: dosageInstruction[]
        - MedicationStatement: dosage[]

        Args:
            resource (dict): FHIR resource

        Returns:
            list: List of dosage instruction objects

        Raises:
            ValueError: If resource type is not supported
        """
        resource_type = resource.get('resourceType', '')

        if resource_type in ['MedicationRequest', 'MedicationDispense']:
            field_name = 'dosageInstruction'
        elif resource_type == 'MedicationStatement':
            field_name = 'dosage'
        else:
            raise ValueError(f"Unsupported resource type: {resource_type}")
        return self._require_list(resource.get(field_name, []), field_name)

    # ============================================================================
    # TYPE CHECKS - JSON-Datentyp jedes gelesenen Feldes gegen seinen FHIR-Typ
    # ============================================================================

    def _require_object(self, value, field_name):
        if not isinstance(value, dict):
            raise ValueError(f"{field_name} muss ein Objekt sein.")
        return value

    def _require_list(self, value, field_name):
        if not isinstance(value, list):
            raise ValueError(f"{field_name} muss eine Liste sein.")
        return value

    def _require_string(self, value, field_name):
        if not isinstance(value, str):
            raise ValueError(f"{field_name} muss ein String sein.")
        return value

    def _require_decimal(self, value, field_name):
        """FHIR decimal ist im JSON eine Zahl. Ein String ("2") ist kein gültiges
        decimal und wird wie jeder andere falsche Typ abgewiesen; ihn
        stillschweigend zu konvertieren würde Werte annehmen, die eine validierte
        Ressource nicht enthalten kann. bool ist in Python ein int-Subtyp und
        wird deshalb ausdrücklich ausgeschlossen.

        Decimal ist zugelassen, weil nur ein mit parse_float=Decimal geparstes
        JSON die Genauigkeit erhält, die FHIR fuer decimal verlangt (2.50 ist
        nicht 2.5); ein float hat sie beim Einlesen bereits verloren."""
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError(f"{field_name} muss numerisch sein.")
        return value

    def _require_integer(self, value, field_name):
        """FHIR positiveInt/unsignedInt: im JSON eine ganze Zahl."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field_name} muss eine ganze Zahl sein.")
        return value

    def _check_field_types(self, dosage):
        """
        Prüft für ein Dosage-Element den JSON-Datentyp jedes Feldes, das der
        Algorithmus liest, gegen den FHIR-Datentyp. Geprüft wird nur der Typ,
        nicht der Wertebereich; der ist Sache der Profilvalidierung.

        Die Prüfung läuft vor der Schema-Erkennung, weil ein falscher Typ dort
        bereits in die Irre führt (period "1" ist nicht 1) und danach nicht mehr
        auffällt.
        """
        self._require_object(dosage, "Dosage")

        for name in ("text", "patientInstruction"):
            if name in dosage:
                self._require_string(dosage[name], name)
        if "asNeededBoolean" in dosage and not isinstance(dosage["asNeededBoolean"], bool):
            raise ValueError("asNeededBoolean muss ein boolescher Wert sein.")
        # Fremde Extensions werden nicht gelesen und deshalb auch nicht geprüft;
        # nur die url entscheidet, ob ein Eintrag den Algorithmus betrifft.
        for name in ("extension", "modifierExtension"):
            if name in dosage:
                for extension in self._require_list(dosage[name], name):
                    self._require_object(extension, f"{name}[]")
                    if "url" in extension:
                        self._require_string(extension["url"], f"{name}[].url")
                    url = extension.get("url")
                    if url == self.URL_AS_NEEDED_FOR and "valueCodeableConcept" in extension:
                        concept = self._require_object(
                            extension["valueCodeableConcept"], f"{name}[].valueCodeableConcept")
                        if "text" in concept:
                            self._require_string(concept["text"], f"{name}[].valueCodeableConcept.text")
                    if url == self.URL_MINDESTABSTAND and "valueDuration" in extension:
                        self._check_quantity_types(extension["valueDuration"], f"{name}[].valueDuration")
                    # Eine modifierExtension veraendert die Bedeutung des Elements
                    # (FHIR); eine unbekannte darf nicht stillschweigend entfallen.
                    if name == "modifierExtension" and url != self.URL_MINDESTABSTAND:
                        raise ValueError(f"Nicht unterstützte modifierExtension: '{url}'.")
        if "doseAndRate" in dosage:
            # Gelesen wird nur doseAndRate[0]; weitere Einträge werden ignoriert.
            items = self._require_list(dosage["doseAndRate"], "doseAndRate")
            if items:
                item = self._require_object(items[0], "doseAndRate[]")
                if "doseQuantity" in item:
                    self._check_quantity_types(item["doseQuantity"], "doseQuantity")
                if "doseRange" in item:
                    dose_range = self._require_object(item["doseRange"], "doseRange")
                    for bound in ("low", "high"):
                        if bound in dose_range:
                            self._check_quantity_types(dose_range[bound], f"doseRange.{bound}")
        if "maxDosePerPeriod" in dosage:
            max_dose = self._require_object(dosage["maxDosePerPeriod"], "maxDosePerPeriod")
            for part in ("numerator", "denominator"):
                if part in max_dose:
                    self._check_quantity_types(max_dose[part], f"maxDosePerPeriod.{part}")

        if "timing" not in dosage:
            return
        timing = self._require_object(dosage["timing"], "timing")
        if "repeat" not in timing:
            return
        repeat = self._require_object(timing["repeat"], "timing.repeat")
        if "boundsDuration" in repeat:
            self._check_quantity_types(repeat["boundsDuration"], "timing.repeat.boundsDuration")
        if "boundsPeriod" in repeat:
            bounds_period = self._require_object(repeat["boundsPeriod"], "timing.repeat.boundsPeriod")
            for name in ("start", "end"):
                if name in bounds_period:
                    self._require_string(bounds_period[name], f"timing.repeat.boundsPeriod.{name}")
        for name in ("frequency", "frequencyMax"):
            if name in repeat:
                self._require_integer(repeat[name], f"timing.repeat.{name}")
        for name in ("period", "periodMax"):
            if name in repeat:
                self._require_decimal(repeat[name], f"timing.repeat.{name}")
        if "periodUnit" in repeat:
            self._require_string(repeat["periodUnit"], "timing.repeat.periodUnit")
        for name in ("dayOfWeek", "when", "timeOfDay"):
            if name in repeat:
                for entry in self._require_list(repeat[name], f"timing.repeat.{name}"):
                    self._require_string(entry, f"timing.repeat.{name}[]")

    def _check_quantity_types(self, quantity, path):
        """Quantity/Duration: value decimal, unit und code string."""
        quantity = self._require_object(quantity, path)
        if "value" in quantity:
            self._require_decimal(quantity["value"], f"{path}.value")
        for name in ("unit", "code"):
            if name in quantity:
                self._require_string(quantity[name], f"{path}.{name}")
        # Fuer einen comparator ("<", ">=", ...) ist keine Darstellung
        # definiert; Bereiche und Obergrenzen traegt die Ressource als
        # doseRange bzw. maxDosePerPeriod.
        if "comparator" in quantity:
            raise ValueError(f"{path}.comparator wird nicht unterstützt.")
        return quantity

    def _check_as_needed_preconditions(self, dosage_instructions):
        """
        Einnahmeanlass, Mindestabstand und Maximalmenge setzen das
        Bedarfskennzeichen voraus; Mindestabstand und Maximalmenge zusaetzlich
        eine reine Bedarfsdosierung ohne timing. Sie stillschweigend zu
        uebergehen waere eine Auslassung - eine modifierExtension darf nie
        ignoriert werden, und alle drei sind Angaben der Ressource. Neben einem
        strukturierten Rhythmus waeren sie zudem widerspruechlich: Der Rhythmus
        legt Abstand und Menge im Bezugszeitraum bereits fest.

        Die Pruefung laeuft ueber *alle* Dosage-Elemente, obwohl der Text die
        Angaben nur aus dem ersten liest: Ein Verstoss in einem spaeteren
        Element darf nicht von der Reihenfolge abhaengen.
        """
        for dosage in dosage_instructions:
            as_needed = self._is_as_needed(dosage)
            has_timing = bool(dosage.get('timing'))
            # Freitext wird unveraendert uebernommen (FreeTextMatchesRenderedText
            # verlangt exakte Gleichheit); Mindestabstand und Maximalmenge daneben
            # koennten nie im Text erscheinen.
            is_free_text = bool(dosage.get('text')) and not has_timing and not dosage.get('doseAndRate')
            if self._extract_as_needed_for_text(dosage) and not as_needed:
                raise ValueError(
                    "Ein Einnahmeanlass (asNeededFor) setzt asNeededBoolean = true voraus.")
            if self._extract_minimum_interval_text(dosage):
                if not as_needed:
                    raise ValueError("Ein Mindestabstand setzt asNeededBoolean = true voraus.")
                if has_timing:
                    raise ValueError(
                        "Ein Mindestabstand ist nur bei reiner Bedarfsmedikation "
                        "zulässig, nicht zusammen mit einem strukturierten Rhythmus."
                    )
                if is_free_text:
                    raise ValueError(
                        "Ein Mindestabstand ist bei einer Freitext-Dosierung nicht darstellbar.")
            if self._extract_max_dose_text(dosage):
                if not as_needed:
                    raise ValueError("Eine Maximalmenge setzt asNeededBoolean = true voraus.")
                if has_timing:
                    raise ValueError(
                        "Eine Maximalmenge ist nur bei reiner Bedarfsmedikation "
                        "zulässig, nicht zusammen mit einem strukturierten Rhythmus."
                    )
                if is_free_text:
                    raise ValueError(
                        "Eine Maximalmenge ist bei einer Freitext-Dosierung nicht darstellbar.")

    def _require_day_code(self, day_code):
        """Die Wochentags-Tabelle ist abschließend. Ein Code außerhalb würde
        sonst roh im Text erscheinen ("xyz — je 1 Stück")."""
        if day_code not in self.DAY_TRANSLATIONS:
            raise ValueError(f"Nicht unterstützter Wochentag (dayOfWeek): '{day_code}'.")
        return day_code

    # ============================================================================
    # SCHEMA DETECTION - Determine which dosage pattern applies
    # ============================================================================

    def _determine_dosage_schema(self, dosage_instructions):
        """
        Determine the dosage schema type based on TimingOnlyOneType constraint logic.

        This method implements the priority order defined in the constraint:
        1. FreeText: Text without timing and without doseAndRate
        2. AsNeeded: asNeededBoolean=true without timing
        3. 4-Schema: 'when' codes without a non-daily period
        4. DayOfWeek: weekdays without concrete times
        5. DayOfWeek + Time/4-Schema: weekdays plus timeOfDay OR when
        6. TimeOfDay: specific times
        7. Interval + Time/4-Schema: non-daily period
        8. Interval: pure interval pattern without timing details

        Args:
            dosage_instructions (list): List of dosage instruction objects

        Returns:
            str: Schema type constant (e.g., SCHEMA_4_PATTERN, SCHEMA_TIME_OF_DAY)
        """

        # Analyze the first dosage instruction (constraint ensures consistency)
        first_dosage = dosage_instructions[0]

        # Schema 1: FreeText - Text ohne jede strukturierte Dosierungsangabe.
        # doseAndRate wird mitgeprüft: andernfalls würde bei widersprüchlichen Angaben
        # der Freitext gewinnen und die strukturierte Dosis kommentarlos entfallen.
        if (first_dosage.get('text')
                and not first_dosage.get('timing')
                and not first_dosage.get('doseAndRate')):
            return self.SCHEMA_FREE_TEXT

        # Extract timing information for further analysis
        timing = first_dosage.get('timing', {})
        repeat_element = timing.get('repeat', {})

        # Check what timing elements are present
        has_frequency = 'frequency' in repeat_element
        has_period = 'period' in repeat_element
        has_period_unit = 'periodUnit' in repeat_element
        has_day_of_week = 'dayOfWeek' in repeat_element and repeat_element['dayOfWeek']
        has_when_codes = 'when' in repeat_element and repeat_element['when']
        has_time_of_day = 'timeOfDay' in repeat_element and repeat_element['timeOfDay']
        # Reine Bedarfsdosierung: Bedarfskennzeichen (asNeededBoolean=true) ohne timing.
        # Ist zusätzlich ein timing vorhanden, kennzeichnet der Bedarf nur ein
        # strukturiertes Schema und wird dort als Präfix "bei {Anlass}:" dargestellt
        # (siehe _assemble).
        if self._is_as_needed(first_dosage) and not first_dosage.get('timing'):
            return self.SCHEMA_AS_NEEDED

        has_period_max = 'periodMax' in repeat_element
        # Helper: Check if this is a daily pattern (period=1, periodUnit='d')
        is_daily_pattern = (repeat_element.get('period') == 1 and
                            repeat_element.get('periodUnit') == 'd' and
                            not has_period_max)
        is_non_daily_pattern = (has_period and has_period_unit and not is_daily_pattern)
        is_pure_interval = (has_frequency and has_period and has_period_unit and
                            not has_when_codes and not has_time_of_day and not has_day_of_week)
        def has_valid_legacy_fields(period_unit):
            """Geduldete Legacy-Angaben fuer ein Schema mit impliziter Wiederholung.

            frequency wird hier nicht geprueft: Es beeinflusst die Erkennung nicht
            und wird nie ausgegeben. Eine variable Frequenz oder Periode ist dagegen
            ausgeschlossen - die konkreten Zeitpunkte legen die Zahl der Gaben
            bereits fest, eine Spanne daneben liesse sich nur unterschlagen.
            """
            return (
                'frequencyMax' not in repeat_element and
                'periodMax' not in repeat_element and
                (
                    (not has_period and not has_period_unit) or
                    (repeat_element.get('period') == 1 and
                     repeat_element.get('periodUnit') == period_unit)
                )
            )

        has_valid_weekday_legacy_fields = has_valid_legacy_fields('wk')
        has_valid_daily_legacy_fields = has_valid_legacy_fields('d')

        # Schema 3: 4-Schema. Konkrete Tagesabschnitte legen die Zahl der Gaben
        # bereits fest. frequency sowie das tägliche period/periodUnit-Paar sind
        # optional und ändern die Textausgabe nicht.
        if (has_when_codes and not has_time_of_day and not has_day_of_week and
                has_valid_daily_legacy_fields):
            return self.SCHEMA_4_PATTERN

        # Schema 4: DayOfWeek. frequency/period/periodUnit may be present as
        # redundant legacy metadata and do not turn this into an interval schema.
        if (has_day_of_week and not has_when_codes and not has_time_of_day and
                has_valid_weekday_legacy_fields):
            return self.SCHEMA_DAY_OF_WEEK

        # Schema 5: DayOfWeek + Time/4-Schema. The same legacy metadata is
        # deliberately ignored for schema selection and text generation.
        if (has_day_of_week and (has_time_of_day or has_when_codes) and
                has_valid_weekday_legacy_fields):
            return self.SCHEMA_DAY_TIME_COMBO

        # Schema 6: TimeOfDay. frequency sowie das tägliche
        # period/periodUnit-Paar sind optional und ändern die Textausgabe nicht.
        if (has_time_of_day and not has_day_of_week and not has_when_codes and
                has_valid_daily_legacy_fields):
            return self.SCHEMA_TIME_OF_DAY

        # Schema 7: Äußeres, nicht tägliches Intervall mit konkreten Zeitpunkten.
        # frequency ist hier redundant, aber optional zulässig; frequencyMax
        # nicht - die Zeitpunkte legen die Zahl der Gaben fest, eine Spanne
        # daneben wuerde unterschlagen.
        if (is_non_daily_pattern and (has_time_of_day or has_when_codes) and
                not has_day_of_week and 'frequencyMax' not in repeat_element and
                repeat_element.get('periodUnit') in ('d', 'wk', 'mo')):
            return self.SCHEMA_INTERVAL_TIME_COMBO

        # Schema 8: Interval - pure interval without timing details
        if is_pure_interval:
            return self.SCHEMA_INTERVAL

        return "Unknown"

    # ============================================================================
    # TEXT GENERATION - Schema-specific text generators
    # ============================================================================

    def _generate_4_schema_text(self, dosage_instructions):
        """
        Generate text for 4-Schema: morning-noon-evening-night pattern.

        The 4-Schema represents doses at four daily time points using a compact
        notation: "morning-noon-evening-night" (e.g., "täglich: 1-0-2-0 Stück").

        Args:
            dosage_instructions (list): List containing dosage instructions with 'when' codes

        Returns:
            str: Formatted text like "täglich: 1-0-2-0 Stück" or "für 7 Tage täglich: 2-1-2-1 mg"

        Example FHIR input:
            - Dosage with when=['MORN'], doseQuantity={value: 1, unit: 'Stück'}
            - Dosage with when=['EVE'], doseQuantity={value: 2, unit: 'Stück'}

        Example output: "täglich: 1-0-2-0 Stück"
        """
        # Je Position (Wert, Einheit); None = nicht belegt. Eine explizit mit 0
        # belegte Position muss davon unterscheidbar bleiben, damit sie in der
        # ausgeschriebenen Form nicht entfaellt (siehe _render_when_doses).
        dose_amounts = {code: None for code in self.WHEN_CODES_ORDER}

        # Process each dosage instruction to extract dose amounts
        for dosage in dosage_instructions:
            timing = dosage.get('timing', {})
            repeat_element = timing.get('repeat', {})
            when_codes = repeat_element.get('when', [])

            # Extract dose quantity information
            dose_value, dose_unit = self._extract_dose_quantity(dosage)

            # Assign dose value to each specified time period
            for when_code in when_codes:
                if when_code not in dose_amounts:
                    raise ValueError(
                        f"Nicht unterstützter Tagesabschnitt (when): '{when_code}'.")
                # Dieselbe Dosis zweimal ergibt denselben Text; nur eine
                # abweichende Dosis ist nicht darstellbar (wie in den anderen
                # Schemata).
                existing = dose_amounts[when_code]
                if existing is None:
                    dose_amounts[when_code] = (dose_value, dose_unit)
                elif self._slot_key(existing) != self._slot_key((dose_value, dose_unit)):
                    raise ValueError(
                        f"Doppelte Belegung des Tagesabschnitts '{when_code}' "
                        "mit unterschiedlicher Dosis.")

        # Feste Dosen mit gemeinsamer Einheit -> kompakt "1-0-2-0"; ein variabler
        # Wert oder abweichende Einheiten -> ausgeschriebene Segmentform
        # (siehe _render_when_doses).
        dose_pattern = self._render_when_doses(dose_amounts)
        # Marker "täglich" wie beim Uhrzeiten-Schema: Das nackte Muster
        # "1-0-2-0" lässt offen, dass es jeden Tag gilt.
        text = self._assemble(dosage_instructions[0], "täglich", dose_pattern)
        return self._append_trailing_instructions(text, dosage_instructions[0])

    def _needs_written_form(self, dose_amounts):
        """Ausgeschriebene Form noetig: ein variabler Wert (Bereich) oder nicht
        alle belegten Positionen mit derselben Einheit. Das kompakte Muster
        traegt nur eine Einheit; eine zweite fiele weg."""
        assigned = [slot for slot in dose_amounts.values() if slot is not None]
        return (any(isinstance(value, str) for value, _ in assigned)
                or len({unit for _, unit in assigned}) > 1)

    def _render_when_doses(self, dose_amounts, force_written=False):
        """
        Render eine MORN/NOON/EVE/NIGHT-Dosisbelegung; je Position (Wert, Einheit)
        oder None fuer nicht belegt.

        Feste Dosen mit gemeinsamer Einheit ergeben die kompakte, positionelle
        Notation "1-0-2-0 [Einheit]"; nicht belegte Positionen erscheinen als 0.
        Ist eine Position variabel (Bereich, z. B. "1 bis 2") oder tragen die
        Positionen verschiedene Einheiten, wird die ausgeschriebene Segmentform
        verwendet: nur belegte Positionen, jede mit ihrer eigenen Einheit, z. B.
        "morgens — je 1 bis 2 Stück, abends — je 2 Messlöffel". Der Algorithmus
        beurteilt nicht, ob die Einheiten zusammenpassen; er gibt sie wieder.
        Eine explizit mit 0 belegte Position ist belegt und bleibt erhalten.

        `force_written` erzwingt die ausgeschriebene Form auch für eine für sich
        genommen kompakt darstellbare Belegung. Die Wochentags-Kombination nutzt
        das, damit die Notation über alle Tage hinweg einheitlich bleibt.
        """
        if not (force_written or self._needs_written_form(dose_amounts)):
            units = {slot[1] for slot in dose_amounts.values() if slot is not None}
            unit_text = units.pop() if units else ""
            pattern = "-".join(
                "0" if dose_amounts[code] is None
                else self._format_decimal_value(dose_amounts[code][0])
                for code in self.WHEN_CODES_ORDER)
            return f"{pattern} {unit_text}"

        segments = []
        for code in self.WHEN_CODES_ORDER:
            slot = dose_amounts[code]
            # Unbelegte Positionen entfallen in der ausgeschriebenen Form.
            if slot is None:
                continue
            value, unit = slot
            formatted = value if isinstance(value, str) else self._format_decimal_value(value)
            segments.append(f"{self.WHEN_CODE_TRANSLATIONS[code]} — je {formatted} {unit}")
        # Tagesabschnitts-Segmente werden mit Komma getrennt (siehe Trennzeichen).
        return ", ".join(segments)

    def _generate_freetext_schema_text(self, dosage_instructions):
        """
        Generate text for FreeText schema: return user-provided text directly.

        For free text dosages, we simply extract and concatenate the text fields
        from all dosage instructions, preserving the original human-readable content.

        Args:
            dosage_instructions (list): List of dosage instructions with text fields

        Returns:
            str: Concatenated text from all dosage instructions

        Example:
            Input: [{"text": "Nach Bedarf"}, {"text": "bei Schmerzen"}]
            Output: "Nach Bedarf bei Schmerzen"
        """

        # Freitext unverändert, auch Rand-Leerraum: FreeTextMatchesRenderedText
        # verlangt exakte Gleichheit mit Dosage.text; ein Trim machte sie fuer
        # solche Texte unmoeglich.
        # Jedes Element traegt einen nicht leeren Text: Die Schema-Erkennung
        # verlangt ihn, und die Schema-Gleichheit gilt fuer alle Elemente.
        return " ".join(dosage['text'] for dosage in dosage_instructions)

    def _generate_time_of_day_text(self, dosage_instructions):
        """
        Generate text for TimeOfDay schema: specific times with doses.

        Creates text showing specific clock times with corresponding doses,
        formatted as German time expressions with "Uhr".

        Args:
            dosage_instructions (list): List with timeOfDay specifications

        Returns:
            str: Formatted text like "täglich: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück"

        Example FHIR input:
            - timing.repeat.timeOfDay = ["08:00", "20:00"]
            - doseQuantity = {value: 1, unit: "Stück"}

        Example output: "täglich: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück"
        """

        combined_instructions = self._build_time_dose_segments(dosage_instructions)

        text = self._assemble(dosage_instructions[0], "täglich", combined_instructions)
        return self._append_trailing_instructions(text, dosage_instructions[0])

    # ============================================================================
    # UTILITY METHODS - Reusable functions for data extraction and formatting
    # ============================================================================

    def _build_time_dose_segments(self, dosages):
        """
        Build the comma-separated time segments shared by the TimeOfDay schemas.

        Sammelt alle Uhrzeit-Dosis-Paare über *alle* übergebenen Dosage-Elemente
        hinweg und sortiert sie global aufsteigend anhand des unveränderten
        timeOfDay-Eingabestrings. Die Reihenfolge der Dosage-Elemente in der
        Ressource beeinflusst die Ausgabe damit nicht.

        Unmittelbar benachbarte Uhrzeiten mit identischer Dosis werden
        anschließend wieder zu einer Zeitgruppe vor einem gemeinsamen
        Gedankenstrich zusammengefasst, damit die kompakte Schreibweise
        "08:00 Uhr, 20:00 Uhr — je 1 Stück" erhalten bleibt. Trennt eine
        abweichende Dosis zwei Uhrzeiten desselben Dosage-Elements, zerfällt
        die Gruppe zugunsten der aufsteigenden Sortierung.

        Args:
            dosages (list): Dosage-Elemente mit timeOfDay-Angaben

        Returns:
            str: z. B. "01:00 Uhr — je 1 Stück, 18:00 Uhr — je 3 Stück,
                 23:00 Uhr — je 1 Stück" oder "" wenn keine Uhrzeit vorliegt
        """
        time_dose_pairs = []

        for dosage in dosages:
            repeat_element = dosage.get('timing', {}).get('repeat', {})
            time_of_day_list = repeat_element.get('timeOfDay', [])
            dose_text = self._extract_dose_text_with_prefix(dosage)
            for time_value in time_of_day_list:
                # Sortierschlüssel ist der unveränderte Eingabestring: Sekunden und
                # Sekundenbruchteile bleiben so sortierwirksam, auch wenn sie in der
                # Ausgabe (HH:MM Uhr) entfallen. Da timeOfDay nullaufgefüllt sein
                # muss, entspricht die lexikographische der chronologischen Ordnung.
                time_dose_pairs.append(
                    (time_value, self._format_time_german(time_value), dose_text))

        time_dose_pairs.sort(key=lambda pair: pair[0])

        # Dieselbe Uhrzeit (HH:MM) mit abweichender Dosis ist mehrdeutig und
        # fuehrt zum Abbruch - ueber alle Dosage-Elemente hinweg, wie bei der
        # Intervall-Kombination. Dieselbe Uhrzeit mit derselben Dosis ergibt
        # denselben Text und wird nur einmal ausgegeben.
        dose_by_time = {}
        unique_pairs = []
        for raw_time, formatted_time, dose_text in time_dose_pairs:
            known = dose_by_time.get(formatted_time)
            if known is None:
                dose_by_time[formatted_time] = dose_text
                unique_pairs.append((raw_time, formatted_time, dose_text))
            elif known != dose_text:
                raise ValueError(
                    f"Doppelte Belegung der Uhrzeit '{formatted_time}' mit unterschiedlicher Dosis.")
        time_dose_pairs = unique_pairs

        segments = []
        for _, formatted_time, dose_text in time_dose_pairs:
            if segments and segments[-1][1] == dose_text:
                segments[-1][0].append(formatted_time)
            else:
                segments.append(([formatted_time], dose_text))

        return ", ".join(
            f"{', '.join(times)} — {dose_text}" for times, dose_text in segments)

    def _extract_dose_quantity(self, dosage):
        """
        Extract dose quantity and unit from a dosage instruction.

        Args:
            dosage (dict): Single dosage instruction

        Returns:
            tuple: (dose_value, unit)

        Raises:
            ValueError: Wenn keine auswertbare Dosis vorhanden ist. Profilkonformer
                Input enthält immer eine: DosageStructuredRequiresBoth erzwingt
                "timing implies doseAndRate", und für die reine Bedarfsdosierung
                verlangt DosageStructuredOrFreeText ebenfalls doseAndRate.

        Example:
            Input: {"doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stück"}}]}
            Output: (2, "Stück")
        """
        dose_and_rate = dosage.get('doseAndRate', [])
        if not dose_and_rate:
            raise ValueError("doseAndRate ist für die Textgenerierung erforderlich.")

        first_dose = dose_and_rate[0]

        # Typen (Objekt, Zahl, String) hat Schritt 3 bereits geprueft; hier geht
        # es nur noch um Vorhandensein. Eine Einheit aus Leerraum ist keine.
        if 'doseQuantity' in first_dose:
            dose_quantity = first_dose['doseQuantity']
            dose_value = dose_quantity.get('value')
            unit = dose_quantity.get('unit')
            if dose_value is None:
                raise ValueError("doseQuantity.value ist für die Textgenerierung erforderlich.")
            if not unit or not unit.strip():
                raise ValueError("doseQuantity.unit ist für die Textgenerierung erforderlich.")
            # "je 0 Stück" ist ein eindeutiger Text; eine negative Dosis ist
            # keine Anweisung und wird nicht dargestellt.
            if dose_value < 0:
                raise ValueError("doseQuantity.value darf nicht negativ sein.")
            return (dose_value, unit)

        if 'doseRange' in first_dose:
            dose_range = first_dose['doseRange']
            low = dose_range.get('low')
            high = dose_range.get('high')

            if high is None or high.get('value') is None:
                raise ValueError("doseRange.high.value ist für die Textgenerierung erforderlich.")
            if not high.get('unit') or not high['unit'].strip():
                raise ValueError("doseRange.high.unit ist für die Textgenerierung erforderlich.")
            if high['value'] < 0:
                raise ValueError("doseRange.high.value darf nicht negativ sein.")

            if low is not None:
                if low.get('value') is None:
                    raise ValueError("doseRange.low.value ist für die Textgenerierung erforderlich.")
                if low['value'] < 0:
                    raise ValueError("doseRange.low.value darf nicht negativ sein.")
                # Die Einheit erscheint nur einmal im Text und stammt aus high.
                # low.unit wird deshalb nicht verlangt; ist sie vorhanden und
                # weicht ab, würde der Text sie unterschlagen - dann Abbruch.
                if low.get('unit') and low.get('unit') != high.get('unit'):
                    raise ValueError("doseRange.low.unit und doseRange.high.unit müssen übereinstimmen.")
                value = (
                    f"{self._format_decimal_value(low.get('value'))} bis "
                    f"{self._format_decimal_value(high.get('value'))}"
                )
            else:
                value = f"bis zu {self._format_decimal_value(high.get('value'))}"
            return (value, high.get('unit'))

        raise ValueError("Dosisangabe in doseAndRate[0] fehlt.")

    def _dose_key(self, dose_value):
        """Vergleichsschluessel fuer "dieselbe Dosis": die Textdarstellung.

        Numerische Gleichheit (Decimal('1.0') == 1) reichte nicht: Beide Werte
        ergeben verschiedene Texte ("1,0" und "1"), und welcher gewinnt, hinge
        von der Reihenfolge der Dosage-Elemente ab.
        """
        return dose_value if isinstance(dose_value, str) else self._format_decimal_value(dose_value)

    def _slot_key(self, slot):
        """Vergleichsschluessel fuer eine Belegung (Wert, Einheit): dieselbe Dosis
        heisst derselbe Text, also gleicher Wert UND gleiche Einheit."""
        value, unit = slot
        return (self._dose_key(value), unit)

    def _extract_dose_text_with_prefix(self, dosage):
        """
        Extract dose as German text with 'je' prefix.

        Args:
            dosage (dict): Single dosage instruction

        Returns:
            str: Formatted dose like "je 1 Stück"
        """
        dose_value, unit = self._extract_dose_quantity(dosage)
        formatted_dose = dose_value if isinstance(dose_value, str) else self._format_decimal_value(dose_value)
        # Die Einheit ist Pflicht (_extract_dose_quantity bricht sonst ab).
        return f"je {formatted_dose} {unit}"

    def _extract_bounds_text(self, dosage):
        """
        Extract duration or period bounds as German text.

        Args:
            dosage (dict): Single dosage instruction

        Returns:
            str: Formatted bounds like "für 7 Tage" or "" if no bounds
        """
        timing = dosage.get('timing', {})
        repeat_element = timing.get('repeat', {})
        bounds_duration = repeat_element.get('boundsDuration')
        bounds_period = repeat_element.get('boundsPeriod')

        has_bounds_duration = 'boundsDuration' in repeat_element
        has_bounds_period = 'boundsPeriod' in repeat_element
        if has_bounds_duration and has_bounds_period:
            raise ValueError(
                "boundsPeriod und boundsDuration dürfen nicht gleichzeitig vorhanden sein."
            )

        if has_bounds_period:
            return self._format_bounds_period(bounds_period or {})

        if has_bounds_duration:
            return self._format_duration_text(
                bounds_duration or {},
                prefix="für",
                field_name="boundsDuration"
            )

        return ""

    def _is_as_needed(self, dosage):
        """
        Prüft, ob eine Dosage als Bedarfsmedikation gekennzeichnet ist.

        Ein Bedarfskennzeichen liegt vor, wenn auf Ebene der Dosage
        asNeededBoolean=true angegeben ist (siehe schema-bedarfsmedikation.md).
        Der Einnahmeanlass asNeededFor ist optional. Ob es sich um eine *reine*
        Bedarfsdosierung oder um die Bedarfskennzeichnung eines strukturierten
        Schemas handelt, entscheidet zusätzlich das Vorhandensein von timing.
        """
        return dosage.get('asNeededBoolean') is True

    def _assemble(self, dosage, middle, core):
        """
        Baut den finalen Dosierungstext aus optionalem Zeitrahmen, optionalem
        Bedarfs-Einnahmeanlass, einem Zwischenteil `middle` (Intervall/Marker wie
        "täglich", "alle 8 Stunden" oder "") und dem Kern `core` (Dosis, 4-Schema-
        Muster oder Zeit-/Tagesabschnitts-Segmente).

        Nicht-Bedarf: [{Zeitrahmen} ][{middle}]: {core}
          - der Doppelpunkt trennt Zeitrahmen/Intervall (links) von der Dosis (rechts).

        Bedarf:
          [{Zeitrahmen} ]bei {Anlass}[, {middle}]: [{Mindestabstand} ]{core}
          - wie ohne Bedarf steht der Rhythmus links des Doppelpunkts; ein Komma
            trennt ihn vom Anlass. Der Anlass ist Freitext und kann auf eine Zahl
            enden ("bei Blutzucker über 250, 2 x täglich: …").
          - ein Mindestabstand kommt nur bei reiner Bedarfsmedikation vor; die
            Vorbedingungen (Bedarfskennzeichen, kein timing) prueft
            _check_as_needed_preconditions vorab ueber alle Elemente.
        """
        bounds_text = self._extract_bounds_text(dosage)

        if self._is_as_needed(dosage):
            # Einnahmeanlass ist optional; ohne Anlass generisch "bei Bedarf".
            reason_text = self._extract_as_needed_for_text(dosage)
            anlass = f"bei {reason_text}" if reason_text else "bei Bedarf"
            left = " ".join(part for part in [bounds_text, anlass] if part)
            if middle:
                left = f"{left}, {middle}"

            minimum_interval = self._extract_minimum_interval_text(dosage)
            right_parts = []
            if minimum_interval:
                right_parts.append(f"im Abstand von mindestens {minimum_interval}")
            if core:
                right_parts.append(core)
            right = " ".join(right_parts)
            return f"{left}: {right}" if right else left

        # Nicht-Bedarf: Zeitrahmen und Intervall/Marker links, Kern rechts.
        left = " ".join(part for part in [bounds_text, middle] if part)
        if left and core:
            return f"{left}: {core}"
        return left or core

    def _finalize_text(self, text):
        """
        Abschließende Aufbereitung eines generierten Textes (außer Freitext):
        Leerzeichen normalisieren.

        Der erzeugte Text ist durchgehend ein kleingeschriebenes Fragment. Die
        Groß-/Kleinschreibung am Satzanfang bleibt dem anzeigenden System
        überlassen, das den Text in seinen eigenen Kontext einbettet.
        """
        return self._normalize_whitespace(text)

    def _normalize_whitespace(self, text):
        """
        Reduziert jede Folge von Leerraum – einschließlich Zeilenumbrüchen aus
        übernommenen Freitextfeldern – zu einem einzelnen Leerzeichen und entfernt
        Leerzeichen vor Satzzeichen (: ; , .). Damit steht ein strukturiert
        erzeugter Text garantiert in einer Zeile. Gedankenstrich und Klammern
        bleiben unangetastet.

        Die Freitext-Dosierung durchläuft diese Normalisierung bewusst nicht:
        FreeTextMatchesRenderedText verlangt exakte Gleichheit von
        renderedDosageInstruction und Dosage.text.
        """
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r' ([;:.,])', r'\1', text)
        return text.strip()

    def _format_duration_text(self, duration, prefix="", field_name="Duration"):
        # Typen prueft Schritt 3; hier nur Vorhandensein.
        duration_value = duration.get('value')
        duration_unit = duration.get('code')
        if duration_value is None:
            raise ValueError(f"{field_name}.value ist für die Textgenerierung erforderlich.")
        # Wertebereich wird nicht geprüft; "für 0 Tage" ist ein eindeutiger Text.
        # TimingValuesPositive bzw. DosageLimitsPositive sind Sache des Profils.
        if not duration_unit:
            raise ValueError(f"{field_name}.code ist für die Textgenerierung erforderlich.")
        formatted_value = self._format_decimal_value(duration_value)
        formatted_unit = self._format_time_unit_german(duration_value, duration_unit)
        duration_text = f"{formatted_value} {formatted_unit}"
        return f"{prefix} {duration_text}" if prefix else duration_text

    def _format_bounds_period(self, bounds_period):
        has_start = 'start' in bounds_period
        has_end = 'end' in bounds_period
        if not has_start and not has_end:
            raise ValueError("boundsPeriod muss start und/oder end enthalten.")

        start_text = (
            self._format_datetime_german(bounds_period.get('start'), "boundsPeriod.start")
            if has_start else ""
        )
        end_text = (
            self._format_datetime_german(bounds_period.get('end'), "boundsPeriod.end")
            if has_end else ""
        )
        # Kleinschreibung wie bei allen uebrigen Bausteinen: der erzeugte Text
        # ist durchgehend ein Fragment, kein Satz.
        if has_start and has_end:
            return f"vom {start_text} bis zum {end_text}"
        if has_start:
            return f"ab dem {start_text}"
        return f"bis zum {end_text}"

    def _format_datetime_german(self, value, field_name="dateTime"):
        error_message = (
            f"{field_name} muss ein parsebares FHIR-dateTime mit vollständigem Datum "
            "im Format JJJJ-MM-TT sein; eine Uhrzeit erfordert eine Zeitzone."
        )
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            try:
                return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
            except ValueError:
                raise ValueError(error_message) from None

        if not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}'
            r'T(?:[01]\d|2[0-3]):[0-5]\d:(?:[0-5]\d|60)'
            r'(?:\.\d+)?'
            r'(?:Z|[+-](?:(?:0\d|1[0-3]):[0-5]\d|14:00))',
            value
        ):
            raise ValueError(error_message)

        # Sekunden werden nicht dargestellt. FHIR erlaubt beliebig viele
        # Bruchteilstellen und die Schaltsekunde 60; datetime.fromisoformat
        # versteht vor Python 3.11 nur 3 oder 6 Bruchteilstellen und nie :60.
        # Deshalb Sekunden samt Bruchteilen vor dem Parsen auf :00 setzen.
        normalized = re.sub(r'(T\d{2}:\d{2}):\d{2}(?:\.\d+)?', r'\1:00', value, count=1)
        try:
            parsed_datetime = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
            berlin_datetime = parsed_datetime.astimezone(self.OUTPUT_TIMEZONE)
        except ValueError:
            raise ValueError(error_message) from None

        return berlin_datetime.strftime("%d.%m.%Y um %H:%M Uhr")

    def _format_decimal_value(self, value):
        """
        Zahl mit deutschem Dezimalkomma und der Genauigkeit der Ressource
        darstellen.

        FHIR verlangt, die Genauigkeit eines decimal einschließlich nachfolgender
        Nullen auch für die Darstellung zu erhalten (2.50 ist nicht 2.5). Das
        gelingt nur, wenn der Wert als Decimal ankommt - die CLI liest JSON mit
        parse_float=Decimal. Ein float hat die Nullen beim Einlesen bereits
        verloren; er wird über str() (nicht über die Binärdarstellung) in ein
        Decimal überführt und bestmöglich ausgegeben.

        Exponentialschreibweise wird nie erzeugt: 1E-2 formatiert als "0,01",
        1E+2 als "100".
        """
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
        return format(decimal_value, 'f').replace('.', ',')

    def _format_time_german(self, time_string):
        """
        Format time string to German format with 'Uhr'.

        Args:
            time_string (str): Time in format "HH:MM" or "HH:MM:SS"

        Returns:
            str: German time format like "08:00 Uhr"

        Example:
            Input: "08:30"
            Output: "08:30 Uhr"
        """
        match = re.fullmatch(
            r'((?:[01]\d|2[0-3])):([0-5]\d)'
            r'(?::(?:[0-5]\d|60)(?:\.\d+)?)?',
            time_string
        )
        if not match:
            raise ValueError(
                "timeOfDay muss im Format HH:MM oder HH:MM:SS"
                "[.Bruchteile] angegeben sein."
            )
        return f"{match.group(1)}:{match.group(2)} Uhr"

    def _format_time_unit_german(self, value, unit):
        """
        Format time unit with proper German singular/plural form.

        Args:
            value (int/float): Numeric value
            unit (str): FHIR time unit code (s, min, h, d, wk, mo, a)

        Returns:
            str: German unit name (e.g., "Tag" vs "Tage")

        Raises:
            ValueError: Bei einem Code außerhalb der Tabelle. Ein roher UCUM-Code
                im erzeugten Text wäre für Patientinnen und Patienten nicht lesbar.
        """
        # Choose singular or plural based on value
        unit_dict = self.TIME_UNITS_SINGULAR if value == 1 else self.TIME_UNITS_PLURAL
        if unit not in unit_dict:
            raise ValueError(f"Nicht unterstützte Zeiteinheit: '{unit}'.")
        return unit_dict[unit]

    def _generate_day_of_week_text(self, dosage_instructions):
        """
        Generate text for DayOfWeek schema: specific weekdays with doses.

        Creates text showing which days of the week to take medication,
        with doses specified for each day.

        Args:
            dosage_instructions (list): List with dayOfWeek specifications

        Returns:
            str: Formatted text like "montags — je 1 Stück; mittwochs — je 2 Stück"

        Example FHIR input:
            - timing.repeat.dayOfWeek = ["mon", "wed"]
            - doseQuantity = {value: 1, unit: "Stück"}

        Example output: "montags — je 1 Stück; mittwochs — je 2 Stück"
        """

        # Group dosages by day and collect dose information
        day_to_dose = {}  # day_code -> (dose_value, unit)

        for dosage in dosage_instructions:
            timing = dosage.get('timing', {})
            repeat_element = timing.get('repeat', {})
            day_codes = repeat_element.get('dayOfWeek', [])

            # Extract dose information
            dose_value, dose_unit = self._extract_dose_quantity(dosage)

            # Associate this dose with each specified day
            for day_code in day_codes:
                self._require_day_code(day_code)
                if day_code not in day_to_dose:
                    day_to_dose[day_code] = (dose_value, dose_unit)
                elif self._slot_key(day_to_dose[day_code]) != self._slot_key((dose_value, dose_unit)):
                    raise ValueError(
                        f"Doppelte Belegung des Wochentags '{day_code}' mit unterschiedlicher Dosis.")

        # Sort days by weekday order and format each day
        sorted_days = sorted(day_to_dose.keys(),
                             key=self.DAY_ORDER.index)

        day_text_parts = []
        for day_code in sorted_days:
            dose_value, unit = day_to_dose[day_code]

            # Get German day name
            day_name = self.DAY_TRANSLATIONS[day_code]

            # Jedes Segment traegt die Einheit seines Elements.
            formatted_dose = dose_value if isinstance(dose_value, str) else self._format_decimal_value(dose_value)
            day_text_parts.append(f"{day_name} — je {formatted_dose} {unit}")

        combined_days = "; ".join(day_text_parts)
        text = self._assemble(dosage_instructions[0], "", combined_days)
        return self._append_trailing_instructions(text, dosage_instructions[0])

    def _generate_interval_text(self, dosage_instructions):
        """
        Generate text for Interval schema: regular time intervals.

        Creates text showing regular dosing intervals like "every 8 hours".
        For interval schema, there should only be one dosage instruction.

        Args:
            dosage_instructions (list): List containing single interval dosage

        Returns:
            str: Formatted text like "alle 8 Stunden: je 1 Stück" or "wöchentlich: je 2 mg"

        Example FHIR input:
            - timing.repeat.frequency = 3, period = 1, periodUnit = "d"
            - doseQuantity = {value: 1, unit: "Stück"}

        Example output: "3 x täglich: je 1 Stück"
        """

        # Ein Intervall laesst sich nicht aggregieren; ein zweites Element
        # entfiele stillschweigend (wie beim reinen Bedarf: Abbruch).
        if len(dosage_instructions) != 1:
            raise ValueError("Wiederkehrende Intervalle erlauben genau ein Dosage-Element.")

        # For interval schema, use the first (and typically only) dosage
        dosage = dosage_instructions[0]

        # Generate frequency description (e.g., "täglich", "alle 8 Stunden")
        frequency_text = self._generate_frequency_description(dosage)

        # Extract dose information
        dose_text = self._extract_dose_text_with_prefix(dosage)

        # [Zeitrahmen] [bei Anlass:] Intervall: Dosis  (Assembler regelt Bedarf/Doppelpunkt)
        text = self._assemble(dosage, frequency_text, dose_text)
        return self._append_trailing_instructions(text, dosage)

    def _generate_frequency_description(self, dosage):
        """
        Generate German frequency description from dosage timing.

        Converts FHIR frequency/period/periodUnit into German text like:
        - "täglich" (daily)
        - "3 x täglich" (3 times daily)
        - "alle 8 Stunden" (every 8 hours)
        - "wöchentlich" (weekly)

        Args:
            dosage (dict): Single dosage instruction with timing

        Returns:
            str: German frequency description
        """
        timing = dosage.get('timing', {})
        repeat_element = timing.get('repeat', {})

        frequency = repeat_element.get('frequency')
        frequency_max = repeat_element.get('frequencyMax')
        period = repeat_element.get('period')
        period_max = repeat_element.get('periodMax')
        period_unit = repeat_element.get('periodUnit')

        # Kurzformen nur für eine feste Periode von genau 1. Mit periodMax greift
        # die allgemeine Form ("alle 1 bis 3 Tage"), sonst entfiele die Obergrenze.
        # Daily patterns (periodUnit='d', period=1)
        if period_unit == 'd' and period == 1 and period_max is None:
            if frequency == 1 and frequency_max is None:
                return "täglich"
            else:
                return f"{self._format_range_value(frequency, frequency_max)} x täglich"

        # Weekly patterns (periodUnit='wk', period=1)
        if period_unit == 'wk' and period == 1 and period_max is None:
            if frequency == 1 and frequency_max is None:
                return "wöchentlich"
            else:
                return f"{self._format_range_value(frequency, frequency_max)} x wöchentlich"

        # Monthly patterns (periodUnit='mo', period=1)
        if period_unit == 'mo' and period == 1 and period_max is None:
            if frequency == 1 and frequency_max is None:
                return "monatlich"
            else:
                return f"{self._format_range_value(frequency, frequency_max)} x monatlich"

        # Kurzform nur für eine feste Frequenz von genau 1.
        if frequency == 1 and frequency_max is None:
            period_description = self._format_period_description(period, period_unit, period_max)
            return f"alle {period_description}"

        # Feste Frequenzen > 1 und Frequenzbereiche (auch 1 bis n).
        frequency_text = f"{self._format_range_value(frequency, frequency_max)} x"
        period_description = self._format_period_description(period, period_unit, period_max)
        return f"{frequency_text} alle {period_description}"

    def _format_period_description(self, period, period_unit, period_max=None):
        """
        Format a period with unit into German description.

        Args:
            period (int/float): Numeric period value
            period_unit (str): FHIR period unit code

        Returns:
            str: German period description like "3 Tage" or "2 Wochen"
        """
        formatted_period = self._format_range_value(period, period_max)
        unit_basis = period_max if period_max is not None else period
        unit_name = self._format_time_unit_german(unit_basis, period_unit)
        return f"{formatted_period} {unit_name}"

    def _format_period_only_rhythm(self, period, period_unit, period_max=None):
        """Formatiert einen Einnahmerhythmus ohne Frequenzangabe."""
        # 1 d ohne periodMax ist ein Tagesmuster und fuehrt nie zu Regel 7.
        if period_max is None and period == 1:
            if period_unit == 'wk':
                return "wöchentlich"
            if period_unit == 'mo':
                return "monatlich"
        return f"alle {self._format_period_description(period, period_unit, period_max)}"

    def _format_range_value(self, value, max_value=None):
        formatted_value = self._format_decimal_value(value)
        if max_value is None:
            return formatted_value
        return f"{formatted_value} bis {self._format_decimal_value(max_value)}"

    def _generate_dayofweek_and_time_schema_text(self, dosage_instructions):
        """
        Generate text for DayOfWeek + Time/4-Schema combination.

        This combines specific weekdays with either timeOfDay or when codes.
        The method determines which sub-type applies and delegates to the
        appropriate specialized generator.

        Args:
            dosage_instructions (list): List with both dayOfWeek and timing info

        Returns:
            str: Formatted combination text

        Sub-types:
        - DayOfWeek + TimeOfDay: "montags 08:00 Uhr — je 1 Stück; mittwochs 20:00 Uhr — je 2 Stück"
        - DayOfWeek + When: "montags 1-0-1-0 Stück; mittwochs 2-1-2-0 Stück"
        """

        # Der Untertyp (Uhrzeiten oder Tagesabschnitte) wird ueber ALLE Elemente
        # bestimmt. Beide Untertypen fallen unter dieselbe Schema-Regel, die
        # Schema-Gleichheitspruefung greift also nicht; entschiede allein das
        # erste Element, entfiele eine Gabe des anderen Untertyps stillschweigend
        # ("mon 08:00" + "mon MORN" -> nur die Uhrzeit).
        repeats = [dosage.get('timing', {}).get('repeat', {}) for dosage in dosage_instructions]
        uses_time_of_day = any(repeat.get('timeOfDay') for repeat in repeats)
        uses_when = any(repeat.get('when') for repeat in repeats)
        if uses_time_of_day and uses_when:
            raise ValueError(
                "Wochentags-Kombinationen mit Uhrzeiten und mit Tagesabschnitten "
                "dürfen nicht gemischt werden.")
        if uses_time_of_day:
            return self._generate_dayofweek_timeofday_combination(dosage_instructions)
        return self._generate_dayofweek_when_combination(dosage_instructions)

    def _generate_dayofweek_timeofday_combination(self, dosage_instructions):
        """
        Generate text for DayOfWeek + TimeOfDay combination.

        Example output: "montags 08:00 Uhr — je 1 Stück; mittwochs 20:00 Uhr — je 2 Stück"
        """

        # Group dosages by day of week
        day_to_dosages = {}  # day_code -> list of dosages

        for dosage in dosage_instructions:
            timing = dosage.get('timing', {})
            repeat_element = timing.get('repeat', {})
            day_codes = repeat_element.get('dayOfWeek', [])

            # Group dosages by day
            for day_code in day_codes:
                self._require_day_code(day_code)
                if day_code not in day_to_dosages:
                    day_to_dosages[day_code] = []
                day_to_dosages[day_code].append(dosage)

        # Format each day with its time-dose combinations
        sorted_days = sorted(day_to_dosages.keys(),
                             key=self.DAY_ORDER.index)

        day_text_parts = []
        for day_code in sorted_days:
            day_dosages = day_to_dosages[day_code]
            day_name = self.DAY_TRANSLATIONS[day_code]

            # Uhrzeiten innerhalb eines Tages: über alle Dosage-Elemente dieses
            # Tages global aufsteigend sortiert, mit Komma getrennt.
            combined_times = self._build_time_dose_segments(day_dosages)
            day_text_parts.append(f"{day_name} {combined_times}")

        combined_days = "; ".join(day_text_parts)
        text = self._assemble(dosage_instructions[0], "", combined_days)
        return self._append_trailing_instructions(text, dosage_instructions[0])

    def _generate_dayofweek_when_combination(self, dosage_instructions):
        """
        Generate text for DayOfWeek + When combination (4-Schema pattern per day).

        Example output: "montags 1-0-1-0 Stück; mittwochs 2-1-2-0 Stück"
        """

        # Group dosages by day and build 4-schema pattern for each day
        day_to_patterns = {}  # day_code -> {MORN: (dose, unit) | None, NOON: …, EVE: …, NIGHT: …}

        for dosage in dosage_instructions:
            timing = dosage.get('timing', {})
            repeat_element = timing.get('repeat', {})

            day_codes = repeat_element.get('dayOfWeek', [])
            when_codes = repeat_element.get('when', [])

            # Extract dose information
            dose_value, dose_unit = self._extract_dose_quantity(dosage)

            # For each day and each when code, set the dose
            for day_code in day_codes:
                self._require_day_code(day_code)
                if day_code not in day_to_patterns:
                    # None = nicht belegt; eine explizite 0 ist eine Belegung.
                    day_to_patterns[day_code] = {code: None for code in self.WHEN_CODES_ORDER}

                for when_code in when_codes:
                    if when_code not in day_to_patterns[day_code]:
                        raise ValueError(
                            f"Nicht unterstützter Tagesabschnitt (when): '{when_code}'.")
                    existing = day_to_patterns[day_code][when_code]
                    if existing is None:
                        day_to_patterns[day_code][when_code] = (dose_value, dose_unit)
                    elif self._slot_key(existing) != self._slot_key((dose_value, dose_unit)):
                        raise ValueError(
                            f"Doppelte Belegung der Kombination aus Wochentag '{day_code}' "
                            f"und Zeit-/Tagesabschnitt '{when_code}' mit unterschiedlicher Dosis.")

        # Format each day with its 4-schema pattern
        sorted_days = sorted(day_to_patterns.keys(),
                             key=self.DAY_ORDER.index)

        # Die Entscheidung kompakt/ausgeschrieben fällt einmal über alle Tage, damit
        # ein einzelner Tag mit variablem Wert oder gemischten Einheiten nicht zu
        # zwei Notationen in einem Text führt. Verschiedene Einheiten an
        # verschiedenen Tagen erzwingen das nicht: Jeder Tag traegt seine Einheit.
        has_variable = any(self._needs_written_form(pattern) for pattern in day_to_patterns.values())

        day_text_parts = []
        for day_code in sorted_days:
            dose_pattern = day_to_patterns[day_code]
            day_name = self.DAY_TRANSLATIONS[day_code]

            # Kompakt "1-0-1-0" oder ausgeschrieben (siehe _render_when_doses).
            day_content = self._render_when_doses(dose_pattern, force_written=has_variable)
            day_text_parts.append(f"{day_name} {day_content}")

        combined_days = "; ".join(day_text_parts)
        text = self._assemble(dosage_instructions[0], "", combined_days)
        return self._append_trailing_instructions(text, dosage_instructions[0])

    def _generate_interval_and_time_schema_text(self, dosage_instructions):
        """
        Generate text for Interval + Time/4-Schema combination.

        This combines regular intervals (non-daily) with either timeOfDay or when codes.

        Args:
            dosage_instructions (list): List with interval and timing information

        Returns:
            str: Formatted text like "alle 2 Tage: 08:00 Uhr — je 1 Stück, 18:00 Uhr — je 2 Stück"

        Example FHIR input:
            - timing.repeat.period = 2, periodUnit = "d"
            - timing.repeat.timeOfDay = ["08:00", "18:00"]
            - doseQuantity = {value: 1, unit: "Stück"}

        Example output: "alle 2 Tage: 08:00 Uhr — je 1 Stück, 18:00 Uhr — je 2 Stück"
        """

        # Extract the shared non-daily period from the first dosage. In an
        # interval combination, explicit timeOfDay/when segments already state
        # how often the dose is administered. An optional frequency is therefore
        # deliberately not included in the common text prefix.
        first_dosage = dosage_instructions[0]
        timing = first_dosage.get('timing', {})
        repeat_element = timing.get('repeat', {})

        # period und periodUnit sind hier vorhanden und numerisch: Die
        # Schema-Erkennung verlangt beide Schlüssel, die Typprüfung den Wert.
        period = repeat_element.get('period')
        period_max = repeat_element.get('periodMax')
        period_unit = repeat_element.get('periodUnit')
        interval_text = self._format_period_only_rhythm(
            period, period_unit, period_max
        )

        # Der Rhythmus wird nur aus dem ersten Element gelesen. Ein spaeteres
        # Element mit anderer Periode verloere sie stillschweigend - deshalb
        # Abbruch (TimingOnlyOneTimeForInterval verlangt dieselbe Periode).
        for dosage in dosage_instructions[1:]:
            other_repeat = dosage.get('timing', {}).get('repeat', {})
            other_text = self._format_period_only_rhythm(
                other_repeat.get('period'), other_repeat.get('periodUnit'),
                other_repeat.get('periodMax'))
            if other_text != interval_text:
                raise ValueError(
                    "Alle Dosage-Elemente einer Intervall-Kombination müssen "
                    "denselben Einnahmerhythmus tragen.")

        # Zeit-Schluessel ist die angezeigte Uhrzeit (HH:MM Uhr) bzw. der
        # when-Code, wie in den anderen Schemata: "08:00" und "08:00:00" sind
        # dieselbe Uhrzeit. Sortiert wird nach dem Eingabestring der ersten
        # Nennung (nullaufgefuellt, daher chronologisch).
        dose_by_key = {}      # Zeit-Schluessel -> Dosis-Text
        sort_key_by_key = {}  # Zeit-Schluessel -> Sortierschluessel

        def register(key, sort_key, dosage, duplicate_message):
            dose_text = self._extract_dose_text_with_prefix(dosage)
            known = dose_by_key.get(key)
            if known is None:
                dose_by_key[key] = dose_text
                sort_key_by_key[key] = sort_key
            elif known != dose_text:
                raise ValueError(duplicate_message)

        for dosage in dosage_instructions:
            repeat_element = dosage.get('timing', {}).get('repeat', {})

            for time_of_day in repeat_element.get('timeOfDay') or []:
                formatted_time = self._format_time_german(time_of_day)
                register(formatted_time, (1, time_of_day), dosage,
                         f"Doppelte Belegung der Uhrzeit '{formatted_time}' "
                         "mit unterschiedlicher Dosis.")

            for when_code in repeat_element.get('when') or []:
                if when_code not in self.WHEN_CODE_TRANSLATIONS:
                    raise ValueError(
                        f"Nicht unterstützter Tagesabschnitt (when): '{when_code}'.")
                register(self.WHEN_CODE_TRANSLATIONS[when_code],
                         (0, self.WHEN_CODES_ORDER.index(when_code)), dosage,
                         f"Doppelte Belegung des Tagesabschnitts '{when_code}' "
                         "mit unterschiedlicher Dosis.")

        # Tagesabschnitte in fester Reihenfolge vor allen Uhrzeiten.
        time_dose_parts = [
            f"{key} — {dose_by_key[key]}"
            for key in sorted(dose_by_key, key=sort_key_by_key.get)
        ]

        # Zeit-/Abschnitts-Segmente werden mit Komma getrennt (siehe Trennzeichen).
        combined_times = ", ".join(time_dose_parts)
        text = self._assemble(first_dosage, interval_text, combined_times)
        return self._append_trailing_instructions(text, first_dosage)

    def _generate_as_needed_text(self, dosage_instructions):
        """
        Reine Bedarfsdosierung (Option 1, einzeilig).

        Aufbau: [{Zeitrahmen} ]bei {Einnahmeanlass}: [im Abstand von mindestens
        {Mindestabstand} ]je {Dosis}[ — nicht mehr als {Maximalmenge} {Zeitraum}]
        ({Zeitraum} = "in 24 Stunden" bei 24 h bzw. "pro Tag" bei 1 d)

        Mindestabstand und Maximalmenge sind nur hier zulässig; zusammen mit einem
        strukturierten Rhythmus bricht der Algorithmus ab. Der Doppelpunkt hinter dem
        Einnahmeanlass, Zeitrahmen und Mindestabstand werden von _assemble
        gesetzt; die Maximalmenge wird zentral ergänzt
        (_append_trailing_instructions).
        """

        dosage = dosage_instructions[0]
        dose_text = self._extract_dose_text_with_prefix(dosage)
        text = self._assemble(dosage, "", dose_text)
        return self._append_trailing_instructions(text, dosage)

    def _extract_as_needed_for_text(self, dosage):
        # Mehrere asNeededFor sind zulässig (0..*); alle Anlässe werden in der
        # angegebenen Reihenfolge übernommen und als deutsche Aufzählung mit
        # abschließendem "oder" verbunden (z. B. "Kopfschmerzen oder Fieber").
        reasons = []
        for extension in dosage.get('extension', []):
            if extension.get('url') != self.URL_AS_NEEDED_FOR:
                continue
            concept = extension.get('valueCodeableConcept') or {}
            reason_text = concept.get('text')
            if not isinstance(reason_text, str) or not reason_text.strip():
                raise ValueError(
                    "asNeededFor.valueCodeableConcept.text ist für die "
                    "Textgenerierung erforderlich."
                )
            reasons.append(reason_text.strip())
        if not reasons:
            return ""
        if len(reasons) == 1:
            return reasons[0]
        return f"{', '.join(reasons[:-1])} oder {reasons[-1]}"

    def _extract_minimum_interval_text(self, dosage):
        for extension in dosage.get('modifierExtension', []):
            if extension.get('url') != self.URL_MINDESTABSTAND:
                continue
            duration = extension.get('valueDuration')
            if duration is None:
                raise ValueError(
                    "MinimumIntervalBetweenAdministrations.valueDuration ist "
                    "für die Textgenerierung erforderlich."
                )
            return self._format_duration_text(
                duration,
                field_name="MinimumIntervalBetweenAdministrations.valueDuration"
            )
        return ""

    def _extract_max_dose_text(self, dosage):
        if 'maxDosePerPeriod' not in dosage:
            return ""

        # Typen prueft Schritt 3; hier nur Vorhandensein.
        max_dose = dosage['maxDosePerPeriod']
        numerator = max_dose.get('numerator') or {}
        value = numerator.get('value')
        unit = numerator.get('unit')
        if value is None:
            raise ValueError(
                "maxDosePerPeriod.numerator.value ist für die "
                "Textgenerierung erforderlich."
            )
        if not unit or not unit.strip():
            raise ValueError(
                "maxDosePerPeriod.numerator.unit ist für die "
                "Textgenerierung erforderlich."
            )

        dose = self._format_decimal_value(value)
        dose = f"{dose} {unit.strip()}"
        period = self._format_max_dose_period(max_dose.get('denominator') or {})
        return f"nicht mehr als {dose} {period}"

    def _format_max_dose_period(self, denominator):
        """
        Bezugszeitraum der Maximalmenge, eingabetreu aus dem Nenner.
        Ausschließlich 1 d und 24 h sind zulässig; andere oder unvollständige
        Nenner führen zu einem Fehler.
        """
        value = denominator.get('value')
        code = denominator.get('code')
        if value is None:
            raise ValueError(
                "maxDosePerPeriod.denominator.value ist für die "
                "Textgenerierung erforderlich."
            )
        if not code:
            raise ValueError(
                "maxDosePerPeriod.denominator.code ist für die "
                "Textgenerierung erforderlich."
            )
        if value == 1 and code == 'd':
            return "pro Tag"
        if value == 24 and code == 'h':
            return "in 24 Stunden"
        raise ValueError(
            "maxDosePerPeriod.denominator muss 1 d oder 24 h sein."
        )

    def _append_trailing_instructions(self, text, dosage):
        # Maximalmenge (nur reine Bedarfsmedikation; Vorbedingungen prueft
        # _check_as_needed_preconditions): der Dosis mit Gedankenstrich nachgestellt.
        max_dose_text = self._extract_max_dose_text(dosage)
        if max_dose_text:
            text = f"{text} — {max_dose_text}"

        # Verabreichungsweg (route) ist im dgMP-Profil 0..0 und wird nicht dargestellt.

        instruction_text = self._extract_patient_instruction_text(dosage)
        if instruction_text:
            separator = " " if text.rstrip().endswith(".") else ". "
            text = f"{text}{separator}Hinweis: {instruction_text}"

        return text

    def _extract_patient_instruction_text(self, dosage):
        """
        Freitext-Einnahmehinweis aus patientInstruction (einzelner String, 0..1).
        In dgMP ist dies das Feld für ergänzende Patientenhinweise;
        additionalInstruction ist dort gestrichen (für künftige strukturierte
        Angaben reserviert).
        """
        instruction = dosage.get('patientInstruction')
        return instruction.strip() if instruction else ""

# ============================================================================
# MAIN FUNCTION - Command line interface
# ============================================================================

def main():
    """
    Command line interface for the dosage text generator.
    
    Usage: python medication-dosage-to-text.py <medication-resource.json>
    
    Reads a FHIR medication resource from JSON file and outputs German dosage text.
    """
    if len(sys.argv) < 2:
        print('Verwendung: python medication-dosage-to-text.py <medication-resource.json>', file=sys.stderr)
        print('', file=sys.stderr)
        print('Dieses Skript konvertiert FHIR-Medikationsdosierungen in deutschen Text.', file=sys.stderr)
        print('Unterstützte Ressourcentypen: MedicationRequest, MedicationDispense, MedicationStatement', file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Fehler: Datei '{file_path}' nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            # parse_float=Decimal: FHIR verlangt den Erhalt der Genauigkeit
            # (2.50 ist nicht 2.5); ein float verwirft nachfolgende Nullen.
            resource = json.load(file, parse_float=Decimal)

        generator = MedicationDosageTextGenerator()
        result = generator.generate_dosage_text(resource)
        print(result)

    except json.JSONDecodeError as e:
        print(f"Fehler: Ungültiges JSON in Datei '{file_path}'.", file=sys.stderr)
        print(f"JSON-Details: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unerwarteter Fehler beim Verarbeiten der Datei: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
