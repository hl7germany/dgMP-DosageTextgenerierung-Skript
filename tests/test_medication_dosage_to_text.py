#!/usr/bin/env python3
"""Tests, die die Testvektoren in tests/cases/ nicht abdecken können.

Was nur die Textgenerierung mit einer Eingabe aufruft, gehört als Vektor nach
tests/cases/ (Runner: test_cases.py). Hier stehen die Kommandozeile, die
Versionsangabe und Eingaben, die JSON nicht darstellen kann.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "medication-dosage-to-text.py"
SPEC_PATH = Path(__file__).resolve().parents[1] / "dosage-text-algorithm-spec.md"
SPEC = importlib.util.spec_from_file_location("medication_dosage_to_text", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class VersionTest(unittest.TestCase):
    def test_algorithm_version_matches_spec(self):
        """__version__ wird als algorithmVersion in jede Ressource geschrieben.

        Der Wert muss mit der Versionsangabe der Spezifikation uebereinstimmen;
        beim Tag-Push prueft die CI zusaetzlich gegen den Tag.
        """
        spec = SPEC_PATH.read_text(encoding="utf-8")
        self.assertIn(f"Algorithmus-Version **{MODULE.__version__}**", spec)


class NonFiniteNumberTest(unittest.TestCase):
    """NaN und Infinity gelten nicht als Zahl. Pythons JSON-Parser nimmt beide
    an (auch die Kommandozeile), JSON selbst kann sie nicht darstellen."""

    def setUp(self):
        self.generator = MODULE.MedicationDosageTextGenerator()

    @staticmethod
    def request(dose, repeat):
        return {"resourceType": "MedicationRequest", "dosageInstruction": [{
            "timing": {"repeat": repeat},
            "doseAndRate": [{"doseQuantity": {"value": dose, "unit": "Stück"}}],
        }]}

    def test_nan_dose_is_not_numeric(self):
        with self.assertRaises(ValueError) as raised:
            self.generator.generate_dosage_text(self.request(float("nan"), {"when": ["MORN"]}))
        self.assertEqual(str(raised.exception), "doseQuantity.value muss numerisch sein.")

    def test_infinite_period_is_not_numeric(self):
        repeat = {"frequency": 1, "period": Decimal("Infinity"), "periodUnit": "h"}
        with self.assertRaises(ValueError) as raised:
            self.generator.generate_dosage_text(self.request(1, repeat))
        self.assertEqual(str(raised.exception), "timing.repeat.period muss numerisch sein.")


class CommandLineTest(unittest.TestCase):
    """Die Kommandozeile ist die Schnittstelle, ueber die der IG-Build das Skript
    aufruft: Text auf stdout und Exit-Code 0, sonst "Fehler: ..." auf stderr und
    Exit-Code 1."""

    def run_cli(self, *args, content=None):
        path = None
        if content is not None:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
                handle.write(content)
                path = handle.name
            args = (path,)
        try:
            return subprocess.run([sys.executable, str(MODULE_PATH), *args],
                                  capture_output=True, text=True, encoding="utf-8")
        finally:
            if path:
                os.unlink(path)

    def test_without_argument_prints_usage(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Verwendung:", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_missing_file(self):
        result = self.run_cli("/nicht/vorhanden.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Fehler: Datei '/nicht/vorhanden.json' nicht gefunden.", result.stderr)

    def test_invalid_json(self):
        result = self.run_cli(content="{kein json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Fehler: Ungültiges JSON", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_abort_is_reported_with_message(self):
        resource = {"resourceType": "MedicationRequest", "dosageInstruction": [
            {"timing": {"repeat": {"when": ["MORN"]}}}]}
        result = self.run_cli(content=json.dumps(resource))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr.strip(), "Fehler: doseAndRate ist für die Textgenerierung erforderlich.")
        self.assertEqual(result.stdout, "")

    def test_cli_reads_json_with_decimal_precision(self):
        """Die CLI liest mit parse_float=Decimal; 2.50 bleibt 2,50."""
        resource = {
            "resourceType": "MedicationRequest",
            "dosageInstruction": [{
                "timing": {"repeat": {"frequency": 1, "period": 8, "periodUnit": "h"}},
                "doseAndRate": [{"doseQuantity": {"value": 2.50, "unit": "mg"}}],
            }],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            # Literal mit nachfolgender Null schreiben; json.dump(2.50) ergaebe 2.5.
            handle.write(json.dumps(resource).replace("2.5", "2.50"))
            path = handle.name
        try:
            result = subprocess.run(
                [sys.executable, str(MODULE_PATH), path],
                capture_output=True, text=True, check=True,
            )
        finally:
            os.unlink(path)
        self.assertEqual(result.stdout.strip(), "alle 8 Stunden: je 2,50 mg")


if __name__ == "__main__":
    unittest.main()
