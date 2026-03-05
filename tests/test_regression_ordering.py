import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "medication-dosage-to-text.py"
SPEC = spec_from_file_location("medication_dosage_to_text", MODULE_PATH)
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RegressionOrderingTest(unittest.TestCase):
    def setUp(self):
        self.generator = MODULE.MedicationDosageTextGenerator()

    def _resource(self, dosage_instructions):
        return {
            "resourceType": "MedicationRequest",
            "dosageInstruction": dosage_instructions,
        }

    def test_day_time_combo_is_order_independent(self):
        dosage_a = {
            "timing": {
                "repeat": {
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "d",
                    "dayOfWeek": ["mon"],
                    "timeOfDay": ["20:00"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stueck"}}],
        }
        dosage_b = {
            "timing": {
                "repeat": {
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "d",
                    "dayOfWeek": ["mon"],
                    "timeOfDay": ["08:00"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stueck"}}],
        }

        output_1 = self.generator.generate_dosage_text(self._resource([dosage_a, dosage_b]))
        output_2 = self.generator.generate_dosage_text(self._resource([dosage_b, dosage_a]))

        self.assertEqual(output_1, output_2)
        self.assertIn("08:00 Uhr", output_1)
        self.assertIn("20:00 Uhr", output_1)

    def test_day_time_combo_duplicate_slot_is_not_summed(self):
        dosage_a = {
            "timing": {
                "repeat": {
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "d",
                    "dayOfWeek": ["mon"],
                    "timeOfDay": ["08:00"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stueck"}}],
        }
        dosage_b = {
            "timing": {
                "repeat": {
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "d",
                    "dayOfWeek": ["mon"],
                    "timeOfDay": ["08:00"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stueck"}}],
        }

        output = self.generator.generate_dosage_text(self._resource([dosage_a, dosage_b]))

        self.assertNotIn("je 3", output)
        self.assertIn("je 1 Stueck", output)
        self.assertIn("je 2 Stueck", output)

    def test_day_when_combo_is_order_independent_and_not_summed(self):
        dosage_a = {
            "timing": {
                "repeat": {
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "d",
                    "dayOfWeek": ["mon"],
                    "when": ["MORN"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stueck"}}],
        }
        dosage_b = {
            "timing": {
                "repeat": {
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "d",
                    "dayOfWeek": ["mon"],
                    "when": ["MORN"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stueck"}}],
        }

        output_1 = self.generator.generate_dosage_text(self._resource([dosage_a, dosage_b]))
        output_2 = self.generator.generate_dosage_text(self._resource([dosage_b, dosage_a]))

        self.assertEqual(output_1, output_2)
        self.assertNotIn("3-0-0-0", output_1)
        self.assertIn("montags 1-0-0-0 Stueck", output_1)
        self.assertIn("montags 2-0-0-0 Stueck", output_1)
        self.assertIn("montags 1-0-0-0 Stueck; montags 2-0-0-0 Stueck", output_1)

    def test_time_of_day_schema_is_order_independent(self):
        dosage_a = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d", "timeOfDay": ["20:00"]}},
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stueck"}}],
        }
        dosage_b = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d", "timeOfDay": ["08:00"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stueck"}}],
        }

        output_1 = self.generator.generate_dosage_text(self._resource([dosage_a, dosage_b]))
        output_2 = self.generator.generate_dosage_text(self._resource([dosage_b, dosage_a]))

        self.assertEqual(output_1, output_2)
        self.assertIn("täglich: 08:00 Uhr — je 1 Stueck; 20:00 Uhr — je 2 Stueck", output_1)

    def test_interval_time_schema_keeps_duplicates_separate(self):
        dosage_a = {
            "timing": {"repeat": {"frequency": 1, "period": 2, "periodUnit": "d", "timeOfDay": ["08:00"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stueck"}}],
        }
        dosage_b = {
            "timing": {"repeat": {"frequency": 1, "period": 2, "periodUnit": "d", "timeOfDay": ["18:00"]}},
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stueck"}}],
        }
        dosage_c = {
            "timing": {"repeat": {"frequency": 1, "period": 2, "periodUnit": "d", "timeOfDay": ["08:00"]}},
            "doseAndRate": [{"doseQuantity": {"value": 3, "unit": "Stueck"}}],
        }

        output_1 = self.generator.generate_dosage_text(self._resource([dosage_a, dosage_b, dosage_c]))
        output_2 = self.generator.generate_dosage_text(self._resource([dosage_c, dosage_b, dosage_a]))

        self.assertEqual(output_1, output_2)
        self.assertNotIn("je 4 Stueck", output_1)
        self.assertIn("alle 2 Tage: 08:00 Uhr — je 1 Stueck; 08:00 Uhr — je 3 Stueck; 18:00 Uhr — je 2 Stueck", output_1)

    def test_4_schema_duplicate_when_raises_value_error(self):
        dosage_a = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d", "when": ["MORN"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stueck"}}],
        }
        dosage_b = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d", "when": ["MORN"]}},
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stueck"}}],
        }

        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text(self._resource([dosage_a, dosage_b]))

    def test_interval_time_schema_without_valid_time_keys_returns_interval_only(self):
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 2, "periodUnit": "d", "when": ["XYZ"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stueck"}}],
        }

        output = self.generator.generate_dosage_text(self._resource([dosage]))
        self.assertEqual("alle 2 Tage", output)


if __name__ == "__main__":
    unittest.main()
