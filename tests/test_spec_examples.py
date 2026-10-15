#!/usr/bin/env python3
"""Die Spezifikation als Test.

SpecExamplesTest: Jedes Textbeispiel der Spezifikation wird als FHIR-Ressource
nachgebaut und muss zeichengenau erzeugt werden.

SpecTextExamplesTest: Jedes Textbeispiel im Fliesstext der Spezifikation
kommt in einer erwarteten Ausgabe vor - ein vollstaendiger Text exakt, ein
Baustein (etwa `je 1 bis 2 Stück`) als Teil einer Ausgabe. Ein neues Beispiel
ohne Testfall laesst den Test scheitern.

ErrorListTest: Jeder Eintrag der Fehlerliste ("Fehler und Validierung") hat
mindestens einen Fall, der genau diese Meldung auslöst. Ein Meta-Test liest die
Meldungen aus der Spezifikation und prüft, dass jede von einem Fall abgedeckt
ist - eine neue oder geänderte Meldung in der Spezifikation ohne passenden Fall
lässt den Test scheitern, ebenso eine Meldung, die das Skript nicht (mehr)
erzeugen kann.
"""

import importlib.util
import re
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "medication-dosage-to-text.py"
SPEC_PATH = ROOT / "dosage-text-algorithm-spec.md"
SPEC = importlib.util.spec_from_file_location("medication_dosage_to_text", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

GENERATOR = MODULE.MedicationDosageTextGenerator
AS_NEEDED_FOR = GENERATOR.URL_AS_NEEDED_FOR
MIN_INTERVAL = GENERATOR.URL_MINDESTABSTAND


def req(*dosages):
    return {"resourceType": "MedicationRequest", "dosageInstruction": list(dosages)}


def dq(value, unit="Stück"):
    return [{"doseQuantity": {"value": value, "unit": unit}}]


def dr(low, high, unit="Stück"):
    dose_range = {"high": {"value": high, "unit": unit}}
    if low is not None:
        dose_range["low"] = {"value": low, "unit": unit}
    return [{"doseRange": dose_range}]


def d(dose, repeat=None, **extra):
    dosage = {"doseAndRate": dose}
    if repeat is not None:
        dosage["timing"] = {"repeat": repeat}
    dosage.update(extra)
    return dosage


def reason(*texts):
    return [{"url": AS_NEEDED_FOR, "valueCodeableConcept": {"text": text}} for text in texts]


def min_interval(value, code):
    return [{"url": MIN_INTERVAL, "valueDuration": {"value": value, "code": code}}]


def max_dose(value, per_value, per_code):
    return {"numerator": {"value": value, "unit": "Stück"},
            "denominator": {"value": per_value, "code": per_code}}


EVERY_8_H = {"frequency": 1, "period": 8, "periodUnit": "h"}

# (Fundstelle in der Spezifikation, Ressource, erwarteter Text)
EXAMPLES = (
    # Teil A: Dosis
    ("Dosis: je 1 Stück", req(d(dq(1), EVERY_8_H)), "alle 8 Stunden: je 1 Stück"),
    ("Dosis: je 1 bis 2 Stück", req(d(dr(1, 2), EVERY_8_H)), "alle 8 Stunden: je 1 bis 2 Stück"),
    ("Dosis: je bis zu 2 Stück", req(d(dr(None, 2), EVERY_8_H)), "alle 8 Stunden: je bis zu 2 Stück"),
    ("Dosis: Dezimalkomma 1,5", req(d(dq(Decimal("1.5")), EVERY_8_H)), "alle 8 Stunden: je 1,5 Stück"),
    ("Dosis: 1 bleibt 1", req(d(dq(Decimal("1")), EVERY_8_H)), "alle 8 Stunden: je 1 Stück"),
    ("Dosis: 1.0 bleibt 1,0", req(d(dq(Decimal("1.0")), EVERY_8_H)), "alle 8 Stunden: je 1,0 Stück"),
    ("Dosis: 2.50 bleibt 2,50", req(d(dq(Decimal("2.50")), EVERY_8_H)), "alle 8 Stunden: je 2,50 Stück"),
    ("Dosis: 1e-2 wird 0,01", req(d(dq(Decimal("1e-2"), "mg"), EVERY_8_H)), "alle 8 Stunden: je 0,01 mg"),
    # Teil A: Zeitrahmen
    ("Dauer: für 1 Tag", req(d(dq(1), {**EVERY_8_H, "boundsDuration": {"value": 1, "code": "d"}})),
     "für 1 Tag alle 8 Stunden: je 1 Stück"),
    ("Dauer: für 7 Tage", req(d(dq(1), {**EVERY_8_H, "boundsDuration": {"value": 7, "code": "d"}})),
     "für 7 Tage alle 8 Stunden: je 1 Stück"),
    ("Zeitpunkt: ab dem", req(d(dq(1), {"when": ["MORN"], "boundsPeriod": {"start": "2026-06-05"}})),
     "ab dem 05.06.2026 täglich: 1-0-0-0 Stück"),
    ("Zeitpunkt: vom … bis zum", req(d(dq(1), {"when": ["MORN"],
                                              "boundsPeriod": {"start": "2026-06-05", "end": "2026-07-05"}})),
     "vom 05.06.2026 bis zum 05.07.2026 täglich: 1-0-0-0 Stück"),
    ("Zeitpunkt: bis zum", req(d(dq(1), {"when": ["MORN"], "boundsPeriod": {"end": "2026-07-05"}})),
     "bis zum 05.07.2026 täglich: 1-0-0-0 Stück"),
    ("Zeitpunkt: Uhrzeit ohne Sekunden",
     req(d(dq(1), {"when": ["MORN"], "boundsPeriod": {"start": "2026-06-05T08:15:45+02:00"}})),
     "ab dem 05.06.2026 um 08:15 Uhr täglich: 1-0-0-0 Stück"),
    ("Zeitpunkt: Europe/Berlin, Datumswechsel",
     req(d(dq(1), {"when": ["MORN"], "boundsPeriod": {"start": "2026-06-05T23:30:45Z"}})),
     "ab dem 06.06.2026 um 01:30 Uhr täglich: 1-0-0-0 Stück"),
    ("Zeitpunkt: Winterzeit",
     req(d(dq(1), {"when": ["MORN"], "boundsPeriod": {"start": "2026-01-15T23:30:00Z"}})),
     "ab dem 16.01.2026 um 00:30 Uhr täglich: 1-0-0-0 Stück"),
    # Teil A: Einnahmerhythmus
    ("Rhythmus: täglich", req(d(dq(1), {"frequency": 1, "period": 1, "periodUnit": "d"})), "täglich: je 1 Stück"),
    ("Rhythmus: 3 x täglich", req(d(dq(1), {"frequency": 3, "period": 1, "periodUnit": "d"})), "3 x täglich: je 1 Stück"),
    ("Rhythmus: wöchentlich", req(d(dq(1), {"frequency": 1, "period": 1, "periodUnit": "wk"})), "wöchentlich: je 1 Stück"),
    ("Rhythmus: 2 x wöchentlich", req(d(dq(1), {"frequency": 2, "period": 1, "periodUnit": "wk"})), "2 x wöchentlich: je 1 Stück"),
    ("Rhythmus: monatlich", req(d(dq(1), {"frequency": 1, "period": 1, "periodUnit": "mo"})), "monatlich: je 1 Stück"),
    ("Rhythmus: 2 x monatlich", req(d(dq(1), {"frequency": 2, "period": 1, "periodUnit": "mo"})), "2 x monatlich: je 1 Stück"),
    ("Rhythmus: alle 8 Stunden", req(d(dq(1), EVERY_8_H)), "alle 8 Stunden: je 1 Stück"),
    ("Rhythmus: 1 bis 2 x alle 8 Stunden", req(d(dq(1), {**EVERY_8_H, "frequencyMax": 2})),
     "1 bis 2 x alle 8 Stunden: je 1 Stück"),
    ("Rhythmus: 2 x alle 8 Stunden", req(d(dq(1), {**EVERY_8_H, "frequency": 2})), "2 x alle 8 Stunden: je 1 Stück"),
    ("Rhythmus: 2 bis 3 x täglich", req(d(dq(1), {"frequency": 2, "frequencyMax": 3, "period": 1, "periodUnit": "d"})),
     "2 bis 3 x täglich: je 1 Stück"),
    ("Rhythmus: alle 2 bis 3 Tage", req(d(dq(1), {"frequency": 1, "period": 2, "periodMax": 3, "periodUnit": "d"})),
     "alle 2 bis 3 Tage: je 1 Stück"),
    ("Rhythmus: alle 1 bis 3 Tage", req(d(dq(1), {"frequency": 1, "period": 1, "periodMax": 3, "periodUnit": "d"})),
     "alle 1 bis 3 Tage: je 1 Stück"),
    ("Rhythmus: Kombination wöchentlich", req(d(dq(1), {"period": 1, "periodUnit": "wk", "when": ["MORN"]})),
     "wöchentlich: morgens — je 1 Stück"),
    ("Rhythmus: Kombination monatlich", req(d(dq(1), {"period": 1, "periodUnit": "mo", "timeOfDay": ["08:00:00"]})),
     "monatlich: 08:00 Uhr — je 1 Stück"),
    # Teil A: Uhrzeiten
    ("Uhrzeit: 08:00 Uhr", req(d(dq(1), {"timeOfDay": ["08:00:00"]})), "täglich: 08:00 Uhr — je 1 Stück"),
    ("Uhrzeit: Beispiel zwei Elemente",
     req(d(dq(1), {"timeOfDay": ["08:00:00", "12:00:00"]}), d(dq(2), {"timeOfDay": ["20:00:00"]})),
     "täglich: 08:00 Uhr, 12:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück"),
    # Teil A: Einnahmeanlass
    ("Anlass: bei Kopfschmerzen", req(d(dq(1), asNeededBoolean=True, extension=reason("Kopfschmerzen"))),
     "bei Kopfschmerzen: je 1 Stück"),
    ("Anlass: bei Bedarf", req(d(dq(1), asNeededBoolean=True)), "bei Bedarf: je 1 Stück"),
    ("Anlass: zwei Anlässe", req(d(dq(1), asNeededBoolean=True, extension=reason("Kopfschmerzen", "Fieber"))),
     "bei Kopfschmerzen oder Fieber: je 1 Stück"),
    ("Anlass: drei Anlässe",
     req(d(dq(1), asNeededBoolean=True, extension=reason("Kopfschmerzen", "Fieber", "Gliederschmerzen"))),
     "bei Kopfschmerzen, Fieber oder Gliederschmerzen: je 1 Stück"),
    # Teil A: Mindestabstand, Maximalmenge, Hinweis
    ("Mindestabstand: 4 Stunden", req(d(dq(1), asNeededBoolean=True, modifierExtension=min_interval(4, "h"))),
     "bei Bedarf: im Abstand von mindestens 4 Stunden je 1 Stück"),
    ("Mindestabstand: 30 Minuten", req(d(dq(1), asNeededBoolean=True, modifierExtension=min_interval(30, "min"))),
     "bei Bedarf: im Abstand von mindestens 30 Minuten je 1 Stück"),
    ("Maximalmenge: in 24 Stunden", req(d(dq(1), asNeededBoolean=True, maxDosePerPeriod=max_dose(6, 24, "h"))),
     "bei Bedarf: je 1 Stück — nicht mehr als 6 Stück in 24 Stunden"),
    ("Maximalmenge: pro Tag", req(d(dq(1), asNeededBoolean=True, maxDosePerPeriod=max_dose(6, 1, "d"))),
     "bei Bedarf: je 1 Stück — nicht mehr als 6 Stück pro Tag"),
    ("Hinweis: Nach dem Essen", req(d(dq(1), {"when": ["MORN", "EVE"]}, patientInstruction="Nach dem Essen")),
     "täglich: 1-0-1-0 Stück. Hinweis: Nach dem Essen"),
    ("Hinweis: Leerraum am Rand entfällt", req(d(dq(1), {"when": ["MORN"]}, patientInstruction="  Mit Wasser ")),
     "täglich: 1-0-0-0 Stück. Hinweis: Mit Wasser"),
    # Teil A: Normalisierung
    ("Normalisierung: Umbruch in übernommenem Feld",
     req(d(dq(1), {"when": ["MORN"]}, patientInstruction="Nach dem\nEssen")),
     "täglich: 1-0-0-0 Stück. Hinweis: Nach dem Essen"),
    ("Normalisierung: geschütztes Leerzeichen in der Einheit",
     req(d(dq(1, "Stück (Tabl.)"), EVERY_8_H)),
     "alle 8 Stunden: je 1 Stück (Tabl.)"),
    # Teil B
    ("4-Schema: täglich: 1-0-2-0 Stück", req(d(dq(1), {"when": ["MORN"]}), d(dq(2), {"when": ["EVE"]})),
     "täglich: 1-0-2-0 Stück"),
    ("4-Schema: mit Zeitrahmen",
     req(d(dq(1, "Kapseln"), {"when": ["MORN", "NOON", "EVE", "NIGHT"], "boundsDuration": {"value": 5, "code": "d"}})),
     "für 5 Tage täglich: 1-1-1-1 Kapseln"),
    ("4-Schema: Variabilität", req(d(dr(1, 2), {"when": ["MORN"]}), d(dq(2), {"when": ["EVE"]})),
     "täglich: morgens — je 1 bis 2 Stück, abends — je 2 Stück"),
    ("4-Schema: explizite 0 in der ausgeschriebenen Form",
     req(d(dq(0), {"when": ["MORN"]}), d(dr(1, 2), {"when": ["EVE"]})),
     "täglich: morgens — je 0 Stück, abends — je 1 bis 2 Stück"),
    ("4-Schema: abweichende Einheiten in ausgeschriebener Form",
     req(d(dq(1), {"when": ["MORN"]}), d(dq(2, "Messlöffel"), {"when": ["EVE"]})),
     "täglich: morgens — je 1 Stück, abends — je 2 Messlöffel"),
    ("Uhrzeiten-Schema: zwei Dosen", req(d(dq(1), {"timeOfDay": ["08:00:00"]}), d(dq(2), {"timeOfDay": ["20:00:00"]})),
     "täglich: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück"),
    ("Uhrzeiten-Schema: gleiche Dosis", req(d(dq(1), {"timeOfDay": ["08:00:00", "20:00:00"]})),
     "täglich: 08:00 Uhr, 20:00 Uhr — je 1 Stück"),
    ("Uhrzeiten-Schema: Sortierung vor Zusammenfassung",
     req(d(dq(1), {"timeOfDay": ["01:00:00", "23:00:00"]}), d(dq(3), {"timeOfDay": ["18:00:00"]})),
     "täglich: 01:00 Uhr — je 1 Stück, 18:00 Uhr — je 3 Stück, 23:00 Uhr — je 1 Stück"),
    ("Wochentags-Schema", req(d(dq(1), {"dayOfWeek": ["mon"]}), d(dq(2), {"dayOfWeek": ["wed"]})),
     "montags — je 1 Stück; mittwochs — je 2 Stück"),
    ("Wochentags-Schema: Einheit je Segment",
     req(d(dq(1), {"dayOfWeek": ["mon"]}), d(dq(2, "Messlöffel"), {"dayOfWeek": ["wed"]})),
     "montags — je 1 Stück; mittwochs — je 2 Messlöffel"),
    ("Wochentags-Schema mit Zeitrahmen",
     req(d(dq(1), {"dayOfWeek": ["mon"], "boundsDuration": {"value": 7, "code": "d"}})),
     "für 7 Tage: montags — je 1 Stück"),
    ("Intervall-Schema", req(d(dq(1), {"frequency": 1, "period": 4, "periodUnit": "h"})), "alle 4 Stunden: je 1 Stück"),
    ("Intervall-Kombination",
     req(d(dq(1), {"period": 2, "periodUnit": "d", "timeOfDay": ["08:00:00"]}),
         d(dq(2), {"period": 2, "periodUnit": "d", "timeOfDay": ["18:00:00"]})),
     "alle 2 Tage: 08:00 Uhr — je 1 Stück, 18:00 Uhr — je 2 Stück"),
    ("Intervall-Kombination mit Zeitrahmen",
     req(d(dq(1), {"period": 2, "periodUnit": "d", "timeOfDay": ["08:00:00"],
                   "boundsDuration": {"value": 7, "code": "d"}})),
     "für 7 Tage alle 2 Tage: 08:00 Uhr — je 1 Stück"),
    ("Wochentags-Kombination mit Uhrzeiten",
     req(d(dq(1), {"dayOfWeek": ["mon"], "timeOfDay": ["08:00:00"]}),
         d(dq(2), {"dayOfWeek": ["mon"], "timeOfDay": ["12:00:00"]}),
         d(dq(1), {"dayOfWeek": ["wed"], "timeOfDay": ["20:00:00"]})),
     "montags 08:00 Uhr — je 1 Stück, 12:00 Uhr — je 2 Stück; mittwochs 20:00 Uhr — je 1 Stück"),
    ("Wochentags-Kombination mit Tagesabschnitten",
     req(d(dq(1), {"dayOfWeek": ["mon"], "when": ["MORN", "EVE"]}),
         d(dq(2), {"dayOfWeek": ["wed"], "when": ["MORN", "EVE"]}),
         d(dq(1), {"dayOfWeek": ["wed"], "when": ["NOON"]})),
     "montags 1-0-1-0 Stück; mittwochs 2-1-2-0 Stück"),
    ("Wochentags-Kombination: Variabilität",
     req(d(dr(1, 2), {"dayOfWeek": ["mon"], "when": ["MORN"]}), d(dq(2), {"dayOfWeek": ["wed"], "when": ["EVE"]})),
     "montags morgens — je 1 bis 2 Stück; mittwochs abends — je 2 Stück"),
    ("Bedarf: vollständig",
     req(d(dq(1), asNeededBoolean=True, extension=reason("Kopfschmerzen"),
           modifierExtension=min_interval(4, "h"), maxDosePerPeriod=max_dose(6, 24, "h"))),
     "bei Kopfschmerzen: im Abstand von mindestens 4 Stunden je 1 Stück — nicht mehr als 6 Stück in 24 Stunden"),
    ("Bedarf: mit Uhrzeiten",
     req(d(dq(1), {"timeOfDay": ["08:00:00"]}, asNeededBoolean=True),
         d(dq(2), {"timeOfDay": ["20:00:00"]}, asNeededBoolean=True)),
     "bei Bedarf, täglich: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück"),
    ("Bedarf: mit Intervall",
     req(d(dq(1), EVERY_8_H, asNeededBoolean=True, extension=reason("Kopfschmerzen"))),
     "bei Kopfschmerzen, alle 8 Stunden: je 1 Stück"),
    ("Bedarf: mit 4-Schema",
     req(d(dq(1), {"when": ["MORN"]}, asNeededBoolean=True), d(dq(2), {"when": ["EVE"]}, asNeededBoolean=True)),
     "bei Bedarf, täglich: 1-0-2-0 Stück"),
    ("Bedarf: mit Zeitrahmen",
     req(d(dq(1), {"when": ["MORN"], "boundsPeriod": {"start": "2026-06-05"}}, asNeededBoolean=True)),
     "ab dem 05.06.2026 bei Bedarf, täglich: 1-0-0-0 Stück"),
    ("Bedarf: mit Wochentagen (kein Intervall, kein Komma)",
     req(d(dq(1), {"dayOfWeek": ["mon"]}, asNeededBoolean=True), d(dq(2), {"dayOfWeek": ["wed"]}, asNeededBoolean=True)),
     "bei Bedarf: montags — je 1 Stück; mittwochs — je 2 Stück"),
    ("Trennzeichen: Komma trennt Anlass mit Zahl vom Intervall",
     req(d(dq(2, "IE"), {"frequency": 2, "period": 1, "periodUnit": "d"}, asNeededBoolean=True,
           extension=reason("Blutzucker über 250"))),
     "bei Blutzucker über 250, 2 x täglich: je 2 IE"),
    ("Trennzeichen: Komma nach Aufzählung der Anlässe",
     req(d(dq(1), EVERY_8_H, asNeededBoolean=True, extension=reason("Kopfschmerzen", "Fieber"))),
     "bei Kopfschmerzen oder Fieber, alle 8 Stunden: je 1 Stück"),
    ("Intervall-Kombination: dieselbe Uhrzeit (HH:MM und HH:MM:SS) mit derselben Dosis nur einmal",
     req(d(dq(1), {"period": 2, "periodUnit": "d", "timeOfDay": ["08:00"]}),
         d(dq(1), {"period": 2, "periodUnit": "d", "timeOfDay": ["08:00:00", "20:00:00"]})),
     "alle 2 Tage: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 1 Stück"),
    ("Intervall-Kombination: Tagesabschnitte vor Uhrzeiten",
     req(d(dq(1), {"period": 2, "periodUnit": "d", "timeOfDay": ["08:00:00"]}),
         d(dq(2), {"period": 2, "periodUnit": "d", "when": ["EVE"]})),
     "alle 2 Tage: abends — je 2 Stück, 08:00 Uhr — je 1 Stück"),
    ("Hinweis: Punkt mit nachfolgendem Leerraum", req(d(dq(1, "Tbl. "), {"when": ["MORN"]}, patientInstruction="X")),
     "täglich: 1-0-0-0 Tbl. Hinweis: X"),
    ("Wochentag: ein Tag", req(d(dq(1), {"dayOfWeek": ["mon"]})), "montags — je 1 Stück"),
    ("Bedarf mit Wochentag: ein Tag", req(d(dq(1), {"dayOfWeek": ["mon"]}, asNeededBoolean=True)),
     "bei Bedarf: montags — je 1 Stück"),
    ("Wochentags-Kombination ausgeschrieben: mehrere Tagesabschnitte eines Tages",
     req(d(dr(1, 2), {"dayOfWeek": ["mon"], "when": ["MORN"]}), d(dq(2), {"dayOfWeek": ["mon"], "when": ["EVE"]})),
     "montags morgens — je 1 bis 2 Stück, abends — je 2 Stück"),
    ("Hinweis", req(d(dq(1), EVERY_8_H, patientInstruction="Mit ausreichend Wasser einnehmen")),
     "alle 8 Stunden: je 1 Stück. Hinweis: Mit ausreichend Wasser einnehmen"),
    ("Einnahmeanlass: fremde Extension wird ignoriert",
     req(d(dq(1), asNeededBoolean=True,
           extension=[{"url": "http://example.org/andere", "valueString": "x"}, *reason("Kopfschmerzen")])),
     "bei Kopfschmerzen: je 1 Stück"),
    ("Freitext", req({"text": "Nach Bedarf bei Schmerzen"}), "Nach Bedarf bei Schmerzen"),
)

ERROR_CASES = (
    ("resourceType", {"resourceType": "Patient"}, "Unsupported resource type: Patient"),
    ("Typ decimal", req(d(dq(1), {**EVERY_8_H, "period": "8"})), "timing.repeat.period muss numerisch sein."),
    ("Typ positiveInt", req(d(dq(1), {**EVERY_8_H, "frequency": 2.5})),
     "timing.repeat.frequency muss eine ganze Zahl sein."),
    ("Typ code", req(d(dq(1), {**EVERY_8_H, "periodUnit": 5})), "timing.repeat.periodUnit muss ein String sein."),
    ("Typ Liste", req(d(dq(1), {"when": "MORN"})), "timing.repeat.when muss eine Liste sein."),
    ("Typ Objekt", req({"timing": "täglich", "doseAndRate": dq(1)}), "timing muss ein Objekt sein."),
    ("Typ boolean", req(d(dq(1), {"when": ["MORN"]}, asNeededBoolean="true")),
     "asNeededBoolean muss ein boolescher Wert sein."),
    ("kein Schema", req(d(dq(1), {"frequency": 1})), "Die Dosierung entspricht keinem unterstützten Dosierungsschema."),
    ("tim-10", req(d(dq(1), {"when": ["MORN"], "timeOfDay": ["08:00:00"]})),
     "timeOfDay und when dürfen nicht gemeinsam angegeben werden (tim-10)."),
    ("reiner Bedarf, zwei Elemente", req(d(dq(1), asNeededBoolean=True), d(dq(2), asNeededBoolean=True)),
     "Reine Bedarfsmedikation erlaubt genau ein Dosage-Element."),
    ("ohne doseAndRate", req({"timing": {"repeat": {"when": ["MORN"]}}}),
     "doseAndRate ist für die Textgenerierung erforderlich."),
    ("doseAndRate leere Liste", req(d([], {"when": ["MORN"]})), "doseAndRate ist für die Textgenerierung erforderlich."),
    ("timing ohne repeat", req({"timing": {"code": {"text": "BID"}}, "doseAndRate": dq(1)}),
     "Die Dosierung entspricht keinem unterstützten Dosierungsschema."),
    ("doseAndRate[0] leer", req(d([{}], {"when": ["MORN"]})), "Dosisangabe in doseAndRate[0] fehlt."),
    ("doseQuantity ohne value", req(d([{"doseQuantity": {"unit": "Stück"}}], {"when": ["MORN"]})),
     "doseQuantity.value ist für die Textgenerierung erforderlich."),
    ("doseQuantity ohne unit", req(d([{"doseQuantity": {"value": 1}}], {"when": ["MORN"]})),
     "doseQuantity.unit ist für die Textgenerierung erforderlich."),
    ("Dosiswert negativ", req(d(dq(-1), {"when": ["MORN"]})), "doseQuantity.value darf nicht negativ sein."),
    ("doseRange.low negativ", req(d(dr(-1, 2), {"when": ["MORN"]})), "doseRange.low.value darf nicht negativ sein."),
    ("doseRange.high negativ", req(d(dr(None, -2), {"when": ["MORN"]})), "doseRange.high.value darf nicht negativ sein."),
    ("Dosiswert nicht numerisch", req(d(dq("2"), {"when": ["MORN"]})), "doseQuantity.value muss numerisch sein."),
    ("doseRange ohne high", req(d([{"doseRange": {"low": {"value": 1, "unit": "Stück"}}}], {"when": ["MORN"]})),
     "doseRange.high.value ist für die Textgenerierung erforderlich."),
    ("doseRange.high ohne unit", req(d([{"doseRange": {"high": {"value": 2}}}], {"when": ["MORN"]})),
     "doseRange.high.unit ist für die Textgenerierung erforderlich."),
    ("doseRange.low leer", req(d([{"doseRange": {"low": {}, "high": {"value": 2, "unit": "Stück"}}}], {"when": ["MORN"]})),
     "doseRange.low.value ist für die Textgenerierung erforderlich."),
    ("Maximalmenge mit Rhythmus", req(d(dq(1), EVERY_8_H, asNeededBoolean=True, maxDosePerPeriod=max_dose(4, 1, "d"))),
     "Eine Maximalmenge ist nur bei reiner Bedarfsmedikation zulässig, nicht zusammen mit einem strukturierten Rhythmus."),
    ("Mindestabstand mit Rhythmus", req(d(dq(1), EVERY_8_H, asNeededBoolean=True, modifierExtension=min_interval(4, "h"))),
     "Ein Mindestabstand ist nur bei reiner Bedarfsmedikation zulässig, nicht zusammen mit einem strukturierten Rhythmus."),
    ("Schema-Mix", req(d(dq(1), {"when": ["MORN"]}), d(dq(2), {"dayOfWeek": ["mon"]})),
     "Alle Dosage-Elemente müssen demselben Schema folgen; Element 1 ergibt '4-Schema', Element 2 'DayOfWeek'."),
    ("low.unit weicht ab", req(d([{"doseRange": {"low": {"value": 1, "unit": "mg"}, "high": {"value": 2, "unit": "Stück"}}}],
                                 {"when": ["MORN"]})),
     "doseRange.low.unit und doseRange.high.unit müssen übereinstimmen."),
    ("boundsDuration ohne value", req(d(dq(1), {"when": ["MORN"], "boundsDuration": {"code": "d"}})),
     "boundsDuration.value ist für die Textgenerierung erforderlich."),
    ("boundsDuration ohne code", req(d(dq(1), {"when": ["MORN"], "boundsDuration": {"value": 7}})),
     "boundsDuration.code ist für die Textgenerierung erforderlich."),
    ("boundsDuration nicht numerisch", req(d(dq(1), {"when": ["MORN"], "boundsDuration": {"value": "7", "code": "d"}})),
     "timing.repeat.boundsDuration.value muss numerisch sein."),
    ("boundsPeriod und boundsDuration",
     req(d(dq(1), {"when": ["MORN"], "boundsDuration": {"value": 7, "code": "d"},
                   "boundsPeriod": {"start": "2026-06-05"}})),
     "boundsPeriod und boundsDuration dürfen nicht gleichzeitig vorhanden sein."),
    ("boundsPeriod leer", req(d(dq(1), {"when": ["MORN"], "boundsPeriod": {}})),
     "boundsPeriod muss start und/oder end enthalten."),
    ("boundsPeriod ohne Zeitzone", req(d(dq(1), {"when": ["MORN"], "boundsPeriod": {"start": "2026-06-05T08:00:00"}})),
     "boundsPeriod.start muss ein parsebares FHIR-dateTime mit vollständigem Datum im Format JJJJ-MM-TT sein; "
     "eine Uhrzeit erfordert eine Zeitzone."),
    ("boundsPeriod.end unvollständig", req(d(dq(1), {"when": ["MORN"], "boundsPeriod": {"end": "2026-06"}})),
     "boundsPeriod.end muss ein parsebares FHIR-dateTime mit vollständigem Datum im Format JJJJ-MM-TT sein; "
     "eine Uhrzeit erfordert eine Zeitzone."),
    ("boundsPeriod: Kalenderdatum ungültig", req(d(dq(1), {"when": ["MORN"], "boundsPeriod": {"start": "2026-02-30"}})),
     "boundsPeriod.start muss ein parsebares FHIR-dateTime mit vollständigem Datum im Format JJJJ-MM-TT sein; "
     "eine Uhrzeit erfordert eine Zeitzone."),
    ("boundsPeriod: Kalenderdatum mit Uhrzeit ungültig",
     req(d(dq(1), {"timeOfDay": ["08:00:00"], "boundsPeriod": {"start": "2026-02-30T08:00:00+01:00"}})),
     "boundsPeriod.start muss ein parsebares FHIR-dateTime mit vollständigem Datum im Format JJJJ-MM-TT sein; "
     "eine Uhrzeit erfordert eine Zeitzone."),
    ("timeOfDay nicht nullaufgefüllt", req(d(dq(1), {"timeOfDay": ["8:00"]})),
     "timeOfDay muss im Format HH:MM oder HH:MM:SS[.Bruchteile] angegeben sein."),
    ("asNeededFor ohne Text",
     req(d(dq(1), asNeededBoolean=True, extension=[{"url": AS_NEEDED_FOR, "valueCodeableConcept": {}}])),
     "asNeededFor.valueCodeableConcept.text ist für die Textgenerierung erforderlich."),
    ("Mindestabstand ohne valueDuration",
     req(d(dq(1), asNeededBoolean=True, modifierExtension=[{"url": MIN_INTERVAL}])),
     "MinimumIntervalBetweenAdministrations.valueDuration ist für die Textgenerierung erforderlich."),
    ("Mindestabstand ohne value",
     req(d(dq(1), asNeededBoolean=True, modifierExtension=[{"url": MIN_INTERVAL, "valueDuration": {"code": "h"}}])),
     "MinimumIntervalBetweenAdministrations.valueDuration.value ist für die Textgenerierung erforderlich."),
    ("Mindestabstand ohne code",
     req(d(dq(1), asNeededBoolean=True, modifierExtension=[{"url": MIN_INTERVAL, "valueDuration": {"value": 4}}])),
     "MinimumIntervalBetweenAdministrations.valueDuration.code ist für die Textgenerierung erforderlich."),
    ("Mindestabstand Zeiteinheit", req(d(dq(1), asNeededBoolean=True, modifierExtension=min_interval(4, "x"))),
     "Nicht unterstützte Zeiteinheit: 'x'."),
    ("Mindestabstand nicht numerisch",
     req(d(dq(1), asNeededBoolean=True, modifierExtension=min_interval("4", "h"))),
     "modifierExtension[].valueDuration.value muss numerisch sein."),
    ("Maximalmenge ohne Zähler-Wert",
     req(d(dq(1), asNeededBoolean=True, maxDosePerPeriod={"numerator": {"unit": "Stück"},
                                                          "denominator": {"value": 1, "code": "d"}})),
     "maxDosePerPeriod.numerator.value ist für die Textgenerierung erforderlich."),
    ("Maximalmenge ohne Zähler-Einheit",
     req(d(dq(1), asNeededBoolean=True, maxDosePerPeriod={"numerator": {"value": 4},
                                                          "denominator": {"value": 1, "code": "d"}})),
     "maxDosePerPeriod.numerator.unit ist für die Textgenerierung erforderlich."),
    ("Maximalmenge ohne Nenner-Wert",
     req(d(dq(1), asNeededBoolean=True, maxDosePerPeriod={"numerator": {"value": 4, "unit": "Stück"},
                                                          "denominator": {"code": "d"}})),
     "maxDosePerPeriod.denominator.value ist für die Textgenerierung erforderlich."),
    ("Maximalmenge ohne Nenner-Code",
     req(d(dq(1), asNeededBoolean=True, maxDosePerPeriod={"numerator": {"value": 4, "unit": "Stück"},
                                                          "denominator": {"value": 1}})),
     "maxDosePerPeriod.denominator.code ist für die Textgenerierung erforderlich."),
    ("Maximalmenge ohne Zähler",
     req(d(dq(1), asNeededBoolean=True, maxDosePerPeriod={"denominator": {"value": 1, "code": "d"}})),
     "maxDosePerPeriod.numerator.value ist für die Textgenerierung erforderlich."),
    ("Maximalmenge nicht numerisch", req(d(dq(1), asNeededBoolean=True, maxDosePerPeriod=max_dose("4", 1, "d"))),
     "maxDosePerPeriod.numerator.value muss numerisch sein."),
    ("Maximalmenge Nenner", req(d(dq(1), asNeededBoolean=True, maxDosePerPeriod=max_dose(2, 12, "h"))),
     "maxDosePerPeriod.denominator muss 1 d oder 24 h sein."),
    ("when-Code", req(d(dq(1), {"when": ["XYZ"]})), "Nicht unterstützter Tagesabschnitt (when): 'XYZ'."),
    ("when-Code in der Wochentags-Kombination", req(d(dq(1), {"dayOfWeek": ["mon"], "when": ["XYZ"]})),
     "Nicht unterstützter Tagesabschnitt (when): 'XYZ'."),
    ("dayOfWeek-Code", req(d(dq(1), {"dayOfWeek": ["xyz"]})), "Nicht unterstützter Wochentag (dayOfWeek): 'xyz'."),
    ("Duplikat 4-Schema", req(d(dq(1), {"when": ["MORN"]}), d(dq(2), {"when": ["MORN"]})),
     "Doppelte Belegung des Tagesabschnitts 'MORN' mit unterschiedlicher Dosis."),
    ("Duplikat Wochentag", req(d(dq(1), {"dayOfWeek": ["mon"]}), d(dq(2), {"dayOfWeek": ["mon"]})),
     "Doppelte Belegung des Wochentags 'mon' mit unterschiedlicher Dosis."),
    ("Duplikat Wochentag+Tagesabschnitt",
     req(d(dq(1), {"dayOfWeek": ["mon"], "when": ["MORN"]}), d(dq(2), {"dayOfWeek": ["mon"], "when": ["MORN"]})),
     "Doppelte Belegung der Kombination aus Wochentag 'mon' und Zeit-/Tagesabschnitt 'MORN' mit unterschiedlicher Dosis."),
    ("Duplikat Intervall-Kombination, Uhrzeit (HH:MM und HH:MM:SS)",
     req(d(dq(1), {"period": 2, "periodUnit": "d", "timeOfDay": ["08:00"]}),
         d(dq(2), {"period": 2, "periodUnit": "d", "timeOfDay": ["08:00:00"]})),
     "Doppelte Belegung der Uhrzeit '08:00 Uhr' mit unterschiedlicher Dosis."),
    ("Duplikat Intervall-Kombination, Tagesabschnitt",
     req(d(dq(1), {"period": 2, "periodUnit": "d", "when": ["MORN"]}),
         d(dq(2), {"period": 2, "periodUnit": "d", "when": ["MORN"]})),
     "Doppelte Belegung des Tagesabschnitts 'MORN' mit unterschiedlicher Dosis."),
    ("unbekannte modifierExtension",
     req(d(dq(1), {"when": ["MORN"]}, modifierExtension=[{"url": "http://example.org/x", "valueBoolean": True}])),
     "Nicht unterstützte modifierExtension: 'http://example.org/x'."),
    ("comparator", req(d([{"doseQuantity": {"value": 2, "unit": "Stück", "comparator": "<"}}], {"when": ["MORN"]})),
     "doseQuantity.comparator wird nicht unterstützt."),
    ("comparator Maximalmenge",
     req(d(dq(1), asNeededBoolean=True,
           maxDosePerPeriod={"numerator": {"value": 6, "unit": "Stück", "comparator": "<"},
                             "denominator": {"value": 1, "code": "d"}})),
     "maxDosePerPeriod.numerator.comparator wird nicht unterstützt."),
    ("Duplikat Uhrzeit", req(d(dq(1), {"timeOfDay": ["08:00:00"]}), d(dq(2), {"timeOfDay": ["08:00:00"]})),
     "Doppelte Belegung der Uhrzeit '08:00 Uhr' mit unterschiedlicher Dosis."),
    ("Wochentags-Kombination gemischt",
     req(d(dq(1), {"dayOfWeek": ["mon"], "timeOfDay": ["08:00:00"]}), d(dq(2), {"dayOfWeek": ["wed"], "when": ["MORN"]})),
     "Wochentags-Kombinationen mit Uhrzeiten und mit Tagesabschnitten dürfen nicht gemischt werden."),
    ("Intervall, zwei Elemente", req(d(dq(1), EVERY_8_H), d(dq(2), {**EVERY_8_H, "period": 12})),
     "Wiederkehrende Intervalle erlauben genau ein Dosage-Element."),
    ("Anlass ohne Bedarf", req(d(dq(1), EVERY_8_H, extension=reason("Kopfschmerzen"))),
     "Ein Einnahmeanlass (asNeededFor) setzt asNeededBoolean = true voraus."),
    ("Mindestabstand ohne Bedarf", req(d(dq(1), EVERY_8_H, modifierExtension=min_interval(4, "h"))),
     "Ein Mindestabstand setzt asNeededBoolean = true voraus."),
    ("Maximalmenge ohne Bedarf", req(d(dq(1), EVERY_8_H, maxDosePerPeriod=max_dose(4, 1, "d"))),
     "Eine Maximalmenge setzt asNeededBoolean = true voraus."),
    ("Zeiteinheit", req(d(dq(1), {**EVERY_8_H, "periodUnit": "x"})), "Nicht unterstützte Zeiteinheit: 'x'."),
    ("Zeiteinheit boundsDuration", req(d(dq(1), {"when": ["MORN"], "boundsDuration": {"value": 7, "code": "x"}})),
     "Nicht unterstützte Zeiteinheit: 'x'."),
    ("Anlass ohne Bedarf in Element 2",
     req(d(dq(1), {"when": ["MORN"]}), d(dq(2), {"when": ["EVE"]}, extension=reason("Kopfschmerzen"))),
     "Ein Einnahmeanlass (asNeededFor) setzt asNeededBoolean = true voraus."),
    ("Mindestabstand mit Rhythmus in Element 2",
     req(d(dq(1), {"when": ["MORN"]}, asNeededBoolean=True),
         d(dq(2), {"when": ["EVE"]}, asNeededBoolean=True, modifierExtension=min_interval(4, "h"))),
     "Ein Mindestabstand ist nur bei reiner Bedarfsmedikation zulässig, nicht zusammen mit einem strukturierten Rhythmus."),
    ("Maximalmenge ohne Bedarf in Element 2",
     req(d(dq(1), {"when": ["MORN"]}), d(dq(2), {"when": ["EVE"]}, maxDosePerPeriod=max_dose(4, 1, "d"))),
     "Eine Maximalmenge setzt asNeededBoolean = true voraus."),
    ("Mindestabstand ohne Bedarf und ohne timing", req(d(dq(1), modifierExtension=min_interval(4, "h"))),
     "Ein Mindestabstand setzt asNeededBoolean = true voraus."),
    ("Mindestabstand an Freitext",
     req({"text": "Bei Kopfschmerzen 1 Stück", "asNeededBoolean": True, "modifierExtension": min_interval(4, "h")}),
     "Ein Mindestabstand ist bei einer Freitext-Dosierung nicht darstellbar."),
    ("Maximalmenge an Freitext",
     req({"text": "Bei Kopfschmerzen 1 Stück", "asNeededBoolean": True, "maxDosePerPeriod": max_dose(6, 1, "d")}),
     "Eine Maximalmenge ist bei einer Freitext-Dosierung nicht darstellbar."),
    ("Einheit aus Leerraum", req(d(dq(1, "  "), {"when": ["MORN"]})),
     "doseQuantity.unit ist für die Textgenerierung erforderlich."),
)


def spec_error_templates():
    """Alle Meldungen aus dem Abschnitt "Fehler und Validierung"."""
    text = SPEC_PATH.read_text(encoding="utf-8")
    section = text.split("## Fehler und Validierung", 1)[1].split("\n## ", 1)[0]
    return re.findall(r'ValueError\("(.*?)"\)', section)


def template_pattern(template):
    """{platzhalter} und <Platzhalter> stehen für beliebigen Text."""
    parts = re.split(r"(\{[^}]+\}|<[^>]+>)", template)
    return re.compile("".join(".+?" if re.fullmatch(r"\{[^}]+\}|<[^>]+>", part) else re.escape(part)
                              for part in parts) + r"\Z")


class SpecExamplesTest(unittest.TestCase):
    def test_every_spec_example_is_generated_exactly(self):
        generator = GENERATOR()
        for name, resource, expected in EXAMPLES:
            with self.subTest(name):
                self.assertEqual(generator.generate_dosage_text(resource), expected)


DAYS = "montags|dienstags|mittwochs|donnerstags|freitags|samstags|sonntags"
# Vollstaendiger Text: beginnt wie ein erzeugter Text und enthaelt den Doppelpunkt
# oder ein Wochentagssegment.
COMPLETE_TEXT = re.compile(
    rf"^(täglich: |wöchentlich: |monatlich: |alle .+: |bei .+: |für .+: |ab dem .+: |vom .+: "
    rf"|bis zum .+: |\d+( bis \d+)? x .+: |({DAYS}) )")
# Baustein: beginnt wie ein Teil eines erzeugten Textes.
TEXT_FRAGMENT = re.compile(
    r"^(je |morgens|mittags|abends|zur Nacht|\d\d:\d\d Uhr|täglich$|wöchentlich$|monatlich$|alle |bei "
    r"|für |ab dem |vom |bis zum |\d+( bis \d+)? x |im Abstand|nicht mehr als|in 24|pro Tag|Hinweis:)")


def spec_text_examples():
    """Inline-Code im Fliesstext der Spezifikation, der wie ein erzeugter Text
    aussieht; Codebloecke (Muster, Pseudocode) und Platzhalter bleiben aussen vor."""
    body = re.sub(r"```.*?```", "", SPEC_PATH.read_text(encoding="utf-8"), flags=re.S)
    spans = {span for span in re.findall(r"`([^`\n]+)`", body)
             if not re.search(r"[{}<>\[\]…=_]|ValueError|\.\.\.|^\w+\.\w+", span)}
    complete = {span for span in spans if COMPLETE_TEXT.match(span) and (" — " in span or ": " in span)}
    fragments = {span for span in spans - complete if TEXT_FRAGMENT.match(span)}
    return complete, fragments


class SpecTextExamplesTest(unittest.TestCase):
    def test_every_spec_text_example_is_generated(self):
        complete, fragments = spec_text_examples()
        outputs = [expected for _, _, expected in EXAMPLES]
        self.assertGreater(len(complete), 20)
        for text in sorted(complete):
            with self.subTest(text):
                self.assertIn(text, outputs, f"Kein Testfall erzeugt das Beispiel: {text}")
        for text in sorted(fragments):
            with self.subTest(text):
                self.assertTrue(any(text in output for output in outputs),
                                f"Baustein in keiner erwarteten Ausgabe: {text}")


class ErrorListTest(unittest.TestCase):
    def test_every_case_raises_its_exact_message(self):
        generator = GENERATOR()
        for name, resource, expected in ERROR_CASES:
            with self.subTest(name):
                with self.assertRaises(ValueError) as caught:
                    generator.generate_dosage_text(resource)
                self.assertEqual(str(caught.exception), expected)

    def test_every_case_message_is_listed_in_the_spec(self):
        patterns = [template_pattern(template) for template in spec_error_templates()]
        for name, _, expected in ERROR_CASES:
            with self.subTest(name):
                self.assertTrue(any(pattern.match(expected) for pattern in patterns),
                                f"Meldung fehlt in der Fehlerliste: {expected}")

    def test_every_spec_message_is_produced_by_a_case(self):
        messages = [expected for _, _, expected in ERROR_CASES]
        for template in spec_error_templates():
            with self.subTest(template):
                pattern = template_pattern(template)
                self.assertTrue(any(pattern.match(message) for message in messages),
                                f"Kein Fall erzeugt diese Meldung: {template}")


if __name__ == "__main__":
    unittest.main()
