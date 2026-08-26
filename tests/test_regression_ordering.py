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
                    "dayOfWeek": ["mon"],
                    "timeOfDay": ["20:00"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stueck"}}],
        }
        dosage_b = {
            "timing": {
                "repeat": {
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
                    "dayOfWeek": ["mon"],
                    "timeOfDay": ["08:00"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stueck"}}],
        }
        dosage_b = {
            "timing": {
                "repeat": {
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

    def test_day_when_combo_duplicate_slot_different_dose_raises_value_error(self):
        # Spec: doppelte Belegung von Wochentag+Tagesabschnitt mit abweichender Dosis → ValueError
        dosage_a = {
            "timing": {
                "repeat": {
                    "dayOfWeek": ["mon"],
                    "when": ["MORN"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stueck"}}],
        }
        dosage_b = {
            "timing": {
                "repeat": {
                    "dayOfWeek": ["mon"],
                    "when": ["MORN"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stueck"}}],
        }

        for order in ([dosage_a, dosage_b], [dosage_b, dosage_a]):
            with self.assertRaisesRegex(ValueError, "Doppelte Belegung der Kombination"):
                self.generator.generate_dosage_text(self._resource(order))

    def test_day_when_combo_merges_different_slots_for_same_day(self):
        dosage_a = {
            "timing": {
                "repeat": {
                    "dayOfWeek": ["mon"],
                    "when": ["MORN"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stueck"}}],
        }
        dosage_b = {
            "timing": {
                "repeat": {
                    "dayOfWeek": ["mon"],
                    "when": ["EVE"],
                }
            },
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stueck"}}],
        }

        output_1 = self.generator.generate_dosage_text(self._resource([dosage_a, dosage_b]))
        output_2 = self.generator.generate_dosage_text(self._resource([dosage_b, dosage_a]))

        self.assertEqual(output_1, output_2)
        self.assertEqual("montags 1-0-2-0 Stueck", output_1)

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
        self.assertIn("täglich: 08:00 Uhr — je 1 Stueck, 20:00 Uhr — je 2 Stueck", output_1)

    def test_interval_time_schema_duplicate_time_key_different_dose_raises_value_error(self):
        # Spec: doppelter Zeit-Schlüssel mit abweichender Dosis → ValueError
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

        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text(self._resource([dosage_a, dosage_b, dosage_c]))

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

    def test_4_schema_when_without_dose_raises_value_error(self):
        dosage_without_dose = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d", "when": ["MORN"]}},
        }
        dosage_with_dose = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d", "when": ["MORN"]}},
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stueck"}}],
        }

        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text(self._resource([dosage_without_dose, dosage_with_dose]))
        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text(self._resource([dosage_with_dose, dosage_without_dose]))

    def test_day_when_without_dose_raises_value_error(self):
        dosage_without_dose = {
            "timing": {
                "repeat": {
                    "dayOfWeek": ["mon"],
                    "when": ["MORN"],
                }
            },
        }

        with self.assertRaisesRegex(ValueError, "doseAndRate ist für die Textgenerierung erforderlich"):
            self.generator.generate_dosage_text(self._resource([dosage_without_dose]))

    def test_interval_when_without_dose_raises_value_error(self):
        dosage_without_dose = {
            "timing": {
                "repeat": {
                    "frequency": 1,
                    "period": 2,
                    "periodUnit": "d",
                    "when": ["MORN"],
                }
            },
        }

        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text(self._resource([dosage_without_dose]))

    def test_interval_time_schema_unknown_when_code_raises_value_error(self):
        # Spec: unbekannter when-Code → ValueError (kein Fallback auf Intervall)
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 2, "periodUnit": "d", "when": ["XYZ"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stueck"}}],
        }

        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text(self._resource([dosage]))


class SchemaOutputTest(unittest.TestCase):
    """Schema-spezifische Ausgabeformat-Tests gegen die normative Spec."""

    URL_AS_NEEDED_FOR = "http://hl7.org/fhir/5.0/StructureDefinition/extension-Dosage.asNeededFor"
    URL_MINDESTABSTAND = "http://ig.fhir.de/igs/medication/StructureDefinition/MindestabstandZwischenGaben"

    def setUp(self):
        self.generator = MODULE.MedicationDosageTextGenerator()

    def _resource(self, dosage_instructions, resource_type="MedicationRequest"):
        key = "dosage" if resource_type == "MedicationStatement" else "dosageInstruction"
        return {"resourceType": resource_type, key: dosage_instructions}

    # ── FreeText ──────────────────────────────────────────────────────────────

    def test_freetext_schema(self):
        dosage = {"text": "Nach Bedarf bei Schmerzen"}
        self.assertEqual("Nach Bedarf bei Schmerzen",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_freetext_multiple_elements_joined_with_space(self):
        self.assertEqual(
            "Morgens Tablette. Abends Kapsel",
            self.generator.generate_dosage_text(self._resource([
                {"text": "Morgens Tablette."},
                {"text": "Abends Kapsel"},
            ])),
        )

    # ── AsNeeded (rein) ───────────────────────────────────────────────────────

    def test_as_needed_without_reason(self):
        dosage = {
            "asNeededBoolean": True,
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("Bei Bedarf: je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_as_needed_with_single_reason(self):
        dosage = {
            "asNeededBoolean": True,
            "extension": [{"url": self.URL_AS_NEEDED_FOR,
                           "valueCodeableConcept": {"text": "Kopfschmerzen"}}],
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("Bei Kopfschmerzen: je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_as_needed_with_two_reasons(self):
        dosage = {
            "asNeededBoolean": True,
            "extension": [
                {"url": self.URL_AS_NEEDED_FOR, "valueCodeableConcept": {"text": "Kopfschmerzen"}},
                {"url": self.URL_AS_NEEDED_FOR, "valueCodeableConcept": {"text": "Fieber"}},
            ],
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("Bei Kopfschmerzen oder Fieber: je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_as_needed_with_three_reasons(self):
        dosage = {
            "asNeededBoolean": True,
            "extension": [
                {"url": self.URL_AS_NEEDED_FOR, "valueCodeableConcept": {"text": "Kopfschmerzen"}},
                {"url": self.URL_AS_NEEDED_FOR, "valueCodeableConcept": {"text": "Fieber"}},
                {"url": self.URL_AS_NEEDED_FOR, "valueCodeableConcept": {"text": "Gliederschmerzen"}},
            ],
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("Bei Kopfschmerzen, Fieber oder Gliederschmerzen: je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_as_needed_with_max_dose_24h(self):
        dosage = {
            "asNeededBoolean": True,
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
            "maxDosePerPeriod": {
                "numerator": {"value": 4, "unit": "Stück"},
                "denominator": {"value": 24, "code": "h"},
            },
        }
        self.assertEqual("Bei Bedarf: je 1 Stück — nicht mehr als 4 Stück in 24 Stunden",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_as_needed_with_max_dose_1d(self):
        dosage = {
            "asNeededBoolean": True,
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
            "maxDosePerPeriod": {
                "numerator": {"value": 4, "unit": "Stück"},
                "denominator": {"value": 1, "code": "d"},
            },
        }
        self.assertEqual("Bei Bedarf: je 1 Stück — nicht mehr als 4 Stück pro Tag",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_as_needed_with_mindestabstand(self):
        dosage = {
            "asNeededBoolean": True,
            "modifierExtension": [{"url": self.URL_MINDESTABSTAND,
                                    "valueDuration": {"value": 4, "code": "h"}}],
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("Bei Bedarf: im Abstand von mindestens 4 Stunden je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_as_needed_multiple_elements_raises_value_error(self):
        dosage = {
            "asNeededBoolean": True,
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text(self._resource([dosage, dosage]))

    # ── 4-Schema ──────────────────────────────────────────────────────────────

    def test_4_schema_basic(self):
        dosage = {
            "timing": {"repeat": {"period": 1, "periodUnit": "d", "when": ["MORN", "EVE"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("1-0-1-0 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_4_schema_all_positions_across_multiple_dosages(self):
        dosage_a = {
            "timing": {"repeat": {"period": 1, "periodUnit": "d", "when": ["MORN", "NOON"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        dosage_b = {
            "timing": {"repeat": {"period": 1, "periodUnit": "d", "when": ["EVE"]}},
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stück"}}],
        }
        self.assertEqual("1-1-2-0 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage_a, dosage_b])))

    def test_4_schema_with_bounds_duration(self):
        dosage = {
            "timing": {"repeat": {"boundsDuration": {"value": 7, "code": "d"},
                                  "period": 1, "periodUnit": "d", "when": ["MORN", "EVE"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Kapsel"}}],
        }
        self.assertEqual("für 7 Tage: 1-0-1-0 Kapsel",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_4_schema_dose_range_switches_to_written_form(self):
        # Variable Dosis → ausgeschriebene Segmentform (kein positionelles Muster)
        dosage = {
            "timing": {"repeat": {"period": 1, "periodUnit": "d", "when": ["MORN"]}},
            "doseAndRate": [{"doseRange": {"low": {"value": 1, "unit": "Stück"},
                                           "high": {"value": 2, "unit": "Stück"}}}],
        }
        result = self.generator.generate_dosage_text(self._resource([dosage]))
        self.assertIn("morgens", result)
        self.assertIn("je 1 bis 2 Stück", result)
        self.assertNotIn("-0-0-0", result)

    # ── TimeOfDay ─────────────────────────────────────────────────────────────

    def test_time_of_day_basic(self):
        dosage = {
            "timing": {"repeat": {"period": 1, "periodUnit": "d", "timeOfDay": ["08:00"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("täglich: 08:00 Uhr — je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_time_of_day_same_dose_grouped(self):
        dosage = {
            "timing": {"repeat": {"period": 1, "periodUnit": "d", "timeOfDay": ["08:00", "20:00"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("täglich: 08:00 Uhr, 20:00 Uhr — je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_time_of_day_different_doses_comma_separated(self):
        dosage_a = {
            "timing": {"repeat": {"period": 1, "periodUnit": "d", "timeOfDay": ["08:00"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        dosage_b = {
            "timing": {"repeat": {"period": 1, "periodUnit": "d", "timeOfDay": ["20:00"]}},
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stück"}}],
        }
        self.assertEqual("täglich: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage_a, dosage_b])))

    # ── DayOfWeek ─────────────────────────────────────────────────────────────

    def test_day_of_week_single_day(self):
        dosage = {
            "timing": {"repeat": {"dayOfWeek": ["mon"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("montags — je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_day_of_week_canonical_order(self):
        dosage = {
            "timing": {"repeat": {"dayOfWeek": ["fri", "mon", "wed"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("montags — je 1 Stück; mittwochs — je 1 Stück; freitags — je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    # ── Interval ─────────────────────────────────────────────────────────────

    def test_interval_taeglich(self):
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d"}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("täglich: je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_interval_woechentlich(self):
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "wk"}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("wöchentlich: je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_interval_alle_8_stunden(self):
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 8, "periodUnit": "h"}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("alle 8 Stunden: je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_interval_frequency_range(self):
        dosage = {
            "timing": {"repeat": {"frequency": 2, "frequencyMax": 3, "period": 1, "periodUnit": "d"}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("2 bis 3 x täglich: je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_interval_period_range(self):
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 2, "periodMax": 3, "periodUnit": "d"}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertEqual("alle 2 bis 3 Tage: je 1 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    # ── Interval+Time-Kombination ─────────────────────────────────────────────

    def test_interval_time_combo(self):
        dosage_a = {
            "timing": {"repeat": {"period": 2, "periodUnit": "d", "timeOfDay": ["08:00"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        dosage_b = {
            "timing": {"repeat": {"period": 2, "periodUnit": "d", "timeOfDay": ["18:00"]}},
            "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stück"}}],
        }
        self.assertEqual("alle 2 Tage: 08:00 Uhr — je 1 Stück, 18:00 Uhr — je 2 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage_a, dosage_b])))

    # ── Dosis-Bereich (doseRange) ─────────────────────────────────────────────

    def test_dose_range_low_and_high(self):
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d"}},
            "doseAndRate": [{"doseRange": {"low": {"value": 1, "unit": "Stück"},
                                           "high": {"value": 2, "unit": "Stück"}}}],
        }
        self.assertEqual("täglich: je 1 bis 2 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    def test_dose_range_high_only(self):
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d"}},
            "doseAndRate": [{"doseRange": {"high": {"value": 2, "unit": "Stück"}}}],
        }
        self.assertEqual("täglich: je bis zu 2 Stück",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    # ── boundsDuration Singular/Plural ────────────────────────────────────────

    def test_bounds_duration_singular(self):
        dosage = {
            "timing": {"repeat": {"boundsDuration": {"value": 1, "code": "d"},
                                  "frequency": 1, "period": 1, "periodUnit": "d"}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertIn("für 1 Tag", self.generator.generate_dosage_text(self._resource([dosage])))

    def test_bounds_duration_plural(self):
        dosage = {
            "timing": {"repeat": {"boundsDuration": {"value": 7, "code": "d"},
                                  "frequency": 1, "period": 1, "periodUnit": "d"}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        self.assertIn("für 7 Tage", self.generator.generate_dosage_text(self._resource([dosage])))

    # ── patientInstruction ────────────────────────────────────────────────────

    def test_patient_instruction_appended(self):
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d"}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
            "patientInstruction": "Mit ausreichend Wasser einnehmen",
        }
        self.assertEqual("täglich: je 1 Stück. Hinweis: Mit ausreichend Wasser einnehmen",
                         self.generator.generate_dosage_text(self._resource([dosage])))

    # ── Deutsches Dezimalkomma ────────────────────────────────────────────────

    def test_decimal_value_german_format(self):
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d"}},
            "doseAndRate": [{"doseQuantity": {"value": 1.5, "unit": "Stück"}}],
        }
        result = self.generator.generate_dosage_text(self._resource([dosage]))
        self.assertIn("1,5", result)
        self.assertNotIn("1.5", result)

    # ── MedicationStatement ───────────────────────────────────────────────────

    def test_medication_statement_resource_type(self):
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d"}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        result = self.generator.generate_dosage_text({
            "resourceType": "MedicationStatement",
            "dosage": [dosage],
        })
        self.assertEqual("täglich: je 1 Stück", result)

    # ── Fehlerbehandlung ──────────────────────────────────────────────────────

    def test_unsupported_resource_type_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text({"resourceType": "Patient"})

    def test_empty_dosage_list_returns_empty_string(self):
        self.assertEqual("", self.generator.generate_dosage_text(self._resource([])))

    def test_time_of_day_and_when_together_raises_value_error(self):
        # tim-10: timeOfDay und when dürfen nicht gemeinsam gesetzt sein
        dosage = {
            "timing": {"repeat": {"period": 1, "periodUnit": "d",
                                  "timeOfDay": ["08:00"], "when": ["MORN"]}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text(self._resource([dosage]))

    def test_bounds_period_and_duration_together_raises_value_error(self):
        dosage = {
            "timing": {"repeat": {
                "boundsDuration": {"value": 7, "code": "d"},
                "boundsPeriod": {"start": "2026-01-01"},
                "frequency": 1, "period": 1, "periodUnit": "d",
            }},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text(self._resource([dosage]))

    def test_unknown_time_unit_raises_value_error(self):
        dosage = {
            "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "x"}},
            "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}],
        }
        with self.assertRaises(ValueError):
            self.generator.generate_dosage_text(self._resource([dosage]))


if __name__ == "__main__":
    unittest.main()
