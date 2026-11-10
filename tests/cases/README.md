# Testvektoren der Textgenerierung

Die JSON-Dateien in diesem Verzeichnis enthalten Eingaben und das erwartete Ergebnis des in [dosage-text-algorithm-spec.md](../../dosage-text-algorithm-spec.md) festgelegten Algorithmus. Sie sind unabhängig von der Programmiersprache und lassen sich gegen jede Implementierung ausführen. Die Spezifikation ist führend; weicht ein Vektor von ihr ab, ist der Vektor falsch.

## Format

Jede Datei enthält einen Abschnitt mit seinen Fällen. Schlüssel, Dateinamen und Bezeichnungen sind englisch:

```json
{
  "section": "Day-of-week schema",
  "cases": [
    {
      "name": "day of week: one day",
      "dosages": [
        {
          "doseAndRate": [{ "doseQuantity": { "value": 1, "unit": "Stück" } }],
          "timing": { "repeat": { "dayOfWeek": ["mon"] } }
        }
      ],
      "expect": { "text": "montags — je 1 Stück" }
    }
  ]
}
```

| Feld | Bedeutung |
|------|-----------|
| `section` | Überschrift der Datei |
| `name` | Bezeichnung des Falls, über alle Dateien eindeutig |
| `dosages` | Liste der `Dosage`-Elemente. Der Fall gilt für `MedicationRequest`, `MedicationDispense` (jeweils unter `dosageInstruction`) und `MedicationStatement` (unter `dosage`) |
| `resource` | Vollständige Ressource, anstelle von `dosages`, wenn der Fall die Ressource selbst betrifft (etwa einen nicht unterstützten `resourceType`) |
| `expect.text` | Erwarteter Text, zeichengenau |
| `expect.error` | Erwarteter Abbruch mit der Meldung aus dem Abschnitt „Fehler und Validierung“ der Spezifikation |

Ein Fall enthält entweder `dosages` oder `resource` und entweder `expect.text` oder `expect.error`.

## Ausführen

Für jeden Fall mit `dosages` wird je Ressourcentyp eine Ressource aus `resourceType` und der Liste gebildet, ein Fall mit `resource` wird unverändert übergeben. Das Ergebnis der Implementierung wird mit `expect` verglichen.

Zahlen sind mit ihrer Genauigkeit zu lesen: `2.50` ist nicht `2.5`, und der erwartete Text lautet `2,50`. Ein JSON-Parser, der Dezimalzahlen als binäre Gleitkommazahl liest, besteht diese Fälle nicht.

Für das Python-Skript führt [tests/test_cases.py](../test_cases.py) die Vektoren aus:

```
python -m unittest tests/test_cases.py
```
