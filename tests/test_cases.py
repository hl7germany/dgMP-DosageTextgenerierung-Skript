#!/usr/bin/env python3
"""Testvektoren aus tests/cases/ gegen das Skript.

Die Vektoren sind sprachneutral (JSON) und für jede Implementierung des
Algorithmus gedacht; das Format beschreibt tests/cases/README.md. Dieser Test
ist der Runner für das Python-Skript:

- Ein Fall mit `dosages` läuft für MedicationRequest, MedicationDispense und
  MedicationStatement; die Liste steht dabei unter `dosageInstruction`
  beziehungsweise `dosage`.
- Ein Fall mit `resource` läuft genau mit dieser Ressource.
- `expect.text` muss zeichengenau erzeugt werden; bei `expect.error` muss
  das Skript abbrechen.

Den Wortlaut einer Meldung legt die Spezifikation nicht fest. Die Meldungen des
Skripts stehen je Fall in tests/script-messages.json und werden hier mitgeprüft.
"""

import importlib.util
import json
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = Path(__file__).resolve().parent / "cases"
MESSAGES_PATH = Path(__file__).resolve().parent / "script-messages.json"
SPEC = importlib.util.spec_from_file_location(
    "medication_dosage_to_text", ROOT / "medication-dosage-to-text.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

DOSAGE_FIELD = {
    "MedicationRequest": "dosageInstruction",
    "MedicationDispense": "dosageInstruction",
    "MedicationStatement": "dosage",
}


def load_files():
    files = {}
    for path in sorted(CASES_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as file:
            # parse_float=Decimal wie in der Kommandozeile des Skripts: 2.50
            # bleibt 2.50.
            files[path.name] = json.load(file, parse_float=Decimal)
    return files


def load_messages():
    with open(MESSAGES_PATH, encoding="utf-8") as file:
        return json.load(file)


def resources(case):
    if "resource" in case:
        yield case["resource"]
        return
    for resource_type, field in DOSAGE_FIELD.items():
        yield {"resourceType": resource_type, field: case["dosages"]}


class CaseFilesTest(unittest.TestCase):
    """Form der Dateien, damit ein Fall nicht unbemerkt übersprungen wird."""

    def test_files_are_well_formed(self):
        files = load_files()
        self.assertTrue(files, "tests/cases enthält keine Testvektoren.")
        names = set()
        for file_name, content in files.items():
            with self.subTest(file=file_name):
                self.assertEqual(set(content), {"section", "cases"})
                self.assertIsInstance(content["section"], str)
                self.assertTrue(content["cases"])
            for case in content["cases"]:
                with self.subTest(file=file_name, name=case.get("name")):
                    self.assertIn(set(case), [{"name", "dosages", "expect"}, {"name", "resource", "expect"}])
                    self.assertNotIn(case["name"], names, "Name ist nicht eindeutig.")
                    names.add(case["name"])
                    if "dosages" in case:
                        self.assertIsInstance(case["dosages"], list)
                    else:
                        self.assertIsInstance(case["resource"], dict)
                    self.assertIn(set(case["expect"]), [{"text"}, {"error"}])
                    if "text" in case["expect"]:
                        self.assertIsInstance(case["expect"]["text"], str)
                    else:
                        self.assertIs(case["expect"]["error"], True)

    def test_every_error_case_has_exactly_one_script_message(self):
        error_cases = [case["name"] for content in load_files().values()
                       for case in content["cases"] if "error" in case["expect"]]
        messages = load_messages()
        self.assertEqual(sorted(error_cases), sorted(messages),
                         "tests/script-messages.json muss genau die Fälle mit expect.error enthalten.")
        for name, message in messages.items():
            with self.subTest(name=name):
                self.assertIsInstance(message, str)

    def test_inputs_are_unique(self):
        seen = {}
        for file_name, content in load_files().items():
            for case in content["cases"]:
                kind = "dosages" if "dosages" in case else "resource"
                key = (kind, json.dumps(case[kind], default=str, sort_keys=True))
                with self.subTest(file=file_name, name=case["name"]):
                    self.assertNotIn(key, seen, "Dieselbe Eingabe steht bereits in einem anderen Fall.")
                seen[key] = case["name"]


class CasesTest(unittest.TestCase):
    def test_every_case_produces_its_expected_result(self):
        generator = MODULE.MedicationDosageTextGenerator()
        messages = load_messages()
        for file_name, content in load_files().items():
            for case in content["cases"]:
                expect = case["expect"]
                for resource in resources(case):
                    with self.subTest(
                        file=file_name, name=case["name"], resource_type=resource.get("resourceType")
                    ):
                        if "error" in expect:
                            with self.assertRaises(ValueError) as raised:
                                generator.generate_dosage_text(resource)
                            self.assertEqual(messages.get(case["name"]), str(raised.exception))
                        else:
                            self.assertEqual(expect["text"], generator.generate_dosage_text(resource))


if __name__ == "__main__":
    unittest.main()
