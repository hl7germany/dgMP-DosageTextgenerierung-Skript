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

## [2.0.0-rc.2] - 2026-10-16

Release Candidate 2 für 2.0.0. Die Einträge beschreiben die Unterschiede zu 2.0.0-rc.1.

### Algorithmus

#### Changed

- Ein abweichender Einnahmerhythmus (`period`, `periodMax`, `periodUnit`) eines weiteren Elements der Intervall-Kombination führt nicht mehr zum Abbruch. Der Rhythmus zählt wie Zeitrahmen, Bedarfsangaben und Hinweis zu den Rahmen-Angaben, die aus dem ersten Element gelesen werden; ihre Gleichheit sichert das Profil (`TimingOnlyOneTimeForInterval`, das im Medication IG DE jetzt auch `periodMax` vergleicht). Die Meldung `Alle Dosage-Elemente einer Intervall-Kombination müssen denselben Einnahmerhythmus tragen.` entfällt. Für eine gegen das Profil validierte Ressource ändert sich kein Text.

### Referenzimplementierung und Repository

#### Added

- `tests/test_spec_examples.py`: Meta-Test für die Textbeispiele der Spezifikation. Jeder vollständige Beispieltext im Fließtext muss von einem Testfall exakt erzeugt werden, jeder Baustein (etwa `je 1 bis 2 Stück`) in einer erwarteten Ausgabe vorkommen; ein neues Beispiel ohne Testfall lässt den Test scheitern. Vier Beispiele, die bisher kein Test erzeugte, sind ergänzt.
- `tests/test_properties.py`: Eigenschaftstests über 1500 Zufallsressourcen mit festem Seed — Abbruch nur mit `ValueError`, Form des strukturierten Textes (eine Zeile, kein Rand-Leerraum, kein Großbuchstabe am Anfang), Unabhängigkeit von der Reihenfolge der `Dosage`-Elemente bei gleichen Rahmen-Angaben, gleicher Text mit Decimal- und float-Parser für Zahlen ohne nachfolgende Nullen.
- Testfälle für ungültige Kalenderdaten in `boundsPeriod`, unbekannte `when`-Codes in der Wochentags-Kombination, eine fremde `extension` neben dem Einnahmeanlass, dieselbe Dosis mehrfach im Wochentags-Schema und in der Wochentags-Kombination, eine leere `doseAndRate`-Liste, `timing` ohne `repeat` und eine Maximalmenge ohne Zähler.
- Testfälle für die Kommandozeile, über die der IG-Build das Skript aufruft: Aufruf ohne Argument, fehlende Datei, ungültiges JSON und Abbruch (`Fehler: …` auf stderr, Exit-Code 1, leere Ausgabe).

#### Removed

- Unerreichbare Zweige: die Prüfung auf eine leere Liste in zehn schemaspezifischen Generatoren und in der Schema-Erkennung (`generate_dosage_text` gibt bei leerer Liste vorher `""` zurück), leere Zwischenergebnisse in Uhrzeiten-, Wochentags- und Wochentags-Kombinations-Schema, der leere Text in der Normalisierung und die Kurzform `täglich` in der Intervall-Kombination (`1 d` ohne `periodMax` ist ein Tagesmuster und führt nie zu Regel 7).

## [2.0.0-rc.1] - 2026-10-15

Release Candidate für 2.0.0. Die Einträge beschreiben die Unterschiede zu 2.0.0-ballot; weitere Release Candidates beschreiben jeweils die Unterschiede zum vorigen.

### Algorithmus

#### Changed

- Das 4‑Schema erhält wie das Uhrzeiten-Schema den Marker `täglich`: Aus `1-0-2-0 Stück` wird `täglich: 1-0-2-0 Stück`, mit Zeitrahmen `für 5 Tage täglich: 1-1-1-1 Kapseln`, bei Bedarf `bei Bedarf, täglich: 1-0-2-0 Stück` (siehe den folgenden Eintrag zur Stellung des Intervalls bei Bedarf). Die ausgeschriebene Segmentform bei variabler Dosis erhält denselben Marker (`täglich: morgens — je 1 bis 2 Stück`). Das Muster allein ließ offen, dass es an jedem Tag gilt; in der HD-Studie war die Form mit `täglich` nachweislich besser verständlich. Wochentags-Kombinationen (`montags 1-0-1-0 Stück`) bleiben unverändert.
- Bei Bedarfsmedikation mit Intervall steht das Intervall wie ohne Bedarf links des Doppelpunkts, durch ein Komma vom Einnahmeanlass getrennt: `bei Kopfschmerzen, alle 8 Stunden: je 1 Stück` statt `bei Kopfschmerzen: alle 8 Stunden je 1 Stück`, `bei Bedarf, täglich: 08:00 Uhr — je 1 Stück` statt `bei Bedarf: täglich 08:00 Uhr — je 1 Stück`. Damit trennt der Doppelpunkt überall „wann und weshalb" von „was". Das Komma ist nötig, weil der Einnahmeanlass Freitext ist und auf eine Zahl enden kann (`bei Blutzucker über 250, 2 x täglich: …`). Reine Bedarfsdosierung und Bedarf mit Wochentagen sind nicht betroffen.
- Freitext wird unverändert übernommen, auch führender und abschließender Leerraum; der bisherige Trim entfällt. `FreeTextMatchesRenderedText` verlangt exakte Gleichheit mit `Dosage.text` — ein getrimmter Text konnte diese Invariante für Texte mit Rand-Leerraum nie erfüllen.
- Der Algorithmus prüft keine Wertebereiche mehr. Vorbedingung der Textgenerierung ist eine gegen das Profil validierte Ressource; der Algorithmus bricht nur noch ab, wenn der Text nicht bildbar wäre oder eine Angabe unterschlagen beziehungsweise mehrdeutig wiedergeben würde. Der Abschnitt „Fehler und Validierung" benennt diese Gründe; als dritter kommt ein falscher JSON-Datentyp hinzu, weil eine validierte Ressource ihn nicht enthält und der Algorithmus ihn nicht umdeuten darf. Konkret entfallen:
  - `doseQuantity.value`, `doseRange.high.value` und `doseRange.low.value` dürfen `0` sein: `je 0 Stück` ist ein eindeutiger Text; `DosageDoseValuePositive` ist Sache des Profils. 1.0.x hatte Dosis `0` ebenfalls gerendert. Ein negativer Dosiswert führt weiterhin zum Abbruch, weil er keine Anweisung darstellt; die Meldung lautet jetzt `<Feld> darf nicht negativ sein.` statt `… muss größer als 0 sein.`
  - `boundsDuration.value` und der Mindestabstand müssen nicht mehr größer als `0` sein (`TimingValuesPositive`, `DosageLimitsPositive`). Nicht numerische Werte führen weiterhin zum Abbruch, jetzt mit `… muss numerisch sein.`
  - `period` und `periodMax` waren schon bisher nicht auf ihren Wertebereich geprüft; durch die Korrektur der Kurzformen werden negative Werte jetzt sichtbar (`alle 1 bis -2 Tage` statt `täglich`). Ein Nenner der Maximalmenge außerhalb von `1 d`/`24 h` — auch `-24 h` — bricht weiterhin ab, weil es dafür keine Wortform gibt; das ist kein Wertebereich, sondern „nicht bildbar".
  - `doseRange.low.unit` ist nicht mehr verpflichtend: Die Einheit erscheint nur einmal im Text und stammt aus `high.unit`. Ist `low.unit` vorhanden und weicht ab, bricht der Algorithmus weiterhin ab.
  - Im 4‑Schema führt eine doppelte Belegung desselben Tagesabschnitts nur noch bei **unterschiedlicher** Dosis zum Abbruch (`Doppelte Belegung des Tagesabschnitts '{code}' mit unterschiedlicher Dosis.`), wie in allen anderen Schemata. Dieselbe Dosis zweimal ergibt denselben Text.
- Weil Dosis `0` jetzt dargestellt wird, gilt eine explizit mit `0` belegte Position des 4‑Schemas als belegt und ist von einer nicht belegten zu unterscheiden: In der ausgeschriebenen Segmentform bleibt sie als eigenes Segment erhalten (`täglich: morgens — je 0 Stück, abends — je 1 bis 2 Stück`), ebenso in der Duplikatprüfung der Wochentags-Kombination.
- Angaben, die der Text bisher stillschweigend unterschlug, führen jetzt zum Abbruch — alle Fälle bestanden schon vor 2.0.0‑ballot und widersprachen dem Grundsatz, dass der Algorithmus abbricht, statt eine Angabe zu übergehen:
  - Dieselbe Uhrzeit (`HH:MM`) mit unterschiedlicher Dosis im Uhrzeiten-Schema und in der Wochentags-Kombination (`täglich: 08:00 Uhr — je 1 Stück, 08:00 Uhr — je 2 Stück` war mehrdeutig und reihenfolgeabhängig). Mit derselben Dosis wird die Uhrzeit nur einmal ausgegeben.
  - Wochentags-Kombination mit Uhrzeiten **und** Tagesabschnitten über mehrere Elemente: Bisher entschied das erste Element über den Untertyp, eine Gabe des anderen entfiel (`mon 08:00 (1 Stück)` + `mon MORN (2 Stück)` → `montags 08:00 Uhr — je 1 Stück`).
  - Mehr als ein `Dosage`-Element im Intervall-Schema: Bisher wurde nur das erste ausgegeben.
  - Mindestabstand bei Wochentagsschemata: Die Prüfung „nur ohne strukturierten Rhythmus" sah den Rhythmus im Zwischenteil des Textes nach, den Wochentagsschemata nicht haben, und ließ `bei Bedarf: im Abstand von mindestens 4 Stunden montags — je 1 Stück` durch. Maßgeblich ist jetzt das `timing`.
  - Einnahmeanlass, Mindestabstand und Maximalmenge ohne `asNeededBoolean = true` wurden stillschweigend verworfen; die Spezifikation sagte für die Maximalmenge sogar „wird gar nicht gelesen". Jetzt Abbruch — eine `modifierExtension` darf nie ignoriert werden, und alle drei sind Angaben der Ressource.
  - `frequencyMax` in der Intervall-Kombination (Regel 7) wurde unterschlagen; jetzt greift keine Regel und der Algorithmus bricht ab, wie es die Spezifikation seit 2.0.0‑ballot für konkrete Zeitpunkte verlangt.
  - „Dieselbe Dosis" in den Duplikatprüfungen bedeutet dieselbe Textdarstellung von Wert und Einheit. Bisher verglich die Wochentags-Prüfung nur den Zahlenwert: `1 Stück` und `1 Tablette` am selben Tag galten als gleich, die zweite Einheit entfiel (`montags — je 1 Stück`). Mit der Genauigkeitsregel (siehe Fixed) sind außerdem `1` und `1,0` verschieden.
- Abweichende Dosis-Einheiten über mehrere Elemente werden wiedergegeben statt unterschlagen. Bisher übernahmen 4‑Schema, Wochentags-Schema und Wochentags-Kombination die Einheit des ersten Elements (`MORN 1 Stück` + `EVE 2 mg` → `1-0-2-0 Stück`). Jetzt trägt jedes Wochentags-Segment die Einheit seines Elements; das kompakte 4‑Schema-Muster wechselt bei verschiedenen Einheiten in die ausgeschriebene Form, wie bei einem variablen Wert: `täglich: morgens — je 1 Stück, abends — je 2 mg`. Verglichen wird die angezeigte Einheit, nicht der Code: Eine abweichende Anzeige bei gleichem Code (`Stück`/`Tablette`, beide KBV `1`) kann auf einen Fehler in einem Element hinweisen und bleibt sichtbar. Solche Ressourcen sind in 1.0.7 gültig (`DosageDoseUnitSameCode` vergleicht nur den Code); sie werden damit weiterhin gerendert, ohne Abbruch.
- Ein `comparator` in einer gelesenen `Quantity` (`doseQuantity`, `doseRange`, `maxDosePerPeriod`, `boundsDuration`, Mindestabstand) führt zum Abbruch (`<Feld>.comparator wird nicht unterstützt.`). Bisher wurde er stillschweigend verworfen: `maxDosePerPeriod.numerator.comparator = "<"` mit Wert `6` ergab `nicht mehr als 6 Stück pro Tag`, also eine andere Aussage als die Ressource. Für einen Vergleichsoperator ist keine Darstellung definiert. Profilkonformer Input enthält keinen `comparator`: Die Dosis ist eine `SimpleQuantity`, und der Medication IG 2.0.0 schließt ihn auch bei `maxDosePerPeriod`, `boundsDuration` und dem Mindestabstand aus, weil Bereiche und Obergrenzen eigene Elemente haben (`doseRange`, `maxDosePerPeriod`).
- Intervall-Kombination (Regel 7) über mehrere `Dosage`-Elemente:
  - Dieselbe Uhrzeit gilt wie in den anderen Schemata nach der dargestellten Form `HH:MM`. Bisher war der rohe `timeOfDay`-String der Schlüssel: `08:00` und `08:00:00` (oder `08:00:00.0`) mit unterschiedlicher Dosis ergaben `alle 2 Tage: 08:00 Uhr — je 1 Stück, 08:00 Uhr — je 2 Stück`, mit derselben Dosis zwei gleiche Segmente. Jetzt Abbruch beziehungsweise einmalige Ausgabe; die Meldungen sind dieselben wie im Uhrzeiten-Schema und im 4‑Schema (`Doppelte Belegung der Uhrzeit '{HH:MM Uhr}' …`, `Doppelte Belegung des Tagesabschnitts '{code}' …`), die bisherige Meldung `Doppelte Belegung des Zeit-Schlüssels …` entfällt.
  - Der Einnahmerhythmus wird aus dem ersten Element gelesen; weicht `period`, `periodMax` oder `periodUnit` eines weiteren Elements ab, bricht der Algorithmus ab (`Alle Dosage-Elemente einer Intervall-Kombination müssen denselben Einnahmerhythmus tragen.`). Bisher wurde der abweichende Rhythmus stillschweigend ersetzt: `period 2 d` + `period 3 d` → `alle 2 Tage: …`.
- Die Vorbedingungen von Einnahmeanlass, Mindestabstand und Maximalmenge (Bedarfskennzeichen; Mindestabstand und Maximalmenge nur ohne `timing`) werden in jedem `Dosage`-Element geprüft, nicht nur im ersten. Bisher hing das Ergebnis von der Reihenfolge ab: Ein Mindestabstand nur im zweiten Element wurde verworfen, in umgekehrter Reihenfolge führte er zum Abbruch. Die Prüfung läuft jetzt vor der Schema-Erkennung und damit auch für Freitext-Elemente (ein Einnahmeanlass ohne Bedarfskennzeichen an einem Freitext wurde bisher stillschweigend ignoriert); ein Mindestabstand ohne Bedarfskennzeichen und ohne `timing` meldet deshalb `Ein Mindestabstand setzt asNeededBoolean = true voraus.` statt `Die Dosierung entspricht keinem unterstützten Dosierungsschema.`
- Ein Mindestabstand oder eine Maximalmenge an einer Freitext-Dosierung führt zum Abbruch (`Ein Mindestabstand ist bei einer Freitext-Dosierung nicht darstellbar.`, `Eine Maximalmenge …`). Bisher wurde der Freitext allein ausgegeben und die Angabe verworfen — bei profilkonformem Input erreichbar, weil `MinimumIntervalOnlyPureAsNeeded` nur Bedarf ohne `timing` verlangt. Anhängen lässt sich nichts: `FreeTextMatchesRenderedText` verlangt exakte Gleichheit mit `Dosage.text`. `asNeededBoolean` und Einnahmeanlass an einer Freitext-Dosierung gehen weiterhin nicht in den Text ein; die Spezifikation sagt das jetzt ausdrücklich.
- Eine `modifierExtension` mit einer anderen URL als der des Mindestabstands führt zum Abbruch (`Nicht unterstützte modifierExtension: '{url}'.`). Bisher wurde sie stillschweigend ignoriert; eine modifierExtension verändert die Bedeutung des Elements und darf nach FHIR nicht übergangen werden. Bei profilkonformem Input nicht erreichbar.
- Ob vor dem Hinweis ein Punkt ergänzt wird, entscheidet der Text nach Entfernen abschließenden Leerraums; bisher ergab die Einheit `"Tbl. "` mit Hinweis `… je 1 Tbl.. Hinweis: …`.
- Eine Dosis-Einheit, die leer ist oder nur aus Leerraum besteht, gilt als fehlend und führt zum Abbruch; bisher ergab `"unit": "  "` den Text `alle 8 Stunden: je 1` ohne Einheit. Die Maximalmenge behandelte Leerraum schon so.
- Die Typprüfung (Schritt 3) erfasst nur Felder, die der Algorithmus liest: von `doseAndRate` den ersten Eintrag, von `extension`/`modifierExtension` neben der `url` nur die Werte der beiden bekannten Extensions. Bisher führte etwa eine fremde Extension mit einem String in `valueCodeableConcept` zum Abbruch, obwohl sie nicht gelesen wird; `system` wird nicht mehr geprüft.

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
  - Doppelpunkt-Regel präzisiert: Zeitrahmen und Intervall teilen sich einen Doppelpunkt (`für 7 Tage alle 2 Tage: …`). Die reine Bedarfsdosierung kann keinen Zeitrahmen tragen (er liegt in `timing.repeat`); das Muster erweckte einen anderen Eindruck.
  - Die vom Algorithmus nicht gelesenen Felder verweisen auf die „Liste der aktuell nicht unterstützten Dosierkonfigurationen", wie der IG sie nennt, nicht mehr auf „zukünftig unterstützte".
  - 4‑Schema und Wochentags-Schema behaupteten, `frequencyMax` und `periodMax` beeinflussten die Ausgabe nicht; nach der Schema-Erkennung führen sie dort zum Abbruch. Jetzt: Nur `frequency` und das redundante Paar `period = 1`/`periodUnit` bleiben ohne Einfluss.
  - Bei mehreren Freitext-Elementen „entfallen leere Werte" war unerreichbar: Ein leerer Text erfüllt keine Erkennungsregel, der Algorithmus bricht wegen Schema-Mix ab.
  - Die Fehlerliste schreibt die Meldung zu fehlendem `MinimumIntervalBetweenAdministrations.valueDuration.code` und zu `boundsPeriod.end` aus; bisher stand dort `….code …` beziehungsweise „für `.end` entsprechend", was der Meta-Test der Spezifikationsbeispiele nicht erfasste. Die Schema-Bezeichner der Meldung „Alle Dosage-Elemente müssen demselben Schema folgen" sind benannt.
  - Die Aggregationsregel nennt die Intervall-Kombination und die Vorbedingungsprüfung als Fälle, in denen der Algorithmus über alle Elemente prüft, statt sich auf Invarianten zu verlassen.
- Die Spezifikation beschränkt sich auf Festlegungen. Begründungen, Hinweise auf Profilregeln, Wiederholungen und Historie sind gestrichen oder in unverbindliche Blöcke verschoben. Neuer Abschnitt „Grundsätze“: Vorbedingung, die drei Abbruchgründe und die allgemeine Textregel (Kleinbuchstabe am Anfang, kein Schlusspunkt, eine Zeile) stehen einmal zentral; die Regeln verweisen mit „Grund 1“ bis „Grund 3“ darauf. Mindestabstand und Maximalmenge sind je einmal festgelegt, Bedarfs- und Freitextschema verweisen nur noch. Bisher unausgesprochenes Verhalten ist festgehalten: Prüfreihenfolge in Schritt 4 und bei der Schema-Gleichheit, `time`/`dateTime` als JSON-String, `null` als falscher Typ, Pfadkonvention der Meldungen unterhalb von `doseAndRate`, numerischer Vergleich bei Bedingungen gegenüber textuellem Vergleich bei Dosen und Rhythmen, zeichengenauer Einheitenvergleich, keine Zusammenfassung in der ausgeschriebenen Form und in der Intervall-Kombination, feste Ausgabe des Nenners der Maximalmenge, kein Abbruch bei abweichenden Rahmen-Angaben weiterer Elemente. Das festgelegte Verhalten ändert sich nicht; die Beispiele und Meldungen der Spezifikation sind unverändert.
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
- `boundsPeriod` akzeptiert wie FHIR beliebig viele Sekundenbruchteile und die Schaltsekunde `60`; `timeOfDay` ebenfalls `60`. Bisher lehnte die Referenzimplementierung die Schaltsekunde auf jeder Python-Version ab und brach unter Python 3.10 bei einer oder sieben Bruchteilstellen ab (`datetime.fromisoformat` versteht dort nur drei oder sechs), obwohl Spezifikation und FHIR den Wert erlauben. Sekunden werden ohnehin nicht dargestellt.
- Die Fehlerliste nennt die Meldungen zu `boundsDuration`, `boundsPeriod`, `maxDosePerPeriod` und zum Mindestabstand wörtlich und legt die Pfadkonvention fest (`[]` für Listenelemente, `Dosage` und `dosageInstruction`/`dosage` oberhalb des Elements).

### Referenzimplementierung und Repository

#### Added

- Testfälle für `period = 1` mit `periodMax` in `d`, `wk` und `mo`.
- Testfälle für strukturierten Bedarf mit Uhrzeiten und mit Intervall sowie für die Fehlermeldungen zum Mindestabstand.
- Testfälle für die Intervall-Kombination (Uhrzeit in verschiedenen Schreibweisen, abweichender Rhythmus, Tagesabschnitte vor Uhrzeiten), die Vorbedingungen der Bedarfs-Bausteine in jedem Element, `comparator`, Einheit aus Leerraum sowie die bisher nicht abgedeckten Meldungen zu `maxDosePerPeriod`, zum Mindestabstand, zu `boundsPeriod.end` und zur Zeiteinheit in `boundsDuration`.
- Testfälle für Dosis `0`, negative Dosis, `boundsDuration = 0`, fehlendes und abweichendes `doseRange.low.unit`, doppelte `when`-Belegung mit gleicher Dosis sowie explizite `0` in der ausgeschriebenen Form und in der Duplikatprüfung.
- `tests/test_spec_examples.py`: Jedes Textbeispiel der Spezifikation wird als FHIR-Ressource nachgebaut und muss zeichengenau erzeugt werden; jeder Eintrag der Fehlerliste hat einen Fall mit der wörtlichen Meldung. Ein Meta-Test liest die Meldungen aus der Spezifikation und scheitert, wenn eine davon von keinem Fall erzeugt wird oder ein Fall eine Meldung erzeugt, die dort fehlt. So können Spezifikation und Referenzimplementierung nicht mehr unbemerkt auseinanderlaufen.

#### Fixed

- Ein leeres `doseRange.low` (`{}`) gilt als vorhanden und bricht mit `doseRange.low.value ist für die Textgenerierung erforderlich.` ab, wie die Spezifikation es schon in 2.0.0‑ballot verlangte; bisher wurde es wie ein fehlendes `low` behandelt (`je bis zu 2 Stück`). Ein leeres `valueDuration` (`{}`) des Mindestabstands meldet entsprechend `….valueDuration.value …` statt `….valueDuration …`.
- Die Fehlermeldungen zum Mindestabstand nennen wie in der Spezifikation festgelegt `MinimumIntervalBetweenAdministrations.valueDuration` statt des alten Namens `MindestabstandZwischenGaben.valueDuration`.
- Kommentare, die noch die Großschreibung bei Bedarf und den entfallenen Baustein `, mit mindestens … Abstand` beschrieben, sind korrigiert.

#### Changed

- `tests/test_regression_ordering.py`: `if __name__ == "__main__"` stand vor drei Testklassen; beim Direktaufruf der Datei liefen sie nicht. Der Block steht jetzt am Dateiende.
- Ein Test prüfte die ausgeschriebene 4‑Schema-Form nur mit `assertIn`; er vergleicht jetzt die vollständige Ausgabe. Ein Testname, der noch „0 nur als Untergrenze zulässig" behauptete, ist umbenannt.

#### Removed

- Unerreichbare Zweige: die Prüfung auf fehlendes `period`/`periodUnit` in der Intervall-Kombination, Nicht-String-Prüfungen in `_format_datetime_german` und `_format_time_german`, der Fallback „kein Timing" im reinen Intervall sowie Typprüfungen in den Extraktoren für Dosis, Dauer und Maximalmenge — Schritt 3 prüft die Typen vorab —, der Fallback in der Wochentags-Kombination für „weder `timeOfDay` noch `when`" sowie die Behandlung einer fehlenden Dosis-Einheit in vier Ausgabestellen — die Einheit ist Pflicht, `_extract_dose_quantity` bricht ohne sie ab.
- Sechs doppelte Tests in `tests/test_regression_ordering.py` (Ressourcentyp, `tim-10`, Hinweis, `MedicationStatement`, Duplikat im 4‑Schema, Maximalmenge in 24 Stunden); dieselben Fälle prüfen `tests/test_medication_dosage_to_text.py` und `tests/test_spec_examples.py` genauer.

## [2.0.0-ballot] - 2026-08-30

Erste Version mit normativer Spezifikation. Die Einträge beschreiben die Unterschiede zum Skript 1.0.2; die Beispiele zeigen jeweils die Ausgabe von 1.0.2 und 2.0.0-ballot.

### Algorithmus

#### Added

- Normative Spezifikation [dosage-text-algorithm-spec.md](dosage-text-algorithm-spec.md). Sie ist gegenüber der Referenzimplementierung führend; weicht das Skript ab, gilt die Spezifikation.
- Bedarfsmedikation. Reine Bedarfsdosierung (`asNeededBoolean = true` ohne `timing`) mit optionalem Einnahmeanlass (`asNeededFor`, mehrere als Aufzählung), Mindestabstand (Extension `MinimumIntervalBetweenAdministrations`) und Maximalmenge (`maxDosePerPeriod`, Bezugszeitraum `24 h` oder `1 d`): `bei Kopfschmerzen: im Abstand von mindestens 4 Stunden je 1 Stück — nicht mehr als 6 Stück in 24 Stunden`. Mindestabstand und Maximalmenge sind nur bei reiner Bedarfsdosierung zulässig; zusammen mit einem strukturierten Rhythmus bricht der Algorithmus ab. Ein strukturiertes Schema kann als Bedarf gekennzeichnet sein: `bei Kopfschmerzen: alle 8 Stunden je 1 Stück`. 1.0.2 lieferte für reinen Bedarf `Unbekanntes Dosierungsschema: Unknown` und ließ bei strukturiertem Bedarf die Kennzeichnung weg (`alle 8 Stunden: je 1 Stück`).
- Start- und Endzeitpunkt (`boundsPeriod`): `ab dem …`, `vom … bis zum …`, `bis zum …`, eine Uhrzeit umgerechnet nach `Europe/Berlin`. 1.0.2 ignorierte `boundsPeriod` (`1-0-0-0 Stück` statt `vom 05.06.2026 bis zum 05.07.2026: 1-0-0-0 Stück`).
- Variable Frequenz und Periode im reinen Intervall: `1 bis 2 x alle 8 Stunden`, `alle 2 bis 3 Tage`. 1.0.2 ignorierte `frequencyMax` und `periodMax` (`alle 8 Stunden`, `alle 2 Tage`).
- Variable Dosis (`doseRange`): `je 1 bis 2 Stück`, `je bis zu 2 Stück`; im 4‑Schema in ausgeschriebener Form (`morgens — je 1 bis 2 Stück`). 1.0.2 gab im Intervall gar keine Dosis aus (`alle 8 Stunden`) und brach im 4‑Schema ab.
- Hinweis aus `patientInstruction` als eigener Satz: `1-0-0-0 Stück. Hinweis: Nach dem Essen`. 1.0.2 ließ ihn weg.
- `frequency`, `period` und `periodUnit` sind bei Tagesabschnitten, Uhrzeiten und Wochentagen optional; vorhanden ändern sie den Text nicht (Legacy-Angaben). 1.0.2 lieferte ohne sie `Unbekanntes Dosierungsschema: Unknown`.
- Intervall-Kombination ohne `frequency` (`alle 2 Tage: morgens — je 1 Stück`). 1.0.2 lieferte dafür `Unbekanntes Dosierungsschema: Unknown`.

#### Changed

- Eine nicht klassifizierbare Dosierung führt zum Abbruch (`Die Dosierung entspricht keinem unterstützten Dosierungsschema.`). 1.0.2 gab `Unbekanntes Dosierungsschema: Unknown` als Dosierungstext zurück.
- Segmente verschiedener Uhrzeiten oder Tagesabschnitte werden mit Komma getrennt statt mit Semikolon; das Semikolon trennt nur noch Wochentage: `täglich: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück` statt `…; 20:00 Uhr — je 2 Stück`. Uhrzeiten mit derselben Dosis werden auch über mehrere `Dosage`-Elemente hinweg zusammengefasst (`täglich: 08:00 Uhr, 20:00 Uhr — je 1 Stück`). Betrifft 16 der 92 regulären Beispiele des IG 1.0.7.
- `period = 1` mit `periodUnit = mo` ergibt `monatlich` statt `alle 1 Monat`, in der Intervall-Kombination statt `alle 1 mo`.
- Enthält eine Ressource mehrere `Dosage`-Elemente, muss jedes zu demselben Schema führen; andernfalls bricht der Algorithmus ab. 1.0.2 bestimmte das Schema allein am ersten Element, ein abweichendes späteres Element entfiel: aus „morgens 1 Stück" und „montags 2 Stück" wurde `1-0-0-0 Stück`.
- Eine variable Frequenz (`frequencyMax`) oder Periode (`periodMax`) führt bei Tagesabschnitten, Uhrzeiten und Wochentagen zum Abbruch; sie ist dem reinen Intervall vorbehalten. 1.0.2 übergang sie stillschweigend.
- Wochentage sind nur mit der Periode `1 wk` kombinierbar; jede andere Periode bricht ab. 1.0.2 ignorierte sie (`montags — je 1 Stück` bei `period = 2`, `periodUnit = d`).
- Die Intervall-Kombination setzt eine Periode in Tagen, Wochen oder Monaten voraus. 1.0.2 akzeptierte auch Stunden (`alle 3 h: morgens — je 1 Stück`).
- Abbruch statt fehlerhaftem Text bei nicht darstellbaren Angaben. 1.0.2 erzeugte jeweils einen Text:
  - fehlende Dosis (`doseAndRate`): `alle 8 Stunden`
  - unbekannter `when`-Code: `0-0-0-0 Stück`
  - unbekannte Zeiteinheit: `alle 8 x: je 1 Stück`
  - `timeOfDay` und `when` im selben Element (`tim-10`): `Unbekanntes Dosierungsschema: Unknown`
  - derselbe Wochentag mit unterschiedlicher Dosis: die zuletzt gelesene (`montags — je 2 Stück`)
  - dieselbe Kombination aus Wochentag und Tagesabschnitt mit unterschiedlicher Dosis: zwei Segmente (`montags 1-0-0-0 Stück; montags 2-0-0-0 Stück`)
  - dieselbe Uhrzeit oder derselbe Tagesabschnitt einer Intervall-Kombination mit unterschiedlicher Dosis: beide Dosen hintereinander
- `doseQuantity.value` und `doseRange.high.value` müssen größer als `0` sein; `0` bleibt nur als `doseRange.low.value` zulässig. 1.0.2 gab `je 0 Stück` aus.
- Nicht numerische Dosiswerte werden mit `<Feld> muss numerisch sein.` abgewiesen. 1.0.2 brach mit einem Python-Fehler ab; numerische Strings werden wie Zahlen geprüft.

### Referenzimplementierung und Repository

#### Added

- Unit-Tests für die Textgenerierung (`tests/test_medication_dosage_to_text.py`).

#### Changed

- Release läuft über `gh release`; die beiden Release-Workflows entfallen. Bei einem Tag-Push prüft die CI, dass `__version__` mit dem Tag übereinstimmt — beide Angaben landen als `algorithmVersion` beim Konsumenten und dürfen nicht auseinanderlaufen.
- CI testet nur noch die älteste und die neueste unterstützte Python-Version. Das Skript nutzt ausschließlich die Standardbibliothek.
- Der Syntax-Check prüft das gesamte `tests/`-Verzeichnis statt einzelner Dateien.

#### Fixed

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
