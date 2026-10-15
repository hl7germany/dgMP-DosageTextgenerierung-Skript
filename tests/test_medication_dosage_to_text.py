#!/usr/bin/env python3

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import pathlib
from decimal import Decimal
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

    def test_short_form_does_not_drop_period_max(self):
        cases = [
            ({"frequency": 1, "period": 1, "periodMax": 3, "periodUnit": "d"},
             "alle 1 bis 3 Tage: je 1 Stück"),
            ({"frequency": 1, "period": 1, "periodMax": 2, "periodUnit": "wk"},
             "alle 1 bis 2 Wochen: je 1 Stück"),
            ({"frequency": 1, "period": 1, "periodMax": 2, "periodUnit": "mo"},
             "alle 1 bis 2 Monate: je 1 Stück"),
            ({"frequency": 2, "period": 1, "periodMax": 3, "periodUnit": "d"},
             "2 x alle 1 bis 3 Tage: je 1 Stück"),
        ]
        for repeat, expected in cases:
            with self.subTest(repeat=repeat):
                resource = self.medication_request(self.dosage(1, repeat))
                self.assertEqual(
                    self.generator.generate_dosage_text(resource),
                    expected,
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
            "täglich: 1-0-2-0 Stück",
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
            "täglich: 1-0-1-0 Stück",
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
            "für 10 Tage täglich: 1-0-1-0 Stück",
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
            "vom 05.06.2026 bis zum 05.07.2026 täglich: 1-0-0-0 Stück",
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

    def test_zero_as_lower_bound_of_a_range_is_rendered(self):
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
            "täglich: morgens — je 0 bis 2 Stück",
        )

    def test_zero_dose_is_rendered_not_rejected(self):
        """Der Wertebereich ist Sache des Profils (DosageDoseValuePositive).
        "je 0 Stück" ist ein eindeutiger Text."""
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
            (self.dosage(0, {"when": ["MORN"]}), "täglich: 0-0-0-0 Stück"),
            (self.dosage(0, {"frequency": 1, "period": 8, "periodUnit": "h"}),
             "alle 8 Stunden: je 0 Stück"),
            (dose_range_high, "täglich: morgens — je 0 bis 0 Stück"),
        )
        for dosage, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    self.generator.generate_dosage_text(
                        self.medication_request(dosage)
                    ),
                    expected,
                )

    def test_explicit_zero_dose_is_kept_in_written_four_schema(self):
        """Eine explizit mit 0 belegte Position ist belegt und darf in der
        ausgeschriebenen Form nicht mit einer unbelegten verwechselt werden."""
        resource = self.medication_request(
            self.dosage(0, {"when": ["MORN"]}),
            {
                "timing": {"repeat": {"when": ["EVE"]}},
                "doseAndRate": [{
                    "doseRange": {
                        "low": {"value": 1, "unit": "Stück"},
                        "high": {"value": 2, "unit": "Stück"},
                    },
                }],
            },
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "täglich: morgens — je 0 Stück, abends — je 1 bis 2 Stück",
        )

    def test_explicit_zero_dose_still_detects_conflicting_duplicates(self):
        """0 darf nicht als "unbelegt" gelten: eine zweite, abweichende Dosis auf
        derselben Position ist ein Konflikt - im 4-Schema wie in der
        Wochentags-Kombination."""
        cases = (
            ({"when": ["MORN"]}, "Doppelte Belegung des Tagesabschnitts 'MORN'"),
            ({"dayOfWeek": ["mon"], "when": ["MORN"]},
             "Doppelte Belegung der Kombination aus Wochentag 'mon'"),
        )
        for repeat, error in cases:
            with self.subTest(error=error):
                resource = self.medication_request(
                    self.dosage(0, repeat),
                    self.dosage(1, repeat),
                )
                with self.assertRaisesRegex(ValueError, error):
                    self.generator.generate_dosage_text(resource)

    def test_zero_bounds_duration_is_rendered_not_rejected(self):
        """TimingValuesPositive ist Sache des Profils."""
        resource = self.medication_request(
            self.dosage(1, {
                "when": ["MORN"],
                "boundsDuration": {"value": 0, "code": "d"},
            })
        )

        self.assertEqual(
            self.generator.generate_dosage_text(resource),
            "für 0 Tage täglich: 1-0-0-0 Stück",
        )

    def test_dose_range_low_unit_is_optional_but_must_match_when_present(self):
        """low.unit erscheint nie im Text (die Ausgabe nimmt high.unit). Fehlt
        sie, ist der Text trotzdem eindeutig; weicht sie ab, würde er sie
        unterschlagen."""
        def dose_range(low):
            return {
                "timing": {"repeat": {"when": ["MORN"]}},
                "doseAndRate": [{
                    "doseRange": {
                        "low": low,
                        "high": {"value": 2, "unit": "Stück"},
                    },
                }],
            }

        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(dose_range({"value": 1}))
            ),
            "täglich: morgens — je 1 bis 2 Stück",
        )
        with self.assertRaisesRegex(
            ValueError,
            "doseRange.low.unit und doseRange.high.unit müssen übereinstimmen",
        ):
            self.generator.generate_dosage_text(
                self.medication_request(dose_range({"value": 1, "unit": "mg"}))
            )

    def test_generated_text_is_always_a_lowercase_fragment(self):
        """Auch Bedarfsmedikation wird nicht grossgeschrieben - es gibt keine Ausnahme."""
        bounds = {"boundsPeriod": {"start": "2026-06-05"}, "when": ["MORN"]}

        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(self.dosage(1, bounds))
            ),
            "ab dem 05.06.2026 täglich: 1-0-0-0 Stück",
        )

        as_needed = self.dosage(1, bounds)
        as_needed["asNeededBoolean"] = True
        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(as_needed)
            ),
            "ab dem 05.06.2026 bei Bedarf: täglich 1-0-0-0 Stück",
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

    def test_numeric_strings_are_rejected_like_any_wrong_type(self):
        """FHIR decimal ist im JSON eine Zahl. Ein String "2" ist kein gueltiger
        Wert; er wuerde sonst als Bereichsmarker (str) gelesen und das 4-Schema
        in die ausgeschriebene Form kippen, ohne Dezimalkomma."""
        for value in ("2", "1.5", "-1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "doseQuantity.value muss numerisch sein"):
                    self.generator.generate_dosage_text(
                        self.medication_request(self.dosage(value, {"when": ["MORN"]}))
                    )

    def test_negative_dose_is_rendered_not_rejected(self):
        """Auch negative Werte sind Sache des Profils; der Text gibt die
        Ressource wieder, statt sie zu beurteilen."""
        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request(
                    self.dosage(-1, {"frequency": 1, "period": 8, "periodUnit": "h"})
                )
            ),
            "alle 8 Stunden: je -1 Stück",
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
            "täglich: 1-0-0-0 Stück. Hinweis: Mit ausreichend Wasser einnehmen",
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

    def test_duplicate_when_segment_raises_error_only_for_different_dose(self):
        # Gleiche Dosis zweimal ergibt denselben Text - wie in allen anderen
        # Schemata; nur eine abweichende Dosis ist nicht darstellbar.
        self.assertEqual(
            self.generator.generate_dosage_text(self.medication_request(
                self.dosage(1, {"when": ["MORN"]}),
                self.dosage(1, {"when": ["MORN"]}),
            )),
            "täglich: 1-0-0-0 Stück",
        )

        resource = self.medication_request(
            self.dosage(1, {"when": ["MORN"]}),
            self.dosage(2, {"when": ["MORN"]}),
        )
        with self.assertRaisesRegex(
            ValueError,
            "Doppelte Belegung des Tagesabschnitts 'MORN' mit unterschiedlicher Dosis",
        ):
            self.generator.generate_dosage_text(resource)

    def test_free_text_is_passed_through_including_surrounding_whitespace(self):
        """FreeTextMatchesRenderedText verlangt exakte Gleichheit mit Dosage.text;
        ein Trim machte sie fuer Texte mit Rand-Leerraum unmoeglich."""
        self.assertEqual(
            self.generator.generate_dosage_text(
                self.medication_request({"text": "  Nach Bedarf\nbei Schmerzen "})
            ),
            "  Nach Bedarf\nbei Schmerzen ",
        )

    def test_unsupported_resource_type_raises_error(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported resource type: Patient",
        ):
            self.generator.generate_dosage_text({
                "resourceType": "Patient",
            })


class FieldTypeTest(unittest.TestCase):
    """Jedes gelesene Feld muss den JSON-Datentyp seines FHIR-Typs haben.

    Ein falscher Typ darf nicht stillschweigend den Text verfaelschen: period "1"
    erkannte kein Tagesmuster (alle 1 Tage statt taeglich), asNeededBoolean
    "true" unterschlug den Bedarf, frequency true zaehlte als 1, ein
    dayOfWeek-String zerfiel in Buchstaben.
    """

    DOSE = [{"doseQuantity": {"value": 1, "unit": "Stück"}}]

    def setUp(self):
        self.generator = MODULE.MedicationDosageTextGenerator()

    def request(self, dosage):
        return {"resourceType": "MedicationRequest", "dosageInstruction": [dosage]}

    def interval(self, **repeat):
        return {
            "timing": {"repeat": {"frequency": 1, "period": 8, "periodUnit": "h", **repeat}},
            "doseAndRate": self.DOSE,
        }

    def test_wrong_json_type_is_rejected_per_fhir_datatype(self):
        when = {"timing": {"repeat": {"when": ["MORN"]}}, "doseAndRate": self.DOSE}
        cases = (
            # positiveInt: nur ganze Zahl, bool ist in Python ein int
            (self.interval(frequency="2"), "timing.repeat.frequency muss eine ganze Zahl sein."),
            (self.interval(frequency=2.5), "timing.repeat.frequency muss eine ganze Zahl sein."),
            (self.interval(frequency=True), "timing.repeat.frequency muss eine ganze Zahl sein."),
            (self.interval(frequencyMax="3"), "timing.repeat.frequencyMax muss eine ganze Zahl sein."),
            # decimal: Zahl, kein String, kein bool
            (self.interval(period="1", periodUnit="d"), "timing.repeat.period muss numerisch sein."),
            (self.interval(period=True), "timing.repeat.period muss numerisch sein."),
            (self.interval(periodMax="3"), "timing.repeat.periodMax muss numerisch sein."),
            # code / string
            (self.interval(periodUnit=5), "timing.repeat.periodUnit muss ein String sein."),
            ({**when, "doseAndRate": [{"doseQuantity": {"value": 1, "unit": 5}}]},
             "doseQuantity.unit muss ein String sein."),
            ({**when, "patientInstruction": 5}, "patientInstruction muss ein String sein."),
            ({"text": 5}, "text muss ein String sein."),
            # Listenfelder
            ({"timing": {"repeat": {"dayOfWeek": "mon"}}, "doseAndRate": self.DOSE},
             "timing.repeat.dayOfWeek muss eine Liste sein."),
            ({"timing": {"repeat": {"when": "MORN"}}, "doseAndRate": self.DOSE},
             "timing.repeat.when muss eine Liste sein."),
            ({"timing": {"repeat": {"timeOfDay": "08:00:00"}}, "doseAndRate": self.DOSE},
             "timing.repeat.timeOfDay muss eine Liste sein."),
            ({"timing": {"repeat": {"when": [5]}}, "doseAndRate": self.DOSE},
             r"timing.repeat.when\[\] muss ein String sein."),
            ({**when, "doseAndRate": {"doseQuantity": {"value": 1, "unit": "Stück"}}},
             "doseAndRate muss eine Liste sein."),
            ({"asNeededBoolean": True, "doseAndRate": self.DOSE, "extension": {"url": "x"}},
             "extension muss eine Liste sein."),
            # boolean
            ({**when, "asNeededBoolean": "true"}, "asNeededBoolean muss ein boolescher Wert sein."),
            ({"asNeededBoolean": 1, "doseAndRate": self.DOSE},
             "asNeededBoolean muss ein boolescher Wert sein."),
            # Objekte
            ({**when, "timing": "täglich"}, "timing muss ein Objekt sein."),
            ({**when, "doseAndRate": [{"doseQuantity": "1 Stück"}]}, "doseQuantity muss ein Objekt sein."),
            # Maximalmenge
            ({"asNeededBoolean": True, "doseAndRate": self.DOSE,
              "maxDosePerPeriod": {"numerator": {"value": 2, "unit": "Stück"},
                                   "denominator": {"value": "1", "code": "d"}}},
             "maxDosePerPeriod.denominator.value muss numerisch sein."),
            ({"asNeededBoolean": True, "doseAndRate": self.DOSE,
              "maxDosePerPeriod": {"numerator": "2 Stück", "denominator": {"value": 1, "code": "d"}}},
             "maxDosePerPeriod.numerator muss ein Objekt sein."),
            # Extensions
            ({"asNeededBoolean": True, "doseAndRate": self.DOSE,
              "extension": [{"url": MODULE.MedicationDosageTextGenerator.URL_AS_NEEDED_FOR,
                             "valueCodeableConcept": "Kopfschmerzen"}]},
             r"extension\[\].valueCodeableConcept muss ein Objekt sein."),
            ({"asNeededBoolean": True, "doseAndRate": self.DOSE,
              "modifierExtension": [{"url": MODULE.MedicationDosageTextGenerator.URL_MINDESTABSTAND,
                                     "valueDuration": {"value": "4", "code": "h"}}]},
             r"modifierExtension\[\].valueDuration.value muss numerisch sein."),
            # Zeitrahmen
            ({**when, "timing": {"repeat": {"when": ["MORN"], "boundsPeriod": {"start": 2026}}}},
             "timing.repeat.boundsPeriod.start muss ein String sein."),
            ({**when, "timing": {"repeat": {"when": ["MORN"], "boundsDuration": {"value": "7", "code": "d"}}}},
             "timing.repeat.boundsDuration.value muss numerisch sein."),
            # Dosis-Unterfelder werden vor der Schema-Erkennung geprueft
            ({"timing": {"repeat": {"frequency": 1}}, "doseAndRate": [{"doseQuantity": {"value": "2", "unit": "Stück"}}]},
             "doseQuantity.value muss numerisch sein."),
        )
        for dosage, error in cases:
            with self.subTest(error=error):
                with self.assertRaisesRegex(ValueError, error):
                    self.generator.generate_dosage_text(self.request(dosage))

    def test_empty_dose_range_low_counts_as_present(self):
        dosage = {
            "timing": {"repeat": {"when": ["MORN"]}},
            "doseAndRate": [{"doseRange": {"low": {}, "high": {"value": 2, "unit": "Stück"}}}],
        }
        with self.assertRaisesRegex(ValueError, "doseRange.low.value ist für die Textgenerierung erforderlich"):
            self.generator.generate_dosage_text(self.request(dosage))

    def test_bounds_period_accepts_any_fraction_digits_and_leap_second(self):
        """FHIR erlaubt beliebig viele Bruchteilstellen und :60; Python 3.10
        verstand nur 3 oder 6 Stellen. Sekunden werden nicht dargestellt."""
        for start in ("2026-06-05T23:30:45.1Z", "2026-06-05T23:30:45.1234567Z",
                      "2026-06-05T23:30:60Z", "2026-06-05T23:30:45Z"):
            with self.subTest(start=start):
                dosage = self.interval(boundsPeriod={"start": start})
                self.assertEqual(
                    self.generator.generate_dosage_text(self.request(dosage)),
                    "ab dem 06.06.2026 um 01:30 Uhr alle 8 Stunden: je 1 Stück",
                )

    def test_time_of_day_accepts_leap_second(self):
        dosage = {"timing": {"repeat": {"timeOfDay": ["08:00:60"]}}, "doseAndRate": self.DOSE}
        self.assertEqual(
            self.generator.generate_dosage_text(self.request(dosage)),
            "täglich: 08:00 Uhr — je 1 Stück",
        )

    def test_dosage_list_must_be_a_list(self):
        with self.assertRaisesRegex(ValueError, "dosageInstruction muss eine Liste sein."):
            self.generator.generate_dosage_text(
                {"resourceType": "MedicationRequest", "dosageInstruction": {"text": "x"}}
            )

    def test_unknown_day_of_week_code_is_rejected_like_when(self):
        """Die Wochentags-Tabelle ist abschliessend; bisher erschien ein fremder
        Code roh im Text ("xyz — je 1 Stück")."""
        cases = (
            {"dayOfWeek": ["xyz"]},
            {"dayOfWeek": ["xyz"], "timeOfDay": ["08:00:00"]},
            {"dayOfWeek": ["xyz"], "when": ["MORN"]},
        )
        for repeat in cases:
            with self.subTest(repeat=repeat):
                with self.assertRaisesRegex(
                    ValueError, "Nicht unterstützter Wochentag \\(dayOfWeek\\): 'xyz'"
                ):
                    self.generator.generate_dosage_text(
                        self.request({"timing": {"repeat": repeat}, "doseAndRate": self.DOSE})
                    )

    def test_numbers_keep_the_precision_of_the_resource(self):
        """FHIR: Die Genauigkeit eines decimal einschliesslich nachfolgender Nullen
        traegt Bedeutung und ist auch fuer die Darstellung zu erhalten. Das
        setzt Decimal-Werte voraus (parse_float=Decimal); ein float hat die
        Nullen beim Einlesen verloren und wird bestmoeglich ausgegeben.
        Exponentialschreibweise wird nie erzeugt."""
        def dose(value, unit="Stück"):
            return self.request({
                "timing": {"repeat": {"frequency": 1, "period": 8, "periodUnit": "h"}},
                "doseAndRate": [{"doseQuantity": {"value": value, "unit": unit}}],
            })

        cases = (
            (dose(Decimal("2.50")), "alle 8 Stunden: je 2,50 Stück"),
            (dose(Decimal("1.0")), "alle 8 Stunden: je 1,0 Stück"),
            (dose(Decimal("1")), "alle 8 Stunden: je 1 Stück"),
            (dose(Decimal("1E-2"), "mg"), "alle 8 Stunden: je 0,01 mg"),
            (dose(Decimal("1E+2"), "mg"), "alle 8 Stunden: je 100 mg"),
            (dose(100), "alle 8 Stunden: je 100 Stück"),
            (dose(2.5), "alle 8 Stunden: je 2,5 Stück"),
            (dose(1.25), "alle 8 Stunden: je 1,25 Stück"),
            (dose(0.00001, "mg"), "alle 8 Stunden: je 0,00001 mg"),
            (self.request(self.interval(period=Decimal("1.5"), periodUnit="d",
                                        boundsDuration={"value": Decimal("2.0"), "code": "wk"})),
             "für 2,0 Wochen alle 1,5 Tage: je 1 Stück"),
        )
        for resource, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(self.generator.generate_dosage_text(resource), expected)

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


class SilentOmissionTest(unittest.TestCase):
    """Der Algorithmus bricht ab, statt eine Angabe der Ressource zu
    unterschlagen oder mehrdeutig wiederzugeben. Diese Faelle rutschten
    bisher durch (Befunde des Reviews gegen Spec und IG-Beispiele)."""

    URL_AS_NEEDED_FOR = MODULE.MedicationDosageTextGenerator.URL_AS_NEEDED_FOR
    URL_MINDESTABSTAND = MODULE.MedicationDosageTextGenerator.URL_MINDESTABSTAND

    def setUp(self):
        self.generator = MODULE.MedicationDosageTextGenerator()

    def request(self, *dosages):
        return {"resourceType": "MedicationRequest", "dosageInstruction": list(dosages)}

    @staticmethod
    def dosage(dose, repeat=None, unit="Stück", **extra):
        dosage = {"doseAndRate": [{"doseQuantity": {"value": dose, "unit": unit}}], **extra}
        if repeat is not None:
            dosage["timing"] = {"repeat": repeat}
        return dosage

    def text(self, *dosages):
        return self.generator.generate_dosage_text(self.request(*dosages))

    # -- doppelte Uhrzeit --------------------------------------------------

    def test_same_time_with_different_dose_is_rejected_in_time_schemas(self):
        cases = (
            ({"timeOfDay": ["08:00:00"]}, {"timeOfDay": ["08:00:00"]}),
            ({"dayOfWeek": ["mon"], "timeOfDay": ["08:00:00"]},
             {"dayOfWeek": ["mon"], "timeOfDay": ["08:00:00"]}),
            # HH:MM und HH:MM:SS sind dieselbe Uhrzeit
            ({"timeOfDay": ["08:00"]}, {"timeOfDay": ["08:00:00"]}),
        )
        for first, second in cases:
            with self.subTest(first=first):
                with self.assertRaisesRegex(ValueError, "Doppelte Belegung der Uhrzeit '08:00 Uhr'"):
                    self.text(self.dosage(1, first), self.dosage(2, second))

    def test_same_time_with_same_dose_is_rendered_once(self):
        self.assertEqual(
            self.text(self.dosage(1, {"timeOfDay": ["08:00:00", "08:00:00"]}),
                      self.dosage(1, {"timeOfDay": ["08:00:00"]})),
            "täglich: 08:00 Uhr — je 1 Stück",
        )

    # -- Wochentags-Kombination: when und timeOfDay gemischt ---------------

    def test_day_combination_rejects_mixed_when_and_time_of_day_across_elements(self):
        a = self.dosage(1, {"dayOfWeek": ["mon"], "timeOfDay": ["08:00:00"]})
        b = self.dosage(2, {"dayOfWeek": ["mon"], "when": ["MORN"]})
        c = self.dosage(2, {"dayOfWeek": ["wed"], "when": ["MORN"]})
        for pair in ((a, b), (b, a), (a, c), (c, a)):
            with self.subTest(pair=[d["timing"]["repeat"] for d in pair]):
                with self.assertRaisesRegex(ValueError, "dürfen nicht gemischt werden"):
                    self.text(*pair)

    # -- Intervall mit mehreren Elementen ------------------------------------

    def test_interval_schema_rejects_more_than_one_element(self):
        a = self.dosage(1, {"frequency": 1, "period": 8, "periodUnit": "h"})
        b = self.dosage(2, {"frequency": 1, "period": 12, "periodUnit": "h"})
        with self.assertRaisesRegex(ValueError, "Wiederkehrende Intervalle erlauben genau ein Dosage-Element"):
            self.text(a, b)

    # -- Mindestabstand, Maximalmenge, Anlass ------------------------------

    def test_minimum_interval_is_rejected_with_weekday_rhythm(self):
        for repeat in ({"dayOfWeek": ["mon"]}, {"dayOfWeek": ["mon"], "when": ["MORN"]}):
            with self.subTest(repeat=repeat):
                dosage = self.dosage(1, repeat, asNeededBoolean=True, modifierExtension=[{
                    "url": self.URL_MINDESTABSTAND, "valueDuration": {"value": 4, "code": "h"}}])
                with self.assertRaisesRegex(ValueError, "Mindestabstand ist nur bei reiner Bedarfsmedikation"):
                    self.text(dosage)

    def test_as_needed_fields_without_as_needed_flag_are_rejected(self):
        repeat = {"frequency": 1, "period": 8, "periodUnit": "h"}
        cases = (
            (self.dosage(1, repeat, extension=[{"url": self.URL_AS_NEEDED_FOR,
                                               "valueCodeableConcept": {"text": "Kopfschmerzen"}}]),
             "Ein Einnahmeanlass \\(asNeededFor\\) setzt asNeededBoolean = true voraus"),
            (self.dosage(1, repeat, modifierExtension=[{"url": self.URL_MINDESTABSTAND,
                                                       "valueDuration": {"value": 4, "code": "h"}}]),
             "Ein Mindestabstand setzt asNeededBoolean = true voraus"),
            (self.dosage(1, repeat, maxDosePerPeriod={"numerator": {"value": 4, "unit": "Stück"},
                                                     "denominator": {"value": 1, "code": "d"}}),
             "Eine Maximalmenge setzt asNeededBoolean = true voraus"),
            (self.dosage(1, {"when": ["MORN"]}, maxDosePerPeriod={"numerator": {"value": 4, "unit": "Stück"},
                                                                 "denominator": {"value": 1, "code": "d"}}),
             "Eine Maximalmenge setzt asNeededBoolean = true voraus"),
        )
        for dosage, error in cases:
            with self.subTest(error=error):
                with self.assertRaisesRegex(ValueError, error):
                    self.text(dosage)

    # -- Einheit ------------------------------------------------------------

    def test_differing_dose_units_across_elements_are_rejected(self):
        cases = (
            ({"when": ["MORN"]}, {"when": ["EVE"]}),
            ({"dayOfWeek": ["mon"]}, {"dayOfWeek": ["wed"]}),
            ({"dayOfWeek": ["mon"], "when": ["MORN"]}, {"dayOfWeek": ["wed"], "when": ["MORN"]}),
        )
        for first, second in cases:
            with self.subTest(first=first):
                with self.assertRaisesRegex(ValueError, "Abweichende Dosis-Einheiten 'Stück' und 'mg'"):
                    self.text(self.dosage(1, first), self.dosage(2, second, unit="mg"))

    # -- frequencyMax in der Intervall-Kombination ---------------------------

    def test_frequency_max_is_not_allowed_in_interval_combination(self):
        dosage = self.dosage(1, {"frequency": 1, "frequencyMax": 2, "period": 2,
                                 "periodUnit": "d", "when": ["MORN"]})
        with self.assertRaisesRegex(ValueError, "keinem unterstützten Dosierungsschema"):
            self.text(dosage)

    # -- "dieselbe Dosis" ------------------------------------------------------

    def test_same_dose_means_same_text_and_first_value_wins(self):
        # 1 und 1.0 sind numerisch gleich, aber verschiedene Texte -> Konflikt
        with self.assertRaisesRegex(ValueError, "Doppelte Belegung des Tagesabschnitts 'MORN'"):
            self.text(self.dosage(1, {"when": ["MORN"]}), self.dosage(Decimal("1.0"), {"when": ["MORN"]}))
        with self.assertRaisesRegex(ValueError, "Doppelte Belegung des Wochentags 'mon'"):
            self.text(self.dosage(1, {"dayOfWeek": ["mon"]}), self.dosage(Decimal("1.0"), {"dayOfWeek": ["mon"]}))
        # gleiche Darstellung: ein Text, unabhaengig von der Reihenfolge
        a, b = self.dosage(1, {"when": ["MORN"]}), self.dosage(Decimal("1"), {"when": ["MORN"]})
        self.assertEqual(self.text(a, b), "täglich: 1-0-0-0 Stück")
        self.assertEqual(self.text(b, a), "täglich: 1-0-0-0 Stück")


if __name__ == "__main__":
    unittest.main()
