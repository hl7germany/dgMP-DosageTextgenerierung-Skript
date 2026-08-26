# Changelog

Alle relevanten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

## [2.0.0] - 2026-08-26

### Added
- Normative Algorithmusspezifikation `dosage-text-algorithm-spec.md`; sie ist gegenüber der Referenzimplementierung führend.
- Schema „Kombination von Zeitintervallen“: eine nicht tägliche Periode (`d`, `wk` oder `mo`) zusammen mit `when` oder `timeOfDay`.
- Unit-Tests für die Textgenerierung (`tests/test_medication_dosage_to_text.py`).

### Changed
- Wochentagsschemata dulden `frequency` sowie das redundante Paar `period = 1`, `periodUnit = wk` als Legacy-Angaben; sie ändern den erzeugten Text nicht. Jede andere Periode ist mit `dayOfWeek` nicht mehr kombinierbar.
- Eine variable Frequenz (`frequencyMax`) ist der reinen Intervallangabe vorbehalten.
- `doseQuantity.value` und `doseRange.high.value` müssen größer als 0 sein; `0` bleibt ausschließlich als `doseRange.low.value` zulässig.
- Doppelte Belegung desselben Zeitpunkts mit unterschiedlicher Dosis führt schemaübergreifend zum Abbruch.
- Nicht numerische Dosiswerte werden abgewiesen (`<Feld> muss numerisch sein.`) statt unverändert in den Text übernommen zu werden; numerische Strings werden wie Zahlen geprüft.

### Fixed
- `tests/test_medication_dosage_to_text.py` konnte das Modul nicht laden und ließ dadurch die gesamte Test-Discovery und damit die CI scheitern.
- Regressionstests kombinierten `dayOfWeek` mit `periodUnit = d`; zwei davon prüften dadurch nur noch die Schema-Erkennung statt der benannten Regel.

## [1.0.2] - 2026-03-05

### Added
- GitHub Actions Workflows für CI, manuelles Release und tag-basiertes Release.
- Regressionstests für stabile Sortierung der Dosage-Ausgabe.
- Zusätzliche Regressionstests für `DayOfWeek + when` (Merge über unterschiedliche Slots) und Validierungsfehler bei `when` ohne Dosis.

### Changed
- Deterministische Sortierung für `DayOfWeek + TimeOfDay`, `DayOfWeek + when`, `TimeOfDay` und `Interval + Time/when`.
- Doppelte Einträge zum gleichen Zeitpunkt werden nacheinander ausgegeben (ohne Summierung) in den entsprechenden Schemata.
- `DayOfWeek + when` merged wieder unterschiedliche `when`-Slots pro Tag in ein gemeinsames 4-Schema-Muster; echte Slot-Duplikate bleiben getrennte Einträge.
- Release-Ablauf stabilisiert: manuelles Release taggt den getesteten Commit und erstellt das GitHub-Release direkt; tag-basierter Flow bleibt für direkte Tag-Pushes erhalten.

### Fixed
- `4-Schema`: doppelte `when`-Belegung wird als Fehler (`ValueError`) behandelt.
- `when` ohne Dosisangabe führt jetzt schemaübergreifend zu einem Fehler (`ValueError`) in allen `when`-basierten Schemata.
- Bug behoben, bei dem ein `when` ohne Dosis fälschlich einen Slot belegte und dadurch Folgeeinträge blockierte.
- `Interval + Time/when`: bei fehlenden gültigen Zeitkeys kein hängender Doppelpunkt mehr.
- Docstrings/Beispiele an aktuelle Ausgabeformate angepasst.

Full Changelog: [1.0.1...1.0.2]

## [1.0.1] - 2025-12-01

### Changed
- fix: update dosage formatting to use German decimal separator, add weekday to every dosage, consistent usage of semikolon and colons by @patrick-werner in #5

Full Changelog: [1.0.0...1.0.1]

## [1.0.0] - 2025-09-17

### Added
- Initiale veröffentlichte Version.

[1.0.2]: https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/releases/tag/1.0.2
[1.0.1]: https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/releases/tag/1.0.1
[1.0.0]: https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/releases/tag/1.0.0
[1.0.1...1.0.2]: https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/compare/1.0.1...1.0.2
[1.0.0...1.0.1]: https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/compare/1.0.0...1.0.1
