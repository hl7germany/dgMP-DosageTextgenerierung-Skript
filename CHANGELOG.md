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

## [Unreleased]

### Algorithmus

#### Changed

- Das 4‑Schema erhält wie das Uhrzeiten-Schema den Marker `täglich`: Aus `1-0-2-0 Stück` wird `täglich: 1-0-2-0 Stück`, mit Zeitrahmen `für 5 Tage täglich: 1-1-1-1 Kapseln`, bei Bedarf `bei Bedarf: täglich 1-0-2-0 Stück`. Die ausgeschriebene Segmentform bei variabler Dosis erhält denselben Marker (`täglich: morgens — je 1 bis 2 Stück`). Das Muster allein ließ offen, dass es an jedem Tag gilt; in der HD-Studie war die Form mit `täglich` nachweislich besser verständlich. Wochentags-Kombinationen (`montags 1-0-1-0 Stück`) bleiben unverändert.
- Freitext wird unverändert übernommen, auch führender und abschließender Leerraum; der bisherige Trim entfällt. `FreeTextMatchesRenderedText` verlangt exakte Gleichheit mit `Dosage.text` — ein getrimmter Text konnte diese Invariante für Texte mit Rand-Leerraum nie erfüllen.
- Der Algorithmus prüft keine Wertebereiche mehr. Vorbedingung der Textgenerierung ist eine gegen das Profil validierte Ressource; der Algorithmus bricht nur noch ab, wenn der Text nicht bildbar wäre oder eine Angabe unterschlagen beziehungsweise mehrdeutig wiedergeben würde. Der Abschnitt „Fehler und Validierung" benennt diese Gründe; als dritter kommt ein falscher JSON-Datentyp hinzu, weil eine validierte Ressource ihn nicht enthält und der Algorithmus ihn nicht umdeuten darf. Konkret entfallen:
  - `doseQuantity.value`, `doseRange.high.value` und `doseRange.low.value` müssen nicht mehr größer als `0` beziehungsweise nicht negativ sein. `je 0 Stück` ist ein eindeutiger Text; `DosageDoseValuePositive` ist Sache des Profils. 1.0.x hatte Dosis `0` ebenfalls gerendert.
  - `boundsDuration.value` und der Mindestabstand müssen nicht mehr größer als `0` sein (`TimingValuesPositive`, `DosageLimitsPositive`). Nicht numerische Werte führen weiterhin zum Abbruch, jetzt mit `… muss numerisch sein.`
  - `period` und `periodMax` waren schon bisher nicht auf ihren Wertebereich geprüft; durch die Korrektur der Kurzformen werden negative Werte jetzt sichtbar (`alle 1 bis -2 Tage` statt `täglich`). Ein Nenner der Maximalmenge außerhalb von `1 d`/`24 h` — auch `-24 h` — bricht weiterhin ab, weil es dafür keine Wortform gibt; das ist kein Wertebereich, sondern „nicht bildbar".
  - `doseRange.low.unit` ist nicht mehr verpflichtend: Die Einheit erscheint nur einmal im Text und stammt aus `high.unit`. Ist `low.unit` vorhanden und weicht ab, bricht der Algorithmus weiterhin ab.
  - Im 4‑Schema führt eine doppelte Belegung desselben Tagesabschnitts nur noch bei **unterschiedlicher** Dosis zum Abbruch (`Doppelte Belegung des Tagesabschnitts '{code}' mit unterschiedlicher Dosis.`), wie in allen anderen Schemata. Dieselbe Dosis zweimal ergibt denselben Text.
- Eine explizit mit `0` belegte Position des 4‑Schemas gilt als belegt. In der ausgeschriebenen Segmentform bleibt sie erhalten (`täglich: morgens — je 0 Stück, abends — je 1 bis 2 Stück`); bisher wäre sie mit einer nicht belegten Position verwechselt worden und entfallen. Auch die Duplikatprüfung der Wochentags-Kombination unterscheidet jetzt zwischen `0` und „nicht belegt".
- Angaben, die der Text bisher stillschweigend unterschlug, führen jetzt zum Abbruch — alle Fälle bestanden schon vor 2.0.0‑ballot und widersprachen dem Grundsatz, dass der Algorithmus abbricht, statt eine Angabe zu übergehen:
  - Dieselbe Uhrzeit (`HH:MM`) mit unterschiedlicher Dosis im Uhrzeiten-Schema und in der Wochentags-Kombination (`täglich: 08:00 Uhr — je 1 Stück, 08:00 Uhr — je 2 Stück` war mehrdeutig und reihenfolgeabhängig). Mit derselben Dosis wird die Uhrzeit nur einmal ausgegeben.
  - Wochentags-Kombination mit Uhrzeiten **und** Tagesabschnitten über mehrere Elemente: Bisher entschied das erste Element über den Untertyp, eine Gabe des anderen entfiel (`mon 08:00 (1 Stück)` + `mon MORN (2 Stück)` → `montags 08:00 Uhr — je 1 Stück`).
  - Mehr als ein `Dosage`-Element im Intervall-Schema: Bisher wurde nur das erste ausgegeben.
  - Mindestabstand bei Wochentagsschemata: Die Prüfung „nur ohne strukturierten Rhythmus" sah den Rhythmus im Zwischenteil des Textes nach, den Wochentagsschemata nicht haben, und ließ `bei Bedarf: im Abstand von mindestens 4 Stunden montags — je 1 Stück` durch. Maßgeblich ist jetzt das `timing`.
  - Einnahmeanlass, Mindestabstand und Maximalmenge ohne `asNeededBoolean = true` wurden stillschweigend verworfen; die Spezifikation sagte für die Maximalmenge sogar „wird gar nicht gelesen". Jetzt Abbruch — eine `modifierExtension` darf nie ignoriert werden, und alle drei sind Angaben der Ressource.
  - Abweichende Dosis-Einheit eines weiteren Elements im 4‑Schema, Wochentags-Schema und in der Wochentags-Kombination mit Tagesabschnitten (`MORN 1 Stück` + `EVE 2 mg` → `täglich: 1-0-2-0 Stück`). `DosageDoseUnitSameCode` vergleicht nur den Code, nicht die Anzeigeeinheit.
  - `frequencyMax` in der Intervall-Kombination (Regel 7) wurde unterschlagen; jetzt greift keine Regel und der Algorithmus bricht ab, wie es die Spezifikation seit 2.0.0‑ballot für konkrete Zeitpunkte verlangt.
  - „Dieselbe Dosis" in den Duplikatprüfungen bedeutet dieselbe Textdarstellung: `1` und `1,0` sind verschieden. Bisher galten sie numerisch als gleich, der spätere Wert überschrieb den ersten, und der Text (`1-0-0-0` oder `1,0-0-0-0`) hing von der Reihenfolge der Elemente ab.

#### Fixed

- Die Kurzformen `täglich`, `wöchentlich` und `monatlich` gelten nur noch für eine feste Periode von `1` ohne `periodMax`. Bisher fiel bei `period = 1` mit `periodMax` die Obergrenze weg: Aus `frequency = 1`, `period = 1`, `periodMax = 3`, `periodUnit = d` wurde `täglich` statt `alle 1 bis 3 Tage`. Bei einer Frequenz größer als `1` entsprechend `2 x alle 1 bis 3 Tage` statt `2 x täglich`.
- Widersprüche in der Spezifikation beseitigt. Das festgelegte Verhalten ändert sich nicht; die Referenzimplementierung setzte es bereits so um.
  - Schritt 8 des Gesamtalgorithmus verlangte bei Bedarf noch einen Großbuchstaben am Textanfang. Seit 2.0.0-ballot ist jeder erzeugte Text ein kleingeschriebenes Fragment.
  - Zwei Beispiele im Schema für Bedarfsmedikation kombinierten eine Maximalmenge mit Uhrzeiten beziehungsweise einem Intervall; das führt seit 2.0.0-ballot zum Abbruch. Sie zeigen jetzt den strukturierten Bedarf ohne Maximalmenge. Die Regel, nach der die Maximalmenge hinter dem letzten von mehreren Segmenten steht, entfällt: Mehrere Segmente setzen einen Rhythmus voraus, die Maximalmenge schließt ihn aus.
  - Der Abbruch „Mindestabstand zusammen mit einem strukturierten Rhythmus" fehlte in der Fehlerliste; er ist ergänzt. Die Meldungen zu Mindestabstand und Maximalmenge schreiben `zulässig` statt `zulaessig` — das Zeichenrepertoire verlangt die NFC-Umlaute auch in Meldungen.
  - Das Zeichenrepertoire behauptete, der gesamte Text sei NFC-normalisiert, zugleich bleiben übernommene Input-Teile ausdrücklich unverändert. Jetzt: Die erzeugten Wortbestandteile sind NFC; der Gesamttext ist es genau dann, wenn es der Input ist.
  - Die Spezifikation nannte die Invarianten `MindestabstandOnlyPureAsNeeded` und `MindestabstandUnitMatchesCode`; im IG heißen sie `MinimumIntervalOnlyPureAsNeeded` und `MinimumIntervalUnitMatchesCode`.
  - Die Einleitung nannte als aktuelle Version `2.0.0`, der Abschnitt Versionierung `2.0.0-ballot`; beide sagen jetzt `2.0.0-ballot`.
  - Die Normalisierung erfasst jedes Unicode-Leerraumzeichen (auch U+00A0) aus übernommenen Feldern; die Aussage „weder ersetzt noch normalisiert" gilt für die übrigen Zeichen. Bisher widersprachen sich beide Sätze.
  - Doppelpunkt-Regel präzisiert: Zeitrahmen und Intervall teilen sich einen Doppelpunkt; bei Bedarfsmedikation steht das Intervall rechts davon. Die reine Bedarfsdosierung kann keinen Zeitrahmen tragen (er liegt in `timing.repeat`); das Muster erweckte einen anderen Eindruck.
  - Die vom Algorithmus nicht gelesenen Felder verweisen auf die „Liste der aktuell nicht unterstützten Dosierkonfigurationen", wie der IG sie nennt, nicht mehr auf „zukünftig unterstützte".
- Jedes gelesene Feld muss den JSON-Datentyp seines FHIR-Typs haben (neuer Schritt 3 des Gesamtalgorithmus); ein falscher Typ führt zum Abbruch statt zu stillschweigend falschem Text. Bisher wurde nur bei einigen Feldern geprüft, und die Lücken verfälschten den Text:
  - Numerische Strings als Dosiswert (`"value": "2"`) wurden akzeptiert, aber nicht wie Zahlen formatiert: `"2"` kippte das 4‑Schema in die ausgeschriebene Form (`morgens — je 2 Stück` statt `2-0-0-0 Stück`), `"1.5"` ergab `je 1.5 Stück` ohne Dezimalkomma. Die Spezifikation hatte numerische Strings ausdrücklich zugelassen; FHIR `decimal` ist im JSON eine Zahl.
  - `period = "1"` (String) wurde nicht als Tagesmuster erkannt und ergab `alle 1 Tage` statt `täglich`; `period = true` ergab `alle 1 Stunde`.
  - `frequency = "2"` und `frequency = 2.5` wurden ausgegeben, obwohl `positiveInt` eine ganze Zahl verlangt; `frequency = true` zählte als `1`.
  - `asNeededBoolean = "true"` galt nicht als Bedarf: Mit Timing wurde der Text ohne `bei Bedarf` erzeugt — das Bedarfskennzeichen fehlte.
  - `doseQuantity.unit = 5` erschien als `1-0-0-0 5`.
  - `dayOfWeek = "mon"` (String statt Liste) ergab `m — …; o — …; n — …`.
  - Nicht-String in `text` oder `patientInstruction` und ein Objekt statt Liste in `doseAndRate` führten zu einem Python-Laufzeitfehler statt zu `ValueError`.
- Ein `dayOfWeek`-Code außerhalb der Wochentags-Tabelle führt zum Abbruch (`Nicht unterstützter Wochentag (dayOfWeek): '{code}'.`), wie bei `when`. Bisher erschien er roh im Text (`xyz — je 1 Stück`).
- Zahlen werden mit der Genauigkeit der Ressource ausgegeben (`1.0` → `1,0`, `2.50` → `2,50`), wie FHIR es für `decimal` verlangt — Genauigkeit einschließlich nachfolgender Nullen trägt Bedeutung und ist auch für die Darstellung zu erhalten. Die bisherige Regel `1.0` → `1` entfällt. Exponentialschreibweise aus der Ressource wird als Dezimalzahl ausgegeben (`1e-2` → `0,01`). Bisher hing die Darstellung vom JSON-Parser und der Float-Darstellung der Implementierung ab; zwei konforme Implementierungen konnten für dieselbe Ressource verschiedene Texte liefern. Die Referenzimplementierung liest JSON jetzt mit `parse_float=Decimal`.
- Der Fehlerlisten-Eintrag „Intervall-Kombination ohne `period` oder `periodUnit`" ist gestrichen. Der Fall ist unerreichbar: Die Schema-Erkennung verlangt beide Schlüssel, die Typprüfung einen numerischen Wert.
- `boundsPeriod` akzeptiert wie FHIR beliebig viele Sekundenbruchteile und die Schaltsekunde `60`; `timeOfDay` ebenfalls `60`. Bisher brach die Referenzimplementierung unter Python 3.10 bei einer oder sieben Bruchteilstellen ab (`datetime.fromisoformat` versteht dort nur drei oder sechs), obwohl Spezifikation und FHIR den Wert erlauben. Sekunden werden ohnehin nicht dargestellt.
- Die Fehlerliste nennt die Meldungen zu `boundsDuration`, `boundsPeriod`, `maxDosePerPeriod` und zum Mindestabstand wörtlich und legt die Pfadkonvention fest (`[]` für Listenelemente, `Dosage` und `dosageInstruction`/`dosage` oberhalb des Elements).
- Ein leeres `doseRange.low` (`{}`) gilt als vorhanden und bricht mit `doseRange.low.value ist für die Textgenerierung erforderlich.` ab; bisher wurde es wie ein fehlendes `low` behandelt (`je bis zu 2 Stück`).
- Die Fehlerliste nannte für nicht numerische Werte von `boundsDuration.value` und beim Mindestabstand Meldungen, die seit der Typprüfung (Schritt 3) nicht mehr entstehen; dort greift bereits `timing.repeat.boundsDuration.value muss numerisch sein.` beziehungsweise `modifierExtension[].valueDuration.value muss numerisch sein.`.

### Referenzimplementierung und Repository

#### Added

- Testfälle für `period = 1` mit `periodMax` in `d`, `wk` und `mo`.
- Testfälle für strukturierten Bedarf mit Uhrzeiten und mit Intervall sowie für die Fehlermeldungen zum Mindestabstand.
- Testfälle für Dosis `0`, negative Dosis, `boundsDuration = 0`, fehlendes und abweichendes `doseRange.low.unit`, doppelte `when`-Belegung mit gleicher Dosis sowie explizite `0` in der ausgeschriebenen Form und in der Duplikatprüfung.
- `tests/test_spec_examples.py`: Jedes Textbeispiel der Spezifikation wird als FHIR-Ressource nachgebaut und muss zeichengenau erzeugt werden; jeder Eintrag der Fehlerliste hat einen Fall mit der wörtlichen Meldung. Ein Meta-Test liest die Meldungen aus der Spezifikation und scheitert, wenn eine davon von keinem Fall erzeugt wird oder ein Fall eine Meldung erzeugt, die dort fehlt. So können Spezifikation und Referenzimplementierung nicht mehr unbemerkt auseinanderlaufen.

#### Fixed

- Die Fehlermeldungen zum Mindestabstand nennen wie in der Spezifikation festgelegt `MinimumIntervalBetweenAdministrations.valueDuration` statt des alten Namens `MindestabstandZwischenGaben.valueDuration`.
- Kommentare, die noch die Großschreibung bei Bedarf und den entfallenen Baustein `, mit mindestens … Abstand` beschrieben, sind korrigiert.

#### Changed

- `tests/test_regression_ordering.py`: `if __name__ == "__main__"` stand vor drei Testklassen; beim Direktaufruf der Datei liefen sie nicht. Der Block steht jetzt am Dateiende.
- Ein Test prüfte die ausgeschriebene 4‑Schema-Form nur mit `assertIn`; er vergleicht jetzt die vollständige Ausgabe. Ein Testname, der noch „0 nur als Untergrenze zulässig" behauptete, ist umbenannt.

#### Removed

- Unerreichbare Zweige: die Prüfung auf fehlendes `period`/`periodUnit` in der Intervall-Kombination, der Fallback in der Wochentags-Kombination für „weder `timeOfDay` noch `when`" sowie die Behandlung einer fehlenden Dosis-Einheit in vier Ausgabestellen — die Einheit ist Pflicht, `_extract_dose_quantity` bricht ohne sie ab.
- Sechs doppelte Tests in `tests/test_regression_ordering.py` (Ressourcentyp, `tim-10`, Hinweis, `MedicationStatement`, Duplikat im 4‑Schema, Maximalmenge in 24 Stunden); dieselben Fälle prüfen `tests/test_medication_dosage_to_text.py` und `tests/test_spec_examples.py` genauer.

## [2.0.0-ballot] - 2026-08-30

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
