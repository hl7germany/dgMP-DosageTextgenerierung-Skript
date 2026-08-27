#!/usr/bin/env python3

import importlib.util
import unittest
import pathlib
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "medication-dosage-to-text.py"
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

    def test_interval_time_combination_ignores_optional_frequency_in_text(self):
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

    def test_minimum_interval_with_structured_rhythm_is_rejected(self):
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

        # Der Rhythmus legt den Abstand bereits fest; ein Mindestabstand daneben
        # waere widerspruechlich und darf nicht stillschweigend entfallen.
        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text(self.medication_request(dosage))

        # Ohne Rhythmus ist derselbe Mindestabstand die einzige zeitliche Schranke.
        del dosage["timing"]
        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(dosage)
            ),
            "bei Kopfschmerzen: im Abstand von mindestens 6 Stunden je 1 Stück — "
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
                    "when": ["MORN"],
                },
            ),
            self.dosage(
                2,
                {
                    "when": ["EVE"],
                },
            ),
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "1-0-2-0 Stück",
        )

    def test_daily_four_schema_accepts_optional_frequency_period_and_unit(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "when": ["MORN", "EVE"],
                    "frequency": 2,
                    "period": 1,
                    "periodUnit": "d",
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "1-0-1-0 Stück",
        )

    def test_day_of_week_schema_uses_canonical_order(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
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
            "bei Kopfschmerzen: im Abstand von mindestens 4 Stunden "
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
            "vom 05.06.2026 bis zum 05.07.2026: 1-0-0-0 Stück",
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

    def test_zero_is_allowed_only_as_the_lower_bound_of_a_range(self):
        dose_range_low = {
            "timing": {"repeat": {"when": ["MORN"]}},
            "doseAndRate": [{
                "doseRange": {
                    "low": {"value": 0, "unit": "Stück"},
                    "high": {"value": 2, "unit": "Stück"},
                },
            }],
        }

        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(dose_range_low)
            ),
            "morgens — je 0 bis 2 Stück",
        )

    def test_zero_is_rejected_as_single_dose_and_as_upper_bound(self):
        dose_quantity = self.dosage(0, {"when": ["MORN"]})
        dose_range_high = {
            "timing": {"repeat": {"when": ["MORN"]}},
            "doseAndRate": [{
                "doseRange": {
                    "low": {"value": 0, "unit": "Stück"},
                    "high": {"value": 0, "unit": "Stück"},
                },
            }],
        }

        cases = (
            (dose_quantity, "doseQuantity.value muss größer als 0 sein"),
            (dose_range_high, "doseRange.high.value muss größer als 0 sein"),
        )
        for dosage, error in cases:
            with self.subTest(error=error):
                with self.assertRaisesRegex(ValueError, error):
                    self.generator.generate_dosage_text(
                        self.medication_request(dosage)
                    )

    def test_generated_text_is_always_a_lowercase_fragment(self):
        """Auch Bedarfsmedikation wird nicht grossgeschrieben - es gibt keine Ausnahme."""
        bounds = {"boundsPeriod": {"start": "2026-06-05"}, "when": ["MORN"]}

        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(self.dosage(1, bounds))
            ),
            "ab dem 05.06.2026: 1-0-0-0 Stück",
        )

        as_needed = self.dosage(1, bounds)
        as_needed["asNeededBoolean"] = True
        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(as_needed)
            ),
            "ab dem 05.06.2026 bei Bedarf: 1-0-0-0 Stück",
        )

    def test_non_numeric_dose_values_are_rejected(self):
        cases = (
            (self.dosage("abc", {"when": ["MORN"]}), "doseQuantity.value muss numerisch sein"),
            (self.dosage(True, {"when": ["MORN"]}), "doseQuantity.value muss numerisch sein"),
            ({
                "timing": {"repeat": {"when": ["MORN"]}},
                "doseAndRate": [{
                    "doseRange": {"high": {"value": "abc", "unit": "Stück"}},
                }],
            }, "doseRange.high.value muss numerisch sein"),
        )
        for dosage, error in cases:
            with self.subTest(error=error):
                with self.assertRaisesRegex(ValueError, error):
                    self.generator.generate_dosage_text(
                        self.medication_request(dosage)
                    )

    def test_numeric_strings_are_validated_like_numbers(self):
        with self.assertRaisesRegex(ValueError, "doseQuantity.value muss größer als 0 sein"):
            self.generator.generate_dosage_text(
                self.medication_request(self.dosage("-1", {"when": ["MORN"]}))
            )

    def test_negative_values_are_rejected_in_all_dose_value_locations(self):
        dose_quantity = self.dosage(-1, {"when": ["MORN"]})
        dose_range_low = {
            "timing": {"repeat": {"when": ["MORN"]}},
            "doseAndRate": [{
                "doseRange": {
                    "low": {"value": -1, "unit": "Stück"},
                    "high": {"value": 2, "unit": "Stück"},
                },
            }],
        }
        dose_range_high = {
            "timing": {"repeat": {"when": ["MORN"]}},
            "doseAndRate": [{
                "doseRange": {
                    "high": {"value": -1, "unit": "Stück"},
                },
            }],
        }

        cases = (
            (dose_quantity, "doseQuantity.value muss größer als 0 sein"),
            (dose_range_low, "doseRange.low.value darf nicht negativ sein"),
            (dose_range_high, "doseRange.high.value muss größer als 0 sein"),
        )
        for dosage, error in cases:
            with self.subTest(error=error):
                with self.assertRaisesRegex(ValueError, error):
                    self.generator.generate_dosage_text(
                        self.medication_request(dosage)
                    )

    def test_patient_instruction_is_appended_once(self):
        dosage = self.dosage(
            1,
            {
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

    def test_weekday_accepts_legacy_frequency_period_and_unit(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "dayOfWeek": ["tue", "thu"],
                    "frequency": 2,
                    "period": 1,
                    "periodUnit": "wk",
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "dienstags — je 1 Stück; donnerstags — je 1 Stück",
        )

    def test_weekday_rejects_a_real_interval(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "dayOfWeek": ["tue"],
                    "frequency": 1,
                    "period": 3,
                    "periodUnit": "h",
                },
            )
        )

        with self.assertRaisesRegex(ValueError, "keinem unterstützten"):
            self.generator.generate_dosage_text(resource)

    def test_weekday_legacy_matrix_across_all_resource_types(self):
        resource_builders = (
            self.medication_request,
            self.medication_dispense,
            self.medication_statement,
        )
        repeats_and_expected = (
            (
                {"dayOfWeek": ["tue", "thu"]},
                "dienstags — je 1 Stück; donnerstags — je 1 Stück",
            ),
            (
                {"dayOfWeek": ["tue"], "when": ["MORN", "EVE"]},
                "dienstags 1-0-1-0 Stück",
            ),
            (
                {
                    "dayOfWeek": ["tue"],
                    "timeOfDay": ["08:00:00", "20:00:00"],
                },
                "dienstags 08:00 Uhr, 20:00 Uhr — je 1 Stück",
            ),
        )

        for builder in resource_builders:
            for repeat, expected in repeats_and_expected:
                for include_legacy in (False, True):
                    tested_repeat = dict(repeat)
                    if include_legacy:
                        concrete_count = len(repeat["dayOfWeek"])
                        concrete_count *= len(
                            repeat.get("when", repeat.get("timeOfDay", [None]))
                        )
                        tested_repeat.update({
                            "frequency": concrete_count,
                            "period": 1,
                            "periodUnit": "wk",
                        })
                    resource = builder(self.dosage(1, tested_repeat))
                    with self.subTest(
                        resource_type=resource["resourceType"],
                        fields=tuple(tested_repeat),
                    ):
                        self.assertEqual(
                            self.generator.generate_dosage_text(resource),
                            expected,
                        )

    def test_weekday_interval_rejected_across_all_resource_types(self):
        resource_builders = (
            self.medication_request,
            self.medication_dispense,
            self.medication_statement,
        )
        repeats = (
            {
                "dayOfWeek": ["tue"],
                "frequency": 1,
                "period": 2,
                "periodUnit": "wk",
            },
            {
                "dayOfWeek": ["tue"],
                "when": ["MORN"],
                "frequency": 1,
                "period": 3,
                "periodUnit": "h",
            },
            {
                "dayOfWeek": ["tue"],
                "timeOfDay": ["08:00:00"],
                "frequency": 1,
                "period": 30,
                "periodUnit": "min",
            },
        )

        for builder in resource_builders:
            for repeat in repeats:
                resource = builder(self.dosage(1, repeat))
                with self.subTest(
                    resource_type=resource["resourceType"],
                    fields=tuple(repeat),
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "keinem unterstützten Dosierungsschema",
                    ):
                        self.generator.generate_dosage_text(resource)

    def test_when_accepts_optional_frequency_period_and_unit(self):
        resource = self.medication_request(
            self.dosage(
                1,
                {
                    "when": ["MORN"],
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "wk",
                },
            )
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "wöchentlich: morgens — je 1 Stück",
        )

    def test_algorithm_version_matches_spec(self):
        """__version__ wird als algorithmVersion in jede Ressource geschrieben.

        Der Wert muss mit der Versionsangabe der Spezifikation uebereinstimmen;
        beim Tag-Push prueft die CI zusaetzlich gegen den Tag.
        """
        spec = (pathlib.Path(__file__).resolve().parents[1]
                / "dosage-text-algorithm-spec.md").read_text(encoding="utf-8")
        self.assertIn(f"Algorithmus-Version **{MODULE.__version__}**", spec)

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
