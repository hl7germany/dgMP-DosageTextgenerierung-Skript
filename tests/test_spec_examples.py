#!/usr/bin/env python3
"""Die Spezifikation gegen die Testvektoren in tests/cases/.

Ob das Skript jeden Vektor erfüllt, prüft test_cases.py. Dieser Test prüft,
dass die Vektoren die Spezifikation abdecken:

SpecTextExamplesTest: Jedes Textbeispiel im Fliesstext der Spezifikation
kommt in einem erwarteten Text vor - ein vollstaendiger Text exakt, ein
Baustein (etwa `je 1 bis 2 Stück`) als Teil eines Textes. Ein neues Beispiel
ohne Vektor laesst den Test scheitern.

ErrorListTest: Jede Meldung der Fehlerliste ("Fehler und Validierung") wird
von mindestens einem Vektor erwartet, und jede erwartete Meldung steht in der
Fehlerliste.
"""

import json
import re
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "dosage-text-algorithm-spec.md"
CASES_DIR = ROOT / "tests" / "cases"


def vector_cases():
    for path in sorted(CASES_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as file:
            yield from json.load(file, parse_float=Decimal)["cases"]


def expected_texts():
    return [case["expect"]["text"] for case in vector_cases() if "text" in case["expect"]]


def expected_errors():
    return [(case["name"], case["expect"]["error"]) for case in vector_cases() if "error" in case["expect"]]


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
    def test_every_spec_text_example_is_expected_by_a_vector(self):
        complete, fragments = spec_text_examples()
        outputs = expected_texts()
        self.assertGreater(len(complete), 20)
        for text in sorted(complete):
            with self.subTest(text):
                self.assertIn(text, outputs, f"Kein Vektor erwartet das Beispiel: {text}")
        for text in sorted(fragments):
            with self.subTest(text):
                self.assertTrue(any(text in output for output in outputs),
                                f"Baustein in keiner erwarteten Ausgabe: {text}")


class ErrorListTest(unittest.TestCase):
    def test_every_vector_message_is_listed_in_the_spec(self):
        patterns = [template_pattern(template) for template in spec_error_templates()]
        for name, message in expected_errors():
            with self.subTest(name):
                self.assertTrue(any(pattern.match(message) for pattern in patterns),
                                f"Meldung fehlt in der Fehlerliste: {message}")

    def test_every_spec_message_is_expected_by_a_vector(self):
        messages = [message for _, message in expected_errors()]
        for template in spec_error_templates():
            with self.subTest(template):
                pattern = template_pattern(template)
                self.assertTrue(any(pattern.match(message) for message in messages),
                                f"Kein Vektor erwartet diese Meldung: {template}")


if __name__ == "__main__":
    unittest.main()
