#!/usr/bin/env python3
"""Die Spezifikation gegen die Testvektoren in tests/cases/.

Ob das Skript jeden Vektor erfüllt, prüft test_cases.py. Dieser Test prüft,
dass die Vektoren die Spezifikation abdecken:

SpecTextExamplesTest: Jedes Textbeispiel im Fliesstext der Spezifikation
kommt in einem erwarteten Text vor - ein vollstaendiger Text exakt, ein
Baustein (etwa `je 1 bis 2 Stück`) als Teil eines Textes. Ein neues Beispiel
ohne Vektor laesst den Test scheitern.

ErrorListTest: Die Spezifikation legt nur die Abbruchbedingungen fest, nicht
den Wortlaut der Meldungen. ABORT_CONDITIONS ordnet jeder Bedingung der Liste
"Fehler und Validierung" die Meldungen des Skripts zu. Jede Bedingung braucht
einen Vektor, der eine ihrer Meldungen auslöst, und jede Meldung, die ein Vektor
auslöst (tests/script-messages.json), muss zu einer Bedingung gehören. Eine neue
Bedingung ohne Vektor oder ein Abbruch des Skripts ohne Bedingung lässt den
Test scheitern.
"""

import json
import re
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "dosage-text-algorithm-spec.md"
CASES_DIR = ROOT / "tests" / "cases"
MESSAGES_PATH = ROOT / "tests" / "script-messages.json"


def vector_cases():
    for path in sorted(CASES_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as file:
            yield from json.load(file, parse_float=Decimal)["cases"]


def expected_texts():
    return [case["expect"]["text"] for case in vector_cases() if "text" in case["expect"]]


def script_messages():
    with open(MESSAGES_PATH, encoding="utf-8") as file:
        return json.load(file)


def spec_abort_conditions():
    """Die Einträge der Liste unter "Fehler und Validierung"."""
    text = SPEC_PATH.read_text(encoding="utf-8")
    section = text.split("\n## Fehler und Validierung\n", 1)[1].split("\n## ", 1)[0]
    return [line[2:] for line in section.splitlines() if line.startswith("* ")]


# Anfang des Listeneintrags -> Meldungen des Skripts. {…} und <…> stehen für
# beliebigen Text.
ABORT_CONDITIONS = {
    "fehlender oder nicht unterstützter `resourceType`": [
        "Unsupported resource type: {resourceType}"],
    "falscher JSON-Datentyp": [
        "<Feld> muss numerisch sein.", "<Feld> muss eine ganze Zahl sein.", "<Feld> muss ein String sein.",
        "<Feld> muss eine Liste sein.", "<Feld> muss ein Objekt sein.",
        "asNeededBoolean muss ein boolescher Wert sein."],
    "`comparator`": [
        "<Feld>.comparator wird nicht unterstützt."],
    "mehr als ein Eintrag in `doseAndRate`": [
        "doseAndRate darf höchstens einen Eintrag enthalten."],
    "`doseQuantity` und `doseRange` im selben": [
        "doseQuantity und doseRange dürfen nicht gemeinsam angegeben werden."],
    "`modifierExtension`": [
        "Nicht unterstützte modifierExtension: '{url}'."],
    "`timeOfDay` und `when`": [
        "timeOfDay und when dürfen nicht gemeinsam angegeben werden (tim-10)."],
    "eine reine Bedarfsdosierung": [
        "Reine Bedarfsmedikation erlaubt genau ein Dosage-Element."],
    "`Dosage`-Elemente mit unterschiedlichem Schema": [
        "Alle Dosage-Elemente müssen demselben Schema folgen; Element 1 ergibt '{schema}', Element {n} '{schema}'."],
    "keine Regel der [Schema-Erkennung]": [
        "Die Dosierung entspricht keinem unterstützten Dosierungsschema."],
    "fehlende [Dosis]": [
        "doseAndRate ist für die Textgenerierung erforderlich.",
        "Dosisangabe in doseAndRate[0] fehlt.",
        "doseQuantity.value ist für die Textgenerierung erforderlich.",
        "doseQuantity.unit ist für die Textgenerierung erforderlich.",
        "doseRange.high.value ist für die Textgenerierung erforderlich.",
        "doseRange.high.unit ist für die Textgenerierung erforderlich.",
        "doseRange.low.value ist für die Textgenerierung erforderlich."],
    "negativer Dosiswert": [
        "<Feld> darf nicht negativ sein."],
    "`doseRange.low.unit`": [
        "doseRange.low.unit und doseRange.high.unit müssen übereinstimmen."],
    "[`boundsDuration`]": [
        "boundsDuration.value ist für die Textgenerierung erforderlich.",
        "boundsDuration.code ist für die Textgenerierung erforderlich."],
    "`boundsPeriod` und `boundsDuration`": [
        "boundsPeriod und boundsDuration dürfen nicht gleichzeitig vorhanden sein."],
    "[`boundsPeriod`]": [
        "boundsPeriod muss start und/oder end enthalten.",
        "boundsPeriod.{start|end} muss ein parsebares FHIR-dateTime mit vollständigem Datum im Format JJJJ-MM-TT "
        "sein; eine Uhrzeit erfordert eine Zeitzone."],
    "nicht parsebares oder außerhalb des Uhrzeitbereichs": [
        "timeOfDay muss im Format HH:MM oder HH:MM:SS[.Bruchteile] angegeben sein."],
    "Code außerhalb der Tabelle": [
        "Nicht unterstützte Zeiteinheit: '{code}'.",
        "Nicht unterstützter Wochentag (dayOfWeek): '{code}'.",
        "Nicht unterstützter Tagesabschnitt (when): '{code}'."],
    "[Einnahmeanlass]": [
        "asNeededFor.valueCodeableConcept.text ist für die Textgenerierung erforderlich.",
        "Ein Einnahmeanlass (asNeededFor) setzt asNeededBoolean = true voraus."],
    "[Mindestabstand]": [
        "MinimumIntervalBetweenAdministrations.valueDuration ist für die Textgenerierung erforderlich.",
        "MinimumIntervalBetweenAdministrations.valueDuration.value ist für die Textgenerierung erforderlich.",
        "MinimumIntervalBetweenAdministrations.valueDuration.code ist für die Textgenerierung erforderlich.",
        "Es ist höchstens ein Mindestabstand (MinimumIntervalBetweenAdministrations) zulässig.",
        "Ein Mindestabstand setzt asNeededBoolean = true voraus.",
        "Ein Mindestabstand ist nur bei reiner Bedarfsmedikation zulässig, nicht zusammen mit einem strukturierten "
        "Rhythmus.",
        "Ein Mindestabstand ist bei einer Freitext-Dosierung nicht darstellbar."],
    "[Maximalmenge]": [
        "maxDosePerPeriod.<Unterfeld> ist für die Textgenerierung erforderlich.",
        "maxDosePerPeriod.denominator muss 1 d oder 24 h sein.",
        "Eine Maximalmenge setzt asNeededBoolean = true voraus.",
        "Eine Maximalmenge ist nur bei reiner Bedarfsmedikation zulässig, nicht zusammen mit einem strukturierten "
        "Rhythmus.",
        "Eine Maximalmenge ist bei einer Freitext-Dosierung nicht darstellbar."],
    "dieselbe Uhrzeit, derselbe Tagesabschnitt": [
        "Doppelte Belegung der Uhrzeit '{zeit}' mit unterschiedlicher Dosis.",
        "Doppelte Belegung des Tagesabschnitts '{code}' mit unterschiedlicher Dosis.",
        "Doppelte Belegung des Wochentags '{code}' mit unterschiedlicher Dosis.",
        "Doppelte Belegung der Kombination aus Wochentag '{code}' und Zeit-/Tagesabschnitt '{zeit}' mit "
        "unterschiedlicher Dosis."],
    "Uhrzeiten und Tagesabschnitte gemischt": [
        "Wochentags-Kombinationen mit Uhrzeiten und mit Tagesabschnitten dürfen nicht gemischt werden."],
    "mehr als ein `Dosage`-Element im Schema für wiederkehrende Intervalle": [
        "Wiederkehrende Intervalle erlauben genau ein Dosage-Element."],
}


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
    def test_every_spec_condition_has_exactly_one_entry(self):
        conditions = spec_abort_conditions()
        self.assertGreater(len(conditions), 20)
        for condition in conditions:
            with self.subTest(condition):
                self.assertRegex(condition, r"\(Grund [123]\)", "Eintrag ohne Grund")
                keys = [key for key in ABORT_CONDITIONS if condition.startswith(key)]
                self.assertEqual(len(keys), 1, f"Eintrag ohne eindeutige Zuordnung in ABORT_CONDITIONS: {condition}")
        for key in ABORT_CONDITIONS:
            with self.subTest(key):
                self.assertEqual(sum(condition.startswith(key) for condition in conditions), 1,
                                 f"Kein eindeutiger Eintrag in der Fehlerliste beginnt mit: {key}")

    def test_every_script_message_belongs_to_a_condition(self):
        patterns = [template_pattern(template) for templates in ABORT_CONDITIONS.values() for template in templates]
        for name, message in script_messages().items():
            with self.subTest(name):
                self.assertTrue(any(pattern.match(message) for pattern in patterns),
                                f"Meldung gehört zu keiner Abbruchbedingung: {message}")

    def test_every_condition_is_triggered_by_a_vector(self):
        messages = list(script_messages().values())
        for key, templates in ABORT_CONDITIONS.items():
            for template in templates:
                with self.subTest(condition=key, message=template):
                    pattern = template_pattern(template)
                    self.assertTrue(any(pattern.match(message) for message in messages),
                                    f"Kein Vektor löst diese Meldung aus: {template}")


if __name__ == "__main__":
    unittest.main()
