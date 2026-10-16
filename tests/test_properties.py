#!/usr/bin/env python3
"""Eigenschaften, die fuer jede Eingabe gelten, geprueft ueber Zufallsressourcen.

Der Generator erzeugt profilnahe Ressourcen ueber alle Schemata hinweg und
streut gezielt Verstoesse ein (falsche Typen, fehlende Angaben, unbekannte
Codes, Duplikate). Der Seed ist fest; ein Fehlschlag ist damit reproduzierbar
und nennt die Ressource.

- Abbruch nur mit ValueError, nie mit einem anderen Laufzeitfehler.
- Ein strukturiert erzeugter Text steht in einer Zeile, ohne Leerraum am Rand,
  und beginnt nicht mit einem Grossbuchstaben (Grundsaetze der Spezifikation).
- Die Reihenfolge der Dosage-Elemente aendert das Ergebnis nicht, sofern die
  Rahmen-Angaben in allen Elementen gleich sind.
- Fuer Zahlen ohne nachfolgende Nullen liefern Decimal- und float-Parser
  denselben Text.
"""

import copy
import importlib.util
import itertools
import json
import random
import unittest
from decimal import Decimal
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "medication-dosage-to-text.py"
SPEC = importlib.util.spec_from_file_location("medication_dosage_to_text", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
GENERATOR = MODULE.MedicationDosageTextGenerator

SEED = 20261016
RESOURCES = 1500

WHEN = ["MORN", "NOON", "EVE", "NIGHT"]
TIMES = ["06:00", "08:00:00", "12:00:00", "13:30", "20:00:00", "22:00:00.5"]
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
UNITS = ["Stück", "Tbl.", "Messlöffel", "mg"]
VALUES = [Decimal("0.5"), Decimal("1"), Decimal("1.5"), Decimal("2"), Decimal("0.25"), Decimal("0")]


class ResourceFactory:
    def __init__(self, rng):
        self.rng = rng

    def pick(self, options):
        return self.rng.choice(options)

    def dose(self):
        unit = self.pick(UNITS)
        if self.rng.random() < 0.2:
            low, high = sorted(self.rng.sample(VALUES[:5], 2))
            return [{"doseRange": {"low": {"value": low, "unit": unit}, "high": {"value": high, "unit": unit}}}]
        return [{"doseQuantity": {"value": self.pick(VALUES), "unit": unit}}]

    def frame(self):
        """Rahmen-Angaben, die in allen Elementen gleich sind."""
        frame, repeat = {}, {}
        roll = self.rng.random()
        if roll < 0.2:
            repeat["boundsDuration"] = {"value": self.pick([1, 7, 14]), "code": self.pick(["d", "wk", "mo"])}
        elif roll < 0.3:
            repeat["boundsPeriod"] = {"start": "2026-06-05"}
        if self.rng.random() < 0.2:
            frame["patientInstruction"] = self.pick(["Nach dem Essen", "Mit Wasser."])
        return frame, repeat

    def element(self, kind, shared_repeat):
        repeat = dict(shared_repeat)
        if kind == "when":
            repeat["when"] = self.rng.sample(WHEN, self.rng.randint(1, 2))
        elif kind == "time":
            repeat["timeOfDay"] = sorted(self.rng.sample(TIMES, self.rng.randint(1, 2)))
        elif kind == "day":
            repeat["dayOfWeek"] = self.rng.sample(DAYS, self.rng.randint(1, 2))
        elif kind == "day_when":
            repeat.update(dayOfWeek=self.rng.sample(DAYS, 1), when=self.rng.sample(WHEN, self.rng.randint(1, 2)))
        elif kind == "day_time":
            repeat.update(dayOfWeek=self.rng.sample(DAYS, 1), timeOfDay=self.rng.sample(TIMES, 1))
        elif kind == "interval_when":
            repeat.update(period=shared_repeat["period"], periodUnit=shared_repeat["periodUnit"],
                          when=self.rng.sample(WHEN, 1))
        elif kind == "interval_time":
            repeat.update(period=shared_repeat["period"], periodUnit=shared_repeat["periodUnit"],
                          timeOfDay=self.rng.sample(TIMES, 1))
        return {"timing": {"repeat": repeat}, "doseAndRate": self.dose()}

    def resource(self):
        frame, shared_repeat = self.frame()
        kind = self.pick(["when", "time", "day", "day_when", "day_time", "interval", "interval_when",
                          "interval_time", "as_needed", "free_text"])
        as_needed = kind == "as_needed" or self.rng.random() < 0.2
        if kind in ("interval", "interval_when", "interval_time"):
            shared_repeat.update(period=self.pick([2, 3, 1]), periodUnit=self.pick(["d", "wk", "mo", "h"]))
        if kind == "free_text":
            elements = [{"text": self.pick(["1 Tablette morgens", "  nach Rücksprache  "])}]
        elif kind == "as_needed":
            elements = [{"doseAndRate": self.dose()}]
        elif kind == "interval":
            elements = [{"timing": {"repeat": {**shared_repeat, "frequency": self.pick([1, 2])}},
                         "doseAndRate": self.dose()}]
        else:
            elements = [self.element(kind, shared_repeat) for _ in range(self.rng.randint(1, 3))]
        for element in elements:
            element.update(copy.deepcopy(frame))
            if as_needed:
                element["asNeededBoolean"] = True
                if kind == "as_needed" and self.rng.random() < 0.3:
                    element["modifierExtension"] = [{"url": GENERATOR.URL_MINDESTABSTAND,
                                                     "valueDuration": {"value": 4, "code": "h"}}]
        self.disturb(elements)
        return {"resourceType": "MedicationRequest", "dosageInstruction": elements}

    def disturb(self, elements):
        """Streut mit geringer Wahrscheinlichkeit einen Verstoss ein."""
        if self.rng.random() > 0.3:
            return
        target = self.pick(elements)
        repeat = target.get("timing", {}).get("repeat")
        disturbances = [
            lambda: target.pop("doseAndRate", None),
            lambda: target.update(doseAndRate=[{"doseQuantity": {"value": "1", "unit": "Stück"}}]),
            lambda: target.update(doseAndRate=[{"doseQuantity": {"value": Decimal("-1"), "unit": "Stück"}}]),
            lambda: target.update(doseAndRate=[{"doseQuantity": {"value": 1, "unit": "  "}}]),
            lambda: target.update(asNeededBoolean="true"),
            lambda: target.update(modifierExtension=[{"url": "http://example.org/x"}]),
            lambda: target.update(maxDosePerPeriod={"numerator": {"value": 4, "unit": "Stück"},
                                                    "denominator": {"value": 1, "code": "d"}}),
        ]
        if repeat is not None:
            disturbances += [
                lambda: repeat.update(when=["XYZ"]),
                lambda: repeat.update(timeOfDay=["8:00"]),
                lambda: repeat.update(dayOfWeek=["xyz"]),
                lambda: repeat.update(period="1"),
                lambda: repeat.update(frequencyMax=3),
                lambda: repeat.update(periodUnit="x"),
            ]
            # Rahmen-Angabe: in allen Elementen gleich, sonst gilt die Eigenschaft
            # "Reihenfolge egal" nicht (sie wird nur aus dem ersten Element gelesen).
            disturbances.append(lambda: [element["timing"]["repeat"].update(boundsPeriod={"start": "2026-02-30"})
                                         for element in elements if "timing" in element])
        self.pick(disturbances)()


def render(resource):
    try:
        return ("text", GENERATOR().generate_dosage_text(resource))
    except ValueError as error:
        return ("abbruch", str(error))


def corpus():
    factory = ResourceFactory(random.Random(SEED))
    return [factory.resource() for _ in range(RESOURCES)]


def is_free_text(resource):
    return all("text" in element and "timing" not in element and "doseAndRate" not in element
               for element in resource["dosageInstruction"])


class PropertyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = corpus()
        cls.results = [render(copy.deepcopy(resource)) for resource in cls.corpus]

    def test_corpus_reaches_both_outcomes(self):
        kinds = {kind for kind, _ in self.results}
        self.assertEqual(kinds, {"text", "abbruch"})

    def test_only_value_error_is_raised(self):
        # render() faengt nur ValueError; jede andere Exception laesst den Test scheitern.
        for resource, (kind, _) in zip(self.corpus, self.results):
            self.assertIn(kind, ("text", "abbruch"), json.dumps(resource, default=str))

    def test_structured_text_shape(self):
        for resource, (kind, text) in zip(self.corpus, self.results):
            if kind != "text" or is_free_text(resource):
                continue
            with self.subTest(resource=json.dumps(resource, default=str, ensure_ascii=False)):
                self.assertTrue(text)
                self.assertNotIn("\n", text)
                self.assertEqual(text, text.strip())
                self.assertFalse(text[0].isupper(), text)

    def test_order_of_dosage_elements_does_not_matter(self):
        for resource, (kind, text) in zip(self.corpus, self.results):
            elements = resource["dosageInstruction"]
            if len(elements) < 2:
                continue
            for order in itertools.permutations(elements):
                permuted = {**resource, "dosageInstruction": copy.deepcopy(list(order))}
                other_kind, other_text = render(permuted)
                with self.subTest(resource=json.dumps(resource, default=str, ensure_ascii=False)):
                    self.assertEqual(other_kind, kind)
                    if kind == "text":
                        self.assertEqual(other_text, text)

    def test_decimal_and_float_parser_agree(self):
        # Die Werte des Generators haben keine nachfolgenden Nullen; dann darf der
        # Parser keinen Unterschied machen.
        for resource in self.corpus:
            as_json = json.dumps(as_json_numbers(resource), ensure_ascii=False)
            with self.subTest(resource=as_json):
                self.assertEqual(render(json.loads(as_json)), render(json.loads(as_json, parse_float=Decimal)))


def as_json_numbers(value):
    """Decimal so ersetzen, wie es im JSON-Text stuende: ganze Zahl oder float."""
    if isinstance(value, Decimal):
        return int(value) if "." not in str(value) else float(value)
    if isinstance(value, dict):
        return {key: as_json_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [as_json_numbers(item) for item in value]
    return value


if __name__ == "__main__":
    unittest.main()
