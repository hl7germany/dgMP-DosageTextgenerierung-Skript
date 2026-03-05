# Changelog

Alle relevanten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

## [1.0.2] - 2026-03-05

### Added
- GitHub Actions Workflows für CI, manuelles Release und tag-basiertes Release.
- Regressionstests für stabile Sortierung der Dosage-Ausgabe.

### Changed
- Deterministische Sortierung für `DayOfWeek + TimeOfDay`, `DayOfWeek + when`, `TimeOfDay` und `Interval + Time/when`.
- Doppelte Einträge zum gleichen Zeitpunkt werden nacheinander ausgegeben (ohne Summierung) in den entsprechenden Schemata.

### Fixed
- `4-Schema`: doppelte `when`-Belegung wird als Fehler (`ValueError`) behandelt.
- `Interval + Time/when`: bei fehlenden gültigen Zeitkeys kein hängender Doppelpunkt mehr.
- Docstrings/Beispiele an aktuelle Ausgabeformate angepasst.

Full Changelog: [1.0.1...1.0.2]

## [1.0.1] - 2025-12-01

### Changed
- fix: update dosage formatting to use German decimal separator, add weekday to every dosage, consistant usage of semikolon and colons by @patrick-werner in #5

Full Changelog: [1.0.0...1.0.1]

## [1.0.0] - 2025-09-17

### Added
- Initiale veröffentlichte Version.

[1.0.2]: https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/releases/tag/1.0.2
[1.0.1]: https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/releases/tag/1.0.1
[1.0.0]: https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/releases/tag/1.0.0
[1.0.1...1.0.2]: https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/compare/1.0.1...1.0.2
[1.0.0...1.0.1]: https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/compare/1.0.0...1.0.1
