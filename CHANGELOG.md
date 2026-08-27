# Changelog

Die Versionsnummern in dieser Datei sind **Algorithmus-Versionen**: sie bezeichnen
den in [dosage-text-algorithm-spec.md](dosage-text-algorithm-spec.md) festgelegten
Algorithmus, nicht den Stand dieses Repositories. Eine eigene Implementierung
trägt dieselbe Nummer, sobald sie diese Spezifikation umsetzt, und gibt sie als
`algorithmVersion` weiter.

Daraus folgt für jeden Eintrag:

- Abschnitt **Algorithmus** — Änderungen an der Spezifikation. Sie sind für jede
  Implementierung verbindlich und nur sie rechtfertigen eine neue Versionsnummer.
- Abschnitt **Referenzimplementierung und Repository** — Änderungen an Skript,
  Tests oder CI, die das festgelegte Verhalten nicht berühren. Sie erscheinen
  unter der Version, mit der sie ausgeliefert wurden, begründen aber keine.

Ändert sich nur die Referenzimplementierung, bleibt die Versionsnummer stehen.

## [2.0.0] - tbd

### Algorithmus

#### Added

- Normative Spezifikation [dosage-text-algorithm-spec.md](dosage-text-algorithm-spec.md). Sie ist gegenüber der Referenzimplementierung führend; weicht das Skript ab, gilt die Spezifikation.
- Abschnitt „Legacy-Angaben" in der Spezifikation: `hatZulaessigeLegacyFelder` und `istTagesmuster` beschreiben denselben Sachverhalt für unterschiedliche Schemata und sind nun gemeinsam erklärt, samt Herkunft der Felder und Abgrenzung zu den Schemata, in denen sie konstituierend sind.
- Blockquotes in der Spezifikation stehen nur noch für Unverbindliches — Orientierung, Hintergrund, Verweise. Sieben normative Regeln, die bisher als eingerückter Hinweis erschienen, sind Fließtext; das Intro benennt die Konvention.
- Schema „Kombination von Zeitintervallen": eine nicht tägliche Periode (`d`, `wk` oder `mo`) zusammen mit `when` oder `timeOfDay`. Damit sind wöchentliche und monatliche Rhythmen mit konkreten Zeitpunkten abbildbar.

#### Changed

- Enthält eine Ressource mehrere `Dosage`-Elemente, muss jedes zu demselben Schema führen; andernfalls bricht der Algorithmus ab. Bisher bestimmte allein das erste Element das Schema, und ein abweichendes späteres Element entfiel stillschweigend — aus „morgens 1 Stück" und „montags 2 Stück" wurde `1-0-0-0 Stück`.
- Eine variable Frequenz (`frequencyMax`) oder Periode (`periodMax`) führt in den täglichen Schemata mit `when` oder `timeOfDay` jetzt zum Abbruch. Bisher wurde sie dort stillschweigend übergangen — `when = MORN` mit `frequencyMax = 3` ergab `1-0-0-0 Stück` und unterschlug die Spanne. Das Profil verbietet die Kombination über `TimingOnlyOneType`; die Schema-Erkennung bildet diese Bedingung jetzt vollständig ab.
- Eine Maximalmenge (`maxDosePerPeriod`) ist nur bei einer **reinen** Bedarfsdosierung zulässig (`asNeededBoolean = true` ohne `timing`); zusammen mit einem strukturierten Rhythmus bricht der Algorithmus ab. Ein Rhythmus legt bereits fest, wie viel im Bezugszeitraum angewendet wird.
- Ein Mindestabstand zwischen zwei Gaben ist nur bei einer **reinen** Bedarfsdosierung zulässig (`asNeededBoolean = true` ohne `timing`). Tritt er zusammen mit einem strukturierten Rhythmus auf, bricht der Algorithmus ab. Der bisherige Baustein `, mit mindestens {Wert} {Einheit} Abstand` entfällt ersatzlos: Ein Rhythmus legt den Abstand zwischen zwei Gaben bereits fest, `alle 8 Stunden, mit mindestens 6 Stunden Abstand` ließ offen, welche Angabe gilt.
- Die kanonische URL der Extension für den Mindestabstand lautet `…/StructureDefinition/MinimumIntervalBetweenAdministrations` statt `…/MindestabstandZwischenGaben`.
- Wochentagsschemata dulden `frequency` sowie das redundante Paar `period = 1`, `periodUnit = wk` als Legacy-Angaben; sie ändern den erzeugten Text nicht. Jede andere Periode ist mit `dayOfWeek` nicht mehr kombinierbar.
- Eine variable Frequenz (`frequencyMax`) ist der reinen Intervallangabe vorbehalten. Konkrete Zeitpunkte und Wochentage legen die Zahl der Gaben bereits fest.
- Jeder erzeugte Text ist durchgehend ein kleingeschriebenes Fragment. Die Großschreibung des ersten Zeichens bei Bedarfsmedikation und die großgeschriebenen `boundsPeriod`-Literale entfallen; die Schreibweise am Satzanfang entscheidet das anzeigende System. Freitext wird weiterhin unverändert durchgereicht.
- `doseQuantity.value` und `doseRange.high.value` müssen größer als `0` sein; `0` bleibt ausschließlich als `doseRange.low.value` zulässig — als Untergrenze einer variablen Dosis wie „0 bis 2 Stück".
- Nicht numerische Dosiswerte werden mit `<Feld> muss numerisch sein.` abgewiesen statt unverändert in den Text übernommen; numerische Strings werden wie Zahlen geprüft.
- Doppelte Belegung desselben Zeitpunkts mit unterschiedlicher Dosis führt schemaübergreifend zum Abbruch.


### Referenzimplementierung und Repository

#### Added

- Unit-Tests für die Textgenerierung (`tests/test_medication_dosage_to_text.py`).

#### Removed

- `MindestabstandIdentical` aus der Aufzählung der Invarianten, die die Konsistenz der Rahmen-Angaben über mehrere `Dosage`-Elemente sichern. Sie ist nicht erreichbar: Ein Mindestabstand setzt eine reine Bedarfsdosierung voraus, und dafür erlaubt `AsNeededSingleDosageOnly` genau ein `Dosage`-Element.

#### Changed

- Release läuft über `gh release`; die beiden Release-Workflows entfallen. Bei einem Tag-Push prüft die CI, dass `__version__` mit dem Tag übereinstimmt — beide Angaben landen als `algorithmVersion` beim Konsumenten und dürfen nicht auseinanderlaufen.
- CI testet nur noch die älteste und die neueste unterstützte Python-Version. Das Skript nutzt ausschließlich die Standardbibliothek.

#### Fixed

- `tests/test_medication_dosage_to_text.py` konnte das Modul nicht laden und ließ dadurch die gesamte Test-Discovery und damit jeden CI-Lauf scheitern.
- Der Tag-Release-Workflow lief bei jedem Branch-Push und scheiterte nach 0 Sekunden ohne Job, weil seine Tag-Muster `*.*.*+*` und `*.*.*-*+*` das Sonderzeichen `+` unescaped enthielten.
- Der Syntax-Check deckte `tests/test_medication_dosage_to_text.py` nicht ab; er prüft jetzt das gesamte `tests/`-Verzeichnis.
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
