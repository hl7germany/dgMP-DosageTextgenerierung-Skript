#!/usr/bin/env python3
"""
FHIR Medication Dosage Text Generator

This script converts FHIR medication dosage instructions into human-readable German text.

It is an EXAMPLE implementation of the dosage text generation algorithm. The normative
definition is the "Dosierung: Textgenerierung" page of the German FHIR medication dosage
implementation guide — if this script and that page disagree, the page prevails.
`__version__` therefore names the version of the algorithm being implemented, not of the
script itself.

The script supports various dosage schemas:
- FreeText: User-provided text instructions
- AsNeeded: Pure as-needed dosage (e.g., "Bei Kopfschmerzen: je 1 Stück")
- 4-Schema: Morning-noon-evening-night pattern (e.g., "1-0-2-0 Stück")
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
from zoneinfo import ZoneInfo

__version__ = "2.0.0"
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
    URL_MINDESTABSTAND = 'http://ig.fhir.de/igs/medication/StructureDefinition/MindestabstandZwischenGaben'

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
            str: German dosage text (e.g., "1-0-2-0 Stück" or "täglich 08:00 Uhr — je 1 Stück")

        Examples:
            4-Schema: "1-0-2-0 Stück"
            TimeOfDay: "täglich: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück"
            DayOfWeek: "montags — je 1 Stück; mittwochs — je 2 Stück"
            Interval: "alle 8 Stunden: je 1 Stück"
        """
        # Step 1: Extract dosage instructions based on resource type
        dosage_instructions = self._extract_dosage_instructions(resource)
        if not dosage_instructions:
            return ""

        # timeOfDay und when schließen sich bereits auf Ebene des FHIR-Basisdatentyps
        # Timing aus (tim-10). Ohne diese Prüfung würde je nach Schema stillschweigend
        # eine der beiden Angaben verworfen.
        for dosage in dosage_instructions:
            repeat = (dosage.get("timing") or {}).get("repeat") or {}
            if repeat.get("timeOfDay") and repeat.get("when"):
                raise ValueError(
                    "timeOfDay und when dürfen nicht gemeinsam angegeben werden (tim-10)."
                )

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
        # abschließend normalisiert (Leerzeichen) und bei Bedarf großgeschrieben.
        if schema_type != self.SCHEMA_FREE_TEXT:
            result = self._finalize_text(result, dosage_instructions[0])
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
            return resource.get('dosageInstruction', [])
        elif resource_type == 'MedicationStatement':
            return resource.get('dosage', [])
        else:
            raise ValueError(f"Unsupported resource type: {resource_type}")

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
        if not dosage_instructions:
            return "Unknown"

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
        has_valid_weekday_legacy_fields = (
            'frequencyMax' not in repeat_element and
            'periodMax' not in repeat_element and
            (
                (not has_period and not has_period_unit) or
                (repeat_element.get('period') == 1 and
                 repeat_element.get('periodUnit') == 'wk')
            )
        )

        # Schema 3: 4-Schema. Konkrete Tagesabschnitte legen die Zahl der Gaben
        # bereits fest. frequency sowie das tägliche period/periodUnit-Paar sind
        # optional und ändern die Textausgabe nicht.
        if (has_when_codes and not has_time_of_day and not has_day_of_week and
                (is_daily_pattern or (not has_period and not has_period_unit))):
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
                (is_daily_pattern or (not has_period and not has_period_unit))):
            return self.SCHEMA_TIME_OF_DAY

        # Schema 7: Äußeres, nicht tägliches Intervall mit konkreten Zeitpunkten.
        # frequency ist hier redundant, aber optional zulässig.
        if (is_non_daily_pattern and (has_time_of_day or has_when_codes) and
                not has_day_of_week and
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
        notation: "morning-noon-evening-night" (e.g., "1-0-2-0 Stück").

        Args:
            dosage_instructions (list): List containing dosage instructions with 'when' codes

        Returns:
            str: Formatted text like "1-0-2-0 Stück" or "für 7 Tage: 2-1-2-1 mg"

        Example FHIR input:
            - Dosage with when=['MORN'], doseQuantity={value: 1, unit: 'Stück'}
            - Dosage with when=['EVE'], doseQuantity={value: 2, unit: 'Stück'}

        Example output: "1-0-2-0 Stück"
        """
        # Initialize dose amounts for each time period (default to 0)
        dose_amounts = {code: 0 for code in self.WHEN_CODES_ORDER}
        assigned_slots = set()  # bereits belegte when-Positionen (Duplikaterkennung)
        unit_text = ""

        # Process each dosage instruction to extract dose amounts
        for dosage in dosage_instructions:
            timing = dosage.get('timing', {})
            repeat_element = timing.get('repeat', {})
            when_codes = repeat_element.get('when', [])

            # Extract dose quantity information
            dose_value, dose_unit = self._extract_dose_quantity(dosage)
            if not unit_text:
                unit_text = dose_unit

            # Assign dose value to each specified time period
            for when_code in when_codes:
                if when_code not in dose_amounts:
                    raise ValueError(
                        f"Nicht unterstützter Tagesabschnitt (when): '{when_code}'.")
                if when_code in assigned_slots:
                    raise ValueError(
                        f"Doppelte Belegung des Tagesabschnitts '{when_code}' im 4-Schema.")
                assigned_slots.add(when_code)
                dose_amounts[when_code] = dose_value

        # Feste Dosen -> kompakt "1-0-2-0"; sobald eine Position variabel ist,
        # wird gemäß Option 2 die ausgeschriebene Segmentform verwendet
        # (siehe _render_when_doses).
        dose_pattern = self._render_when_doses(dose_amounts, unit_text)
        text = self._assemble(dosage_instructions[0], "", dose_pattern)
        return self._append_trailing_instructions(text, dosage_instructions[0])

    def _render_when_doses(self, dose_amounts, unit_text, force_written=False):
        """
        Render eine MORN/NOON/EVE/NIGHT-Dosisbelegung.

        Feste Dosen ergeben die kompakte, positionelle Notation
        "1-0-2-0 [Einheit]". Sobald eine Position variabel ist (Bereich, z. B.
        "1 bis 2"), wird das Schema gemäß Option 2 in die ausgeschriebene
        Segmentform überführt: nur belegte (nicht-null) Positionen erscheinen als
        "morgens — je 1 bis 2 Stück, abends — je 2 Stück".

        `force_written` erzwingt die ausgeschriebene Form auch für eine für sich
        genommen feste Belegung. Die Wochentags-Kombination nutzt das, damit die
        Notation über alle Tage hinweg einheitlich bleibt, sobald irgendein Tag
        einen variablen Wert enthält.
        """
        has_variable = force_written or any(
            isinstance(value, str) for value in dose_amounts.values())

        if not has_variable:
            pattern = "-".join(self._format_decimal_value(dose_amounts[code])
                               for code in self.WHEN_CODES_ORDER)
            return f"{pattern} {unit_text}" if unit_text else pattern

        segments = []
        for code in self.WHEN_CODES_ORDER:
            value = dose_amounts[code]
            # Unbelegte Positionen (0) entfallen in der ausgeschriebenen Form.
            if not isinstance(value, str) and value == 0:
                continue
            formatted = value if isinstance(value, str) else self._format_decimal_value(value)
            dose = f"je {formatted} {unit_text}" if unit_text else f"je {formatted}"
            segments.append(f"{self.WHEN_CODE_TRANSLATIONS[code]} — {dose}")
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
        if not dosage_instructions:
            return ""

        # Extract and combine all text values
        text_parts = []
        for dosage in dosage_instructions:
            text_content = dosage.get('text', '').strip()
            if text_content:
                text_parts.append(text_content)

        return " ".join(text_parts)

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
        if not dosage_instructions:
            return ""

        combined_instructions = self._build_time_dose_segments(dosage_instructions)
        if not combined_instructions:
            return ""

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

            if not time_of_day_list:
                continue

            dose_text = self._extract_dose_text_with_prefix(dosage)
            for time_value in time_of_day_list:
                # Sortierschlüssel ist der unveränderte Eingabestring: Sekunden und
                # Sekundenbruchteile bleiben so sortierwirksam, auch wenn sie in der
                # Ausgabe (HH:MM Uhr) entfallen. Da timeOfDay nullaufgefüllt sein
                # muss, entspricht die lexikographische der chronologischen Ordnung.
                time_dose_pairs.append(
                    (time_value, self._format_time_german(time_value), dose_text))

        if not time_dose_pairs:
            return ""

        time_dose_pairs.sort(key=lambda pair: pair[0])

        segments = []
        for _, formatted_time, dose_text in time_dose_pairs:
            if segments and segments[-1][1] == dose_text:
                segments[-1][0].append(formatted_time)
            else:
                segments.append(([formatted_time], dose_text))

        return ", ".join(
            f"{', '.join(times)} — {dose_text}" for times, dose_text in segments)

    def _dose_value_as_number(self, value, field_name):
        """Dosiswert als Zahl lesen.

        FHIR führt Dosiswerte als decimal; einzelne Serialisierer liefern sie als
        String. Beides wird akzeptiert, alles andere abgewiesen — ein nicht
        auswertbarer Wert darf nicht ungeprüft in den Dosierungstext gelangen.
        """
        if isinstance(value, bool):
            raise ValueError(f"{field_name} muss numerisch sein.")
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} muss numerisch sein.")

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

        if 'doseQuantity' in first_dose:
            dose_quantity = first_dose.get('doseQuantity') or {}
            dose_value = dose_quantity.get('value')
            unit = dose_quantity.get('unit')
            if dose_value is None:
                raise ValueError("doseQuantity.value ist für die Textgenerierung erforderlich.")
            if not unit:
                raise ValueError("doseQuantity.unit ist für die Textgenerierung erforderlich.")
            if self._dose_value_as_number(dose_value, 'doseQuantity.value') <= 0:
                raise ValueError("doseQuantity.value muss größer als 0 sein.")
            return (dose_value, unit)

        if 'doseRange' in first_dose:
            dose_range = first_dose.get('doseRange') or {}
            low = dose_range.get('low')
            high = dose_range.get('high')

            if not high or high.get('value') is None:
                raise ValueError("doseRange.high.value ist für die Textgenerierung erforderlich.")
            if not high.get('unit'):
                raise ValueError("doseRange.high.unit ist für die Textgenerierung erforderlich.")
            if self._dose_value_as_number(high.get('value'), 'doseRange.high.value') <= 0:
                raise ValueError("doseRange.high.value muss größer als 0 sein.")

            if low:
                if low.get('value') is None:
                    raise ValueError("doseRange.low.value ist für die Textgenerierung erforderlich.")
                if not low.get('unit'):
                    raise ValueError("doseRange.low.unit ist für die Textgenerierung erforderlich.")
                if self._dose_value_as_number(low.get('value'), 'doseRange.low.value') < 0:
                    raise ValueError("doseRange.low.value darf nicht negativ sein.")
                if low.get('unit') != high.get('unit'):
                    raise ValueError("doseRange.low.unit und doseRange.high.unit müssen übereinstimmen.")
                value = (
                    f"{self._format_decimal_value(low.get('value'))} bis "
                    f"{self._format_decimal_value(high.get('value'))}"
                )
            else:
                value = f"bis zu {self._format_decimal_value(high.get('value'))}"
            return (value, high.get('unit'))

        raise ValueError("Dosisangabe in doseAndRate[0] fehlt.")

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

        if unit:
            return f"je {formatted_dose} {unit}"
        else:
            return f"je {formatted_dose}"

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

        Bedarf ohne strukturierten Rhythmus:
          [{Zeitrahmen} ]bei {Einnahmeanlass}: [{Mindestabstand} ]{core}
        Bedarf mit strukturiertem Rhythmus:
          [{Zeitrahmen} ]bei {Einnahmeanlass}: {middle} {core}
          [, mit mindestens {Mindestabstand} Abstand]
          - der Doppelpunkt steht direkt hinter dem Einnahmeanlass.
          - bei einem strukturierten Rhythmus wird der Mindestabstand nachgestellt,
            damit Rhythmus und Mindestabstand sprachlich klar getrennt sind.
        """
        bounds_text = self._extract_bounds_text(dosage)

        if self._is_as_needed(dosage):
            # Einnahmeanlass ist optional; ohne Anlass generisch "bei Bedarf".
            reason_text = self._extract_as_needed_for_text(dosage)
            anlass = f"bei {reason_text}" if reason_text else "bei Bedarf"
            left = " ".join(part for part in [bounds_text, anlass] if part)

            minimum_interval = self._extract_minimum_interval_text(dosage)
            right_parts = []
            if minimum_interval and not middle:
                right_parts.append(f"im Abstand von mindestens {minimum_interval}")
            if middle:
                right_parts.append(middle)
            if core:
                right_parts.append(core)
            right = " ".join(right_parts)
            if minimum_interval and middle:
                right = f"{right}, mit mindestens {minimum_interval} Abstand"
            return f"{left}: {right}" if right else left

        # Nicht-Bedarf: Zeitrahmen und Intervall/Marker links, Kern rechts.
        left = " ".join(part for part in [bounds_text, middle] if part)
        if left and core:
            return f"{left}: {core}"
        return left or core

    def _finalize_text(self, text, dosage):
        """
        Abschließende Aufbereitung eines generierten Textes (außer Freitext):
        Leerzeichen normalisieren und bei Bedarfsmedikation den Zeilenanfang
        großschreiben.
        """
        if not text:
            return text

        text = self._normalize_whitespace(text)
        if text and self._is_as_needed(dosage):
            text = text[0].upper() + text[1:]
        return text

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
        duration_value = duration.get('value')
        duration_unit = duration.get('code')
        if duration_value is None:
            raise ValueError(f"{field_name}.value ist für die Textgenerierung erforderlich.")
        if (isinstance(duration_value, bool) or
                not isinstance(duration_value, (int, float)) or
                duration_value <= 0):
            raise ValueError(f"{field_name}.value muss größer als 0 sein.")
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
        if has_start and has_end:
            return f"Vom {start_text} bis zum {end_text}"
        if has_start:
            return f"Ab dem {start_text}"
        return f"Bis zum {end_text}"

    def _format_datetime_german(self, value, field_name="dateTime"):
        error_message = (
            f"{field_name} muss ein parsebares FHIR-dateTime mit vollständigem Datum "
            "im Format JJJJ-MM-TT sein; eine Uhrzeit erfordert eine Zeitzone."
        )
        if not isinstance(value, str):
            raise ValueError(error_message)

        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            try:
                return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
            except ValueError:
                raise ValueError(error_message) from None

        if not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}'
            r'T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d'
            r'(?:\.\d+)?'
            r'(?:Z|[+-](?:(?:0\d|1[0-3]):[0-5]\d|14:00))',
            value
        ):
            raise ValueError(error_message)

        try:
            parsed_datetime = datetime.fromisoformat(value.replace("Z", "+00:00"))
            berlin_datetime = parsed_datetime.astimezone(self.OUTPUT_TIMEZONE)
        except ValueError:
            raise ValueError(error_message) from None

        return berlin_datetime.strftime("%d.%m.%Y um %H:%M Uhr")

    def _format_decimal_value(self, value):
        """
        Format a numeric value with German decimal separator (comma).
        Removes unnecessary decimal places for whole numbers.

        Args:
            value (float/int): Numeric value

        Returns:
            str: Formatted value (e.g., "1" instead of "1,0", "1,5" kept as is)
        """
        if value == int(value):
            return str(int(value))
        else:
            # Use comma as decimal separator for German format
            return str(value).replace('.', ',')

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
        if not isinstance(time_string, str):
            raise ValueError(
                "timeOfDay muss im Format HH:MM oder HH:MM:SS"
                "[.Bruchteile] angegeben sein."
            )

        match = re.fullmatch(
            r'((?:[01]\d|2[0-3])):([0-5]\d)'
            r'(?::[0-5]\d(?:\.\d+)?)?',
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
        if not dosage_instructions:
            return ""

        # Group dosages by day and collect dose information
        day_to_dose = {}  # day_code -> dose_value
        unit_text = ""

        for dosage in dosage_instructions:
            timing = dosage.get('timing', {})
            repeat_element = timing.get('repeat', {})
            day_codes = repeat_element.get('dayOfWeek', [])

            # Extract dose information
            dose_value, dose_unit = self._extract_dose_quantity(dosage)
            if not unit_text:
                unit_text = dose_unit

            # Associate this dose with each specified day
            for day_code in day_codes:
                if day_code in day_to_dose and day_to_dose[day_code] != dose_value:
                    raise ValueError(
                        f"Doppelte Belegung des Wochentags '{day_code}' mit unterschiedlicher Dosis.")
                day_to_dose[day_code] = dose_value

        if not day_to_dose:
            return ""

        # Sort days by weekday order and format each day
        sorted_days = sorted(day_to_dose.keys(),
                             key=lambda day: self.DAY_ORDER.index(day) if day in self.DAY_ORDER else 99)

        day_text_parts = []
        for day_code in sorted_days:
            dose_value = day_to_dose[day_code]

            # Get German day name
            day_name = self.DAY_TRANSLATIONS.get(day_code, day_code)

            # Format dose value and create day entry
            formatted_dose = dose_value if isinstance(dose_value, str) else self._format_decimal_value(dose_value)
            dose_text = f"je {formatted_dose}"
            if unit_text:
                dose_text += f" {unit_text}"

            day_text_parts.append(f"{day_name} — {dose_text}")

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
        if not dosage_instructions:
            return ""

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

        # Handle missing timing information
        if frequency is None and period is None and period_unit is None:
            return ""

        # Daily patterns (periodUnit='d', period=1)
        if period_unit == 'd' and period == 1:
            if frequency == 1 and frequency_max is None:
                return "täglich"
            else:
                return f"{self._format_range_value(frequency, frequency_max)} x täglich"

        # Weekly patterns (periodUnit='wk', period=1)
        if period_unit == 'wk' and period == 1:
            if frequency == 1 and frequency_max is None:
                return "wöchentlich"
            else:
                return f"{self._format_range_value(frequency, frequency_max)} x wöchentlich"

        # Monthly patterns (periodUnit='mo', period=1)
        if period_unit == 'mo' and period == 1:
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
        if period_max is None and period == 1:
            if period_unit == 'd':
                return "täglich"
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
        if not dosage_instructions:
            return ""

        # Check whether this uses timeOfDay or when codes
        first_dosage = dosage_instructions[0]
        timing = first_dosage.get('timing', {})
        repeat_element = timing.get('repeat', {})

        has_time_of_day = 'timeOfDay' in repeat_element and repeat_element['timeOfDay']
        has_when_codes = 'when' in repeat_element and repeat_element['when']

        # Delegate to appropriate sub-type generator
        if has_time_of_day and not has_when_codes:
            return self._generate_dayofweek_timeofday_combination(dosage_instructions)
        elif has_when_codes:  # Handle when codes (with or without timeOfDay)
            return self._generate_dayofweek_when_combination(dosage_instructions)
        else:
            # Fallback to when-based logic if neither present
            return self._generate_dayofweek_when_combination(dosage_instructions)

    def _generate_dayofweek_timeofday_combination(self, dosage_instructions):
        """
        Generate text for DayOfWeek + TimeOfDay combination.

        Example output: "montags 08:00 Uhr — je 1 Stück; mittwochs 20:00 Uhr — je 2 Stück"
        """
        if not dosage_instructions:
            return ""

        # Group dosages by day of week
        day_to_dosages = {}  # day_code -> list of dosages

        for dosage in dosage_instructions:
            timing = dosage.get('timing', {})
            repeat_element = timing.get('repeat', {})
            day_codes = repeat_element.get('dayOfWeek', [])

            # Group dosages by day
            for day_code in day_codes:
                if day_code not in day_to_dosages:
                    day_to_dosages[day_code] = []
                day_to_dosages[day_code].append(dosage)

        # Format each day with its time-dose combinations
        sorted_days = sorted(day_to_dosages.keys(),
                             key=lambda day: self.DAY_ORDER.index(day) if day in self.DAY_ORDER else 99)

        day_text_parts = []
        for day_code in sorted_days:
            day_dosages = day_to_dosages[day_code]
            day_name = self.DAY_TRANSLATIONS.get(day_code, day_code)

            # Uhrzeiten innerhalb eines Tages: über alle Dosage-Elemente dieses
            # Tages global aufsteigend sortiert, mit Komma getrennt.
            combined_times = self._build_time_dose_segments(day_dosages)
            if combined_times:
                day_text_parts.append(f"{day_name} {combined_times}")

        combined_days = "; ".join(day_text_parts)
        text = self._assemble(dosage_instructions[0], "", combined_days)
        return self._append_trailing_instructions(text, dosage_instructions[0])

    def _generate_dayofweek_when_combination(self, dosage_instructions):
        """
        Generate text for DayOfWeek + When combination (4-Schema pattern per day).

        Example output: "montags 1-0-1-0 Stück; mittwochs 2-1-2-0 Stück"
        """
        if not dosage_instructions:
            return ""

        # Group dosages by day and build 4-schema pattern for each day
        day_to_patterns = {}  # day_code -> {MORN: dose, NOON: dose, EVE: dose, NIGHT: dose}
        unit_text = ""

        for dosage in dosage_instructions:
            timing = dosage.get('timing', {})
            repeat_element = timing.get('repeat', {})

            day_codes = repeat_element.get('dayOfWeek', [])
            when_codes = repeat_element.get('when', [])

            # Extract dose information
            dose_value, dose_unit = self._extract_dose_quantity(dosage)
            if not unit_text:
                unit_text = dose_unit

            # For each day and each when code, set the dose
            for day_code in day_codes:
                if day_code not in day_to_patterns:
                    day_to_patterns[day_code] = {code: 0 for code in self.WHEN_CODES_ORDER}

                for when_code in when_codes:
                    if when_code not in day_to_patterns[day_code]:
                        raise ValueError(
                            f"Nicht unterstützter Tagesabschnitt (when): '{when_code}'.")
                    existing = day_to_patterns[day_code][when_code]
                    if existing != 0 and existing != dose_value:
                        raise ValueError(
                            f"Doppelte Belegung der Kombination aus Wochentag '{day_code}' "
                            f"und Zeit-/Tagesabschnitt '{when_code}' mit unterschiedlicher Dosis.")
                    day_to_patterns[day_code][when_code] = dose_value

        if not day_to_patterns:
            return ""

        # Format each day with its 4-schema pattern
        sorted_days = sorted(day_to_patterns.keys(),
                             key=lambda day: self.DAY_ORDER.index(day) if day in self.DAY_ORDER else 99)

        # Die Entscheidung kompakt/ausgeschrieben fällt einmal über alle Tage, damit
        # ein einzelner variabler Wert nicht zu zwei Notationen in einem Text führt.
        has_variable = any(
            isinstance(value, str)
            for pattern in day_to_patterns.values()
            for value in pattern.values()
        )

        day_text_parts = []
        for day_code in sorted_days:
            dose_pattern = day_to_patterns[day_code]
            day_name = self.DAY_TRANSLATIONS.get(day_code, day_code)

            # Feste Dosen -> kompakt "1-0-1-0"; variable -> ausgeschrieben (Option 2).
            day_content = self._render_when_doses(
                dose_pattern, unit_text, force_written=has_variable)
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
        if not dosage_instructions:
            return ""

        # Extract the shared non-daily period from the first dosage. In an
        # interval combination, explicit timeOfDay/when segments already state
        # how often the dose is administered. An optional frequency is therefore
        # deliberately not included in the common text prefix.
        first_dosage = dosage_instructions[0]
        timing = first_dosage.get('timing', {})
        repeat_element = timing.get('repeat', {})

        period = repeat_element.get('period')
        period_max = repeat_element.get('periodMax')
        period_unit = repeat_element.get('periodUnit')
        if period is None or period_unit is None:
            raise ValueError(
                "Intervall-Kombinationen erfordern period und periodUnit."
            )
        interval_text = self._format_period_only_rhythm(
            period, period_unit, period_max
        )

        # Group dosages by time or when code
        time_to_dosages = {}  # time_key -> list of dosages

        for dosage in dosage_instructions:
            timing = dosage.get('timing', {})
            repeat_element = timing.get('repeat', {})

            # Process timeOfDay entries
            if 'timeOfDay' in repeat_element and repeat_element['timeOfDay']:
                for time_of_day in repeat_element['timeOfDay']:
                    if time_of_day in time_to_dosages:
                        if self._extract_dose_quantity(time_to_dosages[time_of_day][0]) != self._extract_dose_quantity(dosage):
                            raise ValueError(
                                f"Doppelte Belegung des Zeit-Schlüssels '{time_of_day}' mit unterschiedlicher Dosis.")
                    else:
                        time_to_dosages[time_of_day] = []
                    time_to_dosages[time_of_day].append(dosage)

            # Process when code entries
            elif 'when' in repeat_element and repeat_element['when']:
                self._extract_dose_quantity(dosage)
                for when_code in repeat_element['when']:
                    if when_code not in self.WHEN_CODE_TRANSLATIONS:
                        raise ValueError(
                            f"Nicht unterstützter Tagesabschnitt (when): '{when_code}'.")
                    if when_code in time_to_dosages:
                        if self._extract_dose_quantity(time_to_dosages[when_code][0]) != self._extract_dose_quantity(dosage):
                            raise ValueError(
                                f"Doppelte Belegung des Zeit-Schlüssels '{when_code}' mit unterschiedlicher Dosis.")
                    else:
                        time_to_dosages[when_code] = []
                    time_to_dosages[when_code].append(dosage)

        # Generate time-dose text parts
        time_dose_parts = []

        # Sort times: when codes first (in logical order), then timeOfDay chronologically
        def time_sort_key(time_key):
            if time_key in self.WHEN_CODES_ORDER:
                # When codes: use position in defined order
                return (0, self.WHEN_CODES_ORDER.index(time_key))
            else:
                # TimeOfDay: sort chronologically by time string
                return (1, time_key)

        sorted_times = sorted(time_to_dosages.keys(), key=time_sort_key)

        for time_key in sorted_times:
            dosages_at_time = time_to_dosages[time_key]

            # Format time display
            if time_key in self.WHEN_CODE_TRANSLATIONS:
                # This is a when code - use German translation
                time_display = self.WHEN_CODE_TRANSLATIONS[time_key]
            else:
                # This is a timeOfDay - format as German time
                time_display = self._format_time_german(time_key)

            dose_text = self._extract_dose_text_with_prefix(dosages_at_time[0])

            time_dose_parts.append(f"{time_display} — {dose_text}")

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

        Bei strukturiertem Bedarf wird der Mindestabstand stattdessen nach dem
        Schema-Kern als ", mit mindestens ... Abstand" ausgegeben. Der Doppelpunkt
        hinter dem Einnahmeanlass, Zeitrahmen und Mindestabstand werden von
        _assemble gesetzt; die Maximalmenge und der Großbuchstabe am Zeilenanfang
        werden zentral ergänzt (_append_trailing_instructions / _finalize_text).
        """
        if not dosage_instructions:
            return ""

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
            if not duration:
                raise ValueError(
                    "MindestabstandZwischenGaben.valueDuration ist "
                    "für die Textgenerierung erforderlich."
                )
            return self._format_duration_text(
                duration,
                field_name="MindestabstandZwischenGaben.valueDuration"
            )
        return ""

    def _extract_max_dose_text(self, dosage):
        if 'maxDosePerPeriod' not in dosage:
            return ""

        max_dose = dosage.get('maxDosePerPeriod') or {}
        numerator = max_dose.get('numerator') or {}
        value = numerator.get('value')
        unit = numerator.get('unit')
        if value is None:
            raise ValueError(
                "maxDosePerPeriod.numerator.value ist für die "
                "Textgenerierung erforderlich."
            )
        if (isinstance(value, bool) or
                not isinstance(value, (int, float))):
            raise ValueError(
                "maxDosePerPeriod.numerator.value muss numerisch sein."
            )
        if not isinstance(unit, str) or not unit.strip():
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
        # Maximalmenge (nur Bedarfsmedikation): der Dosis mit Gedankenstrich nachgestellt.
        if self._is_as_needed(dosage):
            max_dose_text = self._extract_max_dose_text(dosage)
            if max_dose_text:
                text = f"{text} — {max_dose_text}"

        # Verabreichungsweg (route) ist im dgMP-Profil 0..0 und wird nicht dargestellt.

        instruction_text = self._extract_patient_instruction_text(dosage)
        if instruction_text:
            separator = " " if text.endswith(".") else ". "
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
            resource = json.load(file)

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
