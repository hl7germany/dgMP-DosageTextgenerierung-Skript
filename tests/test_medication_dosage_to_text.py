#!/usr/bin/env python3

import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("medication-dosage-to-text.py")
SPEC = importlib.util.spec_from_file_location("medication_dosage_to_text", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MedicationDosageTextTest(unittest.TestCase):
    def setUp(self):
        self.generator = MODULE.MedicationDosageTextGenerator()

    @staticmethod
    def medication_request(*dosages):
        return {
            "resourceType": "MedicationRequest",
            "dosageInstruction": list(dosages),
        }

    @staticmethod
    def medication_dispense(*dosages):
        return {
            "resourceType": "MedicationDispense",
            "dosageInstruction": list(dosages),
        }

    @staticmethod
    def medication_statement(*dosages):
        return {
            "resourceType": "MedicationStatement",
            "dosage": list(dosages),
        }

    @staticmethod
    def dosage(dose, repeat):
        return {
            "timing": {"repeat": repeat},
            "doseAndRate": [{"doseQuantity": {"value": dose, "unit": "Stück"}}],
        }

    def test_interval_time_combination_omits_present_frequency(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "frequency": 2,
                    "period": 2,
                    "periodUnit": "d",
                    "timeOfDay": ["08:00:00", "20:00:00"],
                },
            ),
            self.dosage(
                2,
                {
                    "frequency": 3,
                    "period": 2,
                    "periodUnit": "d",
                    "timeOfDay": ["10:00:00", "14:00:00", "22:00:00"],
                },
            ),
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "alle 2 Tage: 08:00 Uhr — je 1 Stück, "
            "10:00 Uhr — je 2 Stück, 14:00 Uhr — je 2 Stück, "
            "20:00 Uhr — je 1 Stück, 22:00 Uhr — je 2 Stück",
        )

    def test_interval_time_combination_does_not_require_frequency(self):
        resource = self.medication_request(
            self.dosage(
                2,
                {
                    "period": 2,
                    "periodUnit": "d",
                    "timeOfDay": ["10:00:00", "14:00:00", "22:00:00"],
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "alle 2 Tage: 10:00 Uhr — je 2 Stück, "
            "14:00 Uhr — je 2 Stück, 22:00 Uhr — je 2 Stück",
        )

    def test_interval_when_combination_is_not_treated_as_daily_4_schema(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "period": 2,
                    "periodUnit": "d",
                    "when": ["MORN", "EVE"],
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "alle 2 Tage: morgens — je 1 Stück, abends — je 1 Stück",
        )

    def test_every_second_day_morning_regression(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "frequency": 1,
                    "period": 2,
                    "periodUnit": "d",
                    "when": ["MORN"],
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "alle 2 Tage: morgens — je 1 Stück",
        )

    def test_time_of_day_without_period_remains_daily(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "frequency": 2,
                    "timeOfDay": ["08:00:00", "20:00:00"],
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "täglich: 08:00 Uhr, 20:00 Uhr — je 1 Stück",
        )

    def test_pure_interval_keeps_frequency_output_for_follow_up_change(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "frequency": 2,
                    "period": 8,
                    "periodUnit": "h",
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "2 x alle 8 Stunden: je 1 Stück",
        )

    def test_monthly_interval_uses_natural_short_form(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "mo",
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "monatlich: je 1 Stück",
        )

    def test_structured_as_needed_places_minimum_interval_after_core(self):
        dosage = self.dosage(
            1,
            {
                "frequency": 1,
                "period": 8,
                "periodUnit": "h",
            },
        )
        dosage["asNeededBoolean"] = True
        dosage["extension"] = [{
            "url": self.generator.URL_AS_NEEDED_FOR,
            "valueCodeableConcept": {"text": "Kopfschmerzen"},
        }]
        dosage["modifierExtension"] = [{
            "url": self.generator.URL_MINDESTABSTAND,
            "valueDuration": {"value": 6, "code": "h", "unit": "Stunde(n)"},
        }]
        dosage["maxDosePerPeriod"] = {
            "numerator": {"value": 4, "unit": "Stück"},
            "denominator": {"value": 24, "code": "h"},
        }

        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(dosage)
            ),
            "Bei Kopfschmerzen: alle 8 Stunden je 1 Stück, "
            "mit mindestens 6 Stunden Abstand — "
            "nicht mehr als 4 Stück in 24 Stunden",
        )

    def test_free_text_is_returned_unchanged(self):
        resource = self.medication_request({
            "text": "Nach dem Essen — 2 Stück täglich",
        })

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "Nach dem Essen — 2 Stück täglich",
        )

    def test_daily_four_schema_aggregates_different_doses(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "d",
                    "when": ["MORN"],
                },
            ),
            self.dosage(
                2,
                {
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "d",
                    "when": ["EVE"],
                },
            ),
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "1-0-2-0 Stück",
        )

    def test_day_of_week_schema_uses_canonical_order(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "frequency": 2,
                    "period": 1,
                    "periodUnit": "wk",
                    "dayOfWeek": ["wed", "mon"],
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "montags — je 1 Stück; mittwochs — je 1 Stück",
        )

    def test_day_of_week_time_combination_sorts_days_and_times(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "frequency": 4,
                    "period": 1,
                    "periodUnit": "wk",
                    "dayOfWeek": ["fri", "mon"],
                    "timeOfDay": ["20:00:00", "08:00:00"],
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "montags 08:00 Uhr, 20:00 Uhr — je 1 Stück; "
            "freitags 08:00 Uhr, 20:00 Uhr — je 1 Stück",
        )

    def test_pure_as_needed_includes_reason_minimum_and_maximum(self):
        dosage = {
            "asNeededBoolean": True,
            "extension": [{
                "url": self.generator.URL_AS_NEEDED_FOR,
                "valueCodeableConcept": {"text": "Kopfschmerzen"},
            }],
            "modifierExtension": [{
                "url": self.generator.URL_MINDESTABSTAND,
                "valueDuration": {
                    "value": 4,
                    "code": "h",
                    "unit": "Stunde(n)",
                },
            }],
            "doseAndRate": [{
                "doseQuantity": {"value": 1, "unit": "Stück"},
            }],
            "maxDosePerPeriod": {
                "numerator": {"value": 6, "unit": "Stück"},
                "denominator": {"value": 24, "code": "h"},
            },
        }

        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(dosage)
            ),
            "Bei Kopfschmerzen: im Abstand von mindestens 4 Stunden "
            "je 1 Stück — nicht mehr als 6 Stück in 24 Stunden",
        )

    def test_bounds_duration_regression_uses_days(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "when": ["MORN", "EVE"],
                    "boundsDuration": {
                        "value": 10,
                        "code": "d",
                        "unit": "Tag(e)",
                    },
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "für 10 Tage: 1-0-1-0 Stück",
        )

    def test_bounds_period_formats_start_and_end(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "when": ["MORN"],
                    "boundsPeriod": {
                        "start": "2026-06-05",
                        "end": "2026-07-05",
                    },
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "Vom 05.06.2026 bis zum 05.07.2026: 1-0-0-0 Stück",
        )

    def test_dose_range_is_rendered_with_bis(self):
        dosage = {
            "timing": {
                "repeat": {
                    "frequency": 1,
                    "period": 8,
                    "periodUnit": "h",
                },
            },
            "doseAndRate": [{
                "doseRange": {
                    "low": {"value": 1, "unit": "Stück"},
                    "high": {"value": 2, "unit": "Stück"},
                },
            }],
        }

        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(dosage)
            ),
            "alle 8 Stunden: je 1 bis 2 Stück",
        )

    def test_patient_instruction_is_appended_once(self):
        dosage = self.dosage(
            1,
            {
                "frequency": 1,
                "period": 1,
                "periodUnit": "d",
                "when": ["MORN"],
            },
        )
        dosage["patientInstruction"] = "Mit ausreichend Wasser einnehmen"

        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(dosage)
            ),
            "1-0-0-0 Stück. Hinweis: Mit ausreichend Wasser einnehmen",
        )

    def test_all_supported_resource_types_use_their_dosage_field(self):
        dosage = self.dosage(
            1,
            {
                "frequency": 1,
                "period": 1,
                "periodUnit": "d",
            },
        )
        resources = (
            self.medication_request(dosage),
            self.medication_dispense(dosage),
            self.medication_statement(dosage),
        )

        for resource in resources:
            with self.subTest(resource_type=resource["resourceType"]):
                self.assertEqual(
                    self.generator.generate_dosage_text(resource),
                    "täglich: je 1 Stück",
                )

    def test_time_of_day_and_when_together_raise_error(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "when": ["MORN"],
                    "timeOfDay": ["08:00:00"],
                },
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "timeOfDay und when dürfen nicht gemeinsam angegeben werden",
        ):
            self.generator.generate_dosage_text(resource)

    def test_structured_dosage_without_dose_raises_error(self):
        resource = self.medication_request({
            "timing": {
                "repeat": {
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "d",
                },
            },
        })

        with self.assertRaisesRegex(
            ValueError,
            "doseAndRate ist für die Textgenerierung erforderlich",
        ):
            self.generator.generate_dosage_text(resource)

    def test_duplicate_when_segment_raises_error(self):
        resource = self.medication_request(
            self.dosage(1, {"when": ["MORN"]}),
            self.dosage(2, {"when": ["MORN"]}),
        )

        with self.assertRaisesRegex(
            ValueError,
            "Doppelte Belegung des Tagesabschnitts 'MORN'",
        ):
            self.generator.generate_dosage_text(resource)

    def test_unsupported_resource_type_raises_error(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported resource type: Patient",
        ):
            self.generator.generate_dosage_text({
                "resourceType": "Patient",
            })


if __name__ == "__main__":
    unittest.main()
