Diese Seite beschreibt die Erzeugung eines menschenlesbaren Dosierungstextes aus einer gesamten Arzneimittel‑Ressource (`MedicationRequest`, `MedicationDispense` oder `MedicationStatement`).

**Verbindlich ist der auf dieser Seite beschriebene Algorithmus.** Er ist die normative Festlegung der Textgenerierung; Implementierungen müssen ihn nachbilden, unabhängig von der gewählten Programmiersprache. Die aktuelle Version des Algorithmus ist **2.0.0** (siehe [Versionierung](#versionierung)).

Zur Veranschaulichung steht eine **Beispielimplementierung** als [Python-Skript](https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/blob/main/medication-dosage-to-text.py) bereit, mit der auch die Beispieltexte dieses Implementation Guides erzeugt werden. Sie ist weder verbindlich noch vollständig maßgeblich: Weicht sie von dieser Seite ab, gilt diese Seite. Das Skript führt die umgesetzte Algorithmus-Version in `__version__`; sie entspricht der hier angegebenen.

Voraussetzung für eine erfolgreiche Texterzeugung ist stets ein **profilkonformer Input**; im Profil gestrichene Elemente sind nicht Teil der Verarbeitung. Der Algorithmus ist kein Ersatz für die FHIR-Profilvalidierung: Er prüft einige nicht zulässige Konstellationen defensiv, führt aber keine vollständige Invariantenprüfung durch.

Diese Seite stellt zwei Aspekte dar: **Teil A** beschreibt, wie jede einzelne Angabe einer `Dosage` in Text überführt wird. **Teil B** beschreibt, wie diese Bausteine je zulässigem Schema zu einem vollständigen Dosierungstext zusammengesetzt werden.

Der gesamte Fließtext dieser Seite ist verbindlich. Eingerückte Blöcke enthalten ausschließlich Unverbindliches: Orientierungshilfen, Hintergrund und Verweise auf andere Dokumente.

**Zur Bereichsdarstellung** — festgelegt in den jeweiligen Abschnitten, hier vorab zur Orientierung: Variable Angaben (Frequenz, Periode, Einzeldosis) werden durchgängig mit dem Wort **„bis"** gebildet (z. B. „1 bis 2 Stück"). Enthält das kompakte 4‑Schema einen variablen Wert, wird es in die ausgeschriebene Segmentform überführt (siehe [4‑Schema](#schema-mit-tageszeiten-bezug-4-schema)).

---

## Gesamtalgorithmus

Die Verarbeitung erfolgt in dieser Reihenfolge:

1. Anhand von `resourceType` wird die Liste der Dosierungen gelesen:
   * `MedicationRequest.dosageInstruction`
   * `MedicationDispense.dosageInstruction`
   * `MedicationStatement.dosage`
2. Bei einem anderen Ressourcentyp wird mit einem Fehler abgebrochen (`Unsupported resource type: {resourceType}`). Ist die gelesene Liste leer oder fehlt sie, ist das Ergebnis ein leerer String.
3. Setzt eines der `Dosage`-Elemente `timeOfDay` **und** `when` gemeinsam, wird abgebrochen. Beides zugleich ist bereits durch die FHIR-Basisinvariante `tim-10` ausgeschlossen; ohne diese Prüfung würde je nach Schema eine der beiden Angaben stillschweigend verworfen.
4. Enthält die Liste eine reine Bedarfsdosierung (`asNeededBoolean = true` ohne `timing`) und insgesamt nicht genau ein `Dosage`-Element, wird die Verarbeitung abgebrochen.
5. Das Darstellungsschema wird ausschließlich anhand des **ersten** `Dosage`-Elements und in der unter [Schema-Erkennung](#schema-erkennung) angegebenen Priorität bestimmt. Trifft keine Regel zu, wird abgebrochen; es wird **kein** Ersatztext erzeugt.
6. Der schemaspezifische Generator sammelt die benötigten Dosis-/Zeitsegmente. Je nach Schema werden alle `Dosage`-Elemente oder nur das erste verarbeitet; die genaue Aggregation ist unter [Aggregation mehrerer Dosage-Elemente](#aggregation-mehrerer-dosage-elemente) festgelegt.
7. Der Generator setzt Zeitrahmen, Bedarfsangaben, Rhythmus und Kerntext zusammen. Danach werden – außer bei Freitext – Maximalmenge und `patientInstruction` ergänzt.
8. Abschließend wird der Text – außer bei Freitext – normalisiert. Ist das erste `Dosage`-Element als Bedarf gekennzeichnet, wird zusätzlich exakt das erste Zeichen des Ergebnisses in einen Großbuchstaben umgewandelt.

Das folgende Pseudocode-Gerüst zeigt den vollständigen Kontrollfluss:

```text
dosierungen = extrahiereDosierungen(resource)
wenn dosierungen leer: return ""

wenn irgendeine dosierung timeOfDay und when gemeinsam setzt:
  Fehler

wenn irgendeine dosierung reine Bedarfsdosierung ist
und anzahl(dosierungen) != 1:
  Fehler

schema = erkenneSchema(dosierungen[0])
wenn schema unbekannt: Fehler
fuer jede weitere dosierung:
  wenn erkenneSchema(dosierung) != schema: Fehler

text = erzeugeSchemaspezifischenText(schema, dosierungen)
wenn schema = Freitext: return text

text = normalisiere(text)
return text
```

---

## Teil A: Übersetzung der einzelnen Angaben

### Dosis (`doseAndRate.doseQuantity` / `doseRange`)

Es wird ausschließlich `doseAndRate[0]` ausgewertet. Ist dort `doseQuantity` vorhanden, hat sie Vorrang; andernfalls wird `doseRange` gelesen. Weitere `doseAndRate`-Einträge werden ignoriert. Die Standardform lautet `je {Wert} {Einheit}` (z. B. `je 1 Stück`). Bei einem `doseRange` gilt abhängig davon, ob ein beidseitig oder einseitig begrenzter Bereich vorliegt:

* beidseitig: `je {von} bis {bis} {Einheit}` (z. B. `je 1 bis 2 Stück`)
* nur obere Grenze: `je bis zu {bis} {Einheit}` (z. B. `je bis zu 2 Stück`)

Nur die untere Grenze (`low` ohne `high`) ist **nicht zulässig** und wird durch die Invariante `DoseRangeHighRequiredWhenLowPresent` ausgeschlossen.

Ganzzahlige Werte werden ohne Nachkommastelle dargestellt; überflüssige Dezimalstelle und Komma entfallen (`1.0` → `1`). Dezimalwerte werden mit **deutschem Dezimalkomma** ausgegeben (z. B. `1,5`). Die maximale Anzahl von Nachkommastellen ist nicht eingeschränkt; Werte werden verlustfrei ohne Rundung übernommen. Die Verantwortung für sinnvolle Präzision (z. B. nicht mehr als 2 Nachkommastellen) liegt beim aufrufenden System.


Eine Dosis ist in **jedem** strukturierten Schema erforderlich. Fehlt `doseAndRate` ganz, bricht der Algorithmus ab — es wird weder ein Segment stillschweigend übersprungen noch eine Dosieranweisung ohne Dosis erzeugt. Profilkonformer Input enthält immer eine Dosis: `DosageStructuredRequiresBoth` erzwingt „`timing` impliziert `doseAndRate`", und für die reine Bedarfsdosierung verlangt `DosageStructuredOrFreeText` ebenfalls `doseAndRate`.

`doseQuantity.value` und `doseQuantity.unit` sind für die Textgenerierung verpflichtend. Fehlt eine dieser Angaben trotz vorhandener `doseQuantity`, bricht der Algorithmus mit einem Fehler ab. Der Wert muss außerdem größer als `0` sein; andernfalls bricht der Algorithmus mit `ValueError("doseQuantity.value muss größer als 0 sein.")` ab.

Bei `doseRange` muss die Obergrenze mit `high.value` und `high.unit` vorhanden sein. Ist zusätzlich `low` vorhanden, müssen auch `low.value` und `low.unit` vorhanden sein und beide Einheiten müssen übereinstimmen. Eine fehlende Pflichtangabe oder eine abweichende Einheit führt zum Abbruch. Die Ausgabeeinheit stammt stets aus `high.unit`. Enthält `doseAndRate[0]` weder `doseQuantity` noch `doseRange`, wird ebenfalls abgebrochen. Vorhandene Werte müssen jeweils größer als `0` sein — ein `doseRange.high.value <= 0` führt zu `ValueError("doseRange.high.value muss größer als 0 sein.")`, ein vorhandenes `doseRange.low.value <= 0` entsprechend zu `ValueError("doseRange.low.value muss größer als 0 sein.")`.

Der so gebildete Dosis-Baustein – einschließlich der **Bereichsform** (`je {von} bis {bis} {Einheit}`) – ist in **allen** Schemata einsetzbar; überall dort, wo in Teil B der Platzhalter `{Dosis}` steht, kann ein fester Wert **oder** ein Bereich stehen (z. B. `alle 8 Stunden: je 1 bis 2 Stück`).

**Ausnahme:** Im kompakten 4‑Schema entfällt das vorangestellte `je`; dort erscheinen die Dosiswerte positionell (siehe Teil B).

### Zeitrahmen

#### Dauer (`boundsDuration`)

Eine begrenzte Anwendungsdauer wird vorangestellt als `für {Wert} {Einheit}`. Die Einheit wird nach den Regeln unter [Einheiten und Pluralisierung](#einheiten-und-pluralisierung) ausgegeben, z. B. `für 1 Tag` bzw. `für 7 Tage`.

`boundsDuration.value` und `boundsDuration.code` sind für die Textgenerierung verpflichtend, sobald `boundsDuration` vorhanden ist. Der Wert muss numerisch und größer als `0` sein. Fehlt eine Pflichtangabe oder ist der Wert nicht größer als `0`, bricht der Algorithmus mit einem Fehler ab.

#### Start- und Endzeitpunkt (`boundsPeriod`)

Start- und/oder Endzeitpunkt werden vorangestellt:

* nur Start (offenes Ende): `ab dem {Startdatum}[ um {Uhrzeit}]`
* Start und Ende: `vom {Startdatum}[ um {Uhrzeit}] bis zum {Enddatum}[ um {Uhrzeit}]`
* nur Ende: `bis zum {Enddatum}[ um {Uhrzeit}]`

Das Datum wird im Format `TT.MM.JJJJ`, eine vorhandene Uhrzeit im Format `HH:MM Uhr` ausgegeben. Sekunden werden nicht dargestellt.

`boundsPeriod` und `boundsDuration` dürfen nicht gleichzeitig vorhanden sein. Andernfalls bricht die Textgenerierung ab. Ein vorhandenes `boundsPeriod` muss `start` und/oder `end` enthalten. Jeder vorhandene Wert muss als FHIR-`dateTime` mit vollständigem Datum `JJJJ-MM-TT` parsebar sein. Bei einer reinen Datumsangabe erfolgt keine Zeitzonenverarbeitung. Enthält der Wert eine Uhrzeit, muss gemäß FHIR eine Zeitzone als `Z` oder Offset vorhanden sein. Der Zeitpunkt wird in die verbindliche IANA-Zielzeitzone `Europe/Berlin` umgerechnet; erst danach werden das gegebenenfalls verschobene Datum sowie Stunde und Minute formatiert. Die Umrechnung berücksichtigt automatisch Sommer- und Winterzeit.

*Beispiel:* `2026-06-05T23:30:45Z` wird in `Europe/Berlin` zu `06.06.2026 um 01:30 Uhr`, im Text also `ab dem 06.06.2026 um 01:30 Uhr`.

### Einnahmerhythmus (`frequency` / `period` / `periodUnit`)

Aus `frequency`, `frequencyMax`, `period`, `periodMax` und `periodUnit` entsteht der einleitende Rhythmus:

* tägliches Muster (`periodUnit='d'`, `period=1`): `täglich` bei `frequency=1` und fehlendem `frequencyMax`, sonst `{Frequenzwert} x täglich`
* wöchentliches Muster (`periodUnit='wk'`, `period=1`): `wöchentlich` bei `frequency=1` und fehlendem `frequencyMax`, sonst `{Frequenzwert} x wöchentlich`
* monatliches Muster (`periodUnit='mo'`, `period=1`): `monatlich` bei `frequency=1` und fehlendem `frequencyMax`, sonst `{Frequenzwert} x monatlich`
* sonstige Perioden bei einer **festen Frequenz von genau 1** (`frequency=1`, `frequencyMax` fehlt): `alle {Periodenwert} {Einheit}` (z. B. `alle 8 Stunden`)
* sonstige Perioden bei einem **Frequenzbereich** (`frequencyMax` vorhanden, auch bei `frequency=1`) oder einer festen Frequenz größer als 1: `{Frequenzwert} x alle {Periodenwert} {Einheit}` (z. B. `1 bis 2 x alle 8 Stunden` beziehungsweise `2 x alle 8 Stunden`)

`{Frequenzwert}` bezeichnet entweder `frequency` allein oder `frequency bis frequencyMax`; `{Periodenwert}` entsprechend `period` allein oder `period bis periodMax`. Die Perioden-Einheit wird nach den Regeln unter [Einheiten und Pluralisierung](#einheiten-und-pluralisierung) ausgegeben. Beispiele für Bereiche sind `2 bis 3 x täglich` und `alle 2 bis 3 Tage`.

Diese allgemeine Frequenzdarstellung gilt für das reine Intervallschema ohne
`timeOfDay` oder `when`. Bei einer Intervall-Kombination geben die konkreten
Zeitpunkte die Anwendungshäufigkeit bereits vollständig an. Deshalb wird dort eine
vorhandene `frequency` nicht ausgegeben; der gemeinsame Einnahmerhythmus wird
ausschließlich aus `period`, `periodMax` und `periodUnit` gebildet. Dabei gelten
für `1 d`, `1 wk` und `1 mo` ebenfalls die Kurzformen `täglich`, `wöchentlich`
und `monatlich`.

Fehlen `frequency`, `period` und `periodUnit` vollständig, wird kein Baustein für
den Einnahmerhythmus erzeugt. Dies ist nur bei Schemata zulässig, deren zeitlicher
Bezug bereits durch `when`, `timeOfDay` oder `dayOfWeek` bestimmt wird. Das reine
Intervallschema erfordert `frequency`, `period` und `periodUnit`; die
Intervall-Kombination erfordert `period` und `periodUnit`, während `frequency`
optional ist. Sind die jeweils erforderlichen Angaben unvollständig, greift keine
der Schema-Regeln und die Verarbeitung bricht ab (siehe
[Fehler und Validierung](#fehler-und-validierung)).

### Einheiten und Pluralisierung

Es sind zwei Arten von Einheiten zu unterscheiden:

**1. Zeit-Einheiten** (aus `periodUnit`, `boundsDuration.code`, `MinimumIntervalBetweenAdministrations`): Sie werden über eine **feste Tabelle** in ihre deutsche Bezeichnung übersetzt. Die Form richtet sich ausschließlich nach dem für die Einheit verwendeten Bezugswert: **Singular genau dann, wenn dieser Wert gleich `1` ist**, sonst **Plural**. Bei einem Periodenbereich ist `periodMax` der Bezugswert; ohne `periodMax` ist es `period`. Bei `boundsDuration` und beim Mindestabstand ist es der jeweilige `value` (`boundsDuration` mit `1 d` ergibt daher `für 1 Tag`).

| Code | Singular (Wert = 1) | Plural (sonst) |
|------|---------------------|----------------|
| `s`  | Sekunde | Sekunden |
| `min`| Minute | Minuten |
| `h`  | Stunde | Stunden |
| `d`  | Tag | Tage |
| `wk` | Woche | Wochen |
| `mo` | Monat | Monate |
| `a`  | Jahr | Jahre |

Die Tabelle ist **abschließend**. Ein Code außerhalb dieser Liste führt zum Abbruch; ein roher UCUM-Code wäre in einem patientenlesbaren Text nicht verständlich. Profilkonformer Input kann diesen Fall nicht auslösen, da alle drei Quellen required gebunden sind: `periodUnit` an `PeriodUnitsOfTimeDgMPVS` (`min`, `h`, `d`, `wk`, `mo`), `boundsDuration.code` an `DurationUnitsOfTimeDgMPVS` (`d`, `wk`, `mo`, `a`) und der Mindestabstand an `MindestabstandUnitsOfTimeDgMPVS` (`min`, `h`).

**2. Dosis-Einheit** (`doseQuantity.unit` / `doseRange.*.unit`, z. B. „Stück", „mg", „Kapseln", „Tropfen"): Sie wird **wörtlich und unverändert** aus dem Input übernommen und **nicht** pluralisiert. Der Numerator der Maximalmenge (`maxDosePerPeriod.numerator.unit`) entspricht der Dosis-Einheit und wird ebenfalls wörtlich übernommen.

### Wochentage (`dayOfWeek`)

Wochentage werden, sofern vorhanden, in kanonischer Reihenfolge (Montag bis Sonntag) verarbeitet und in adverbialer Form dargestellt:

| Code | Text |
|------|------|
| `mon` | montags |
| `tue` | dienstags |
| `wed` | mittwochs |
| `thu` | donnerstags |
| `fri` | freitags |
| `sat` | samstags |
| `sun` | sonntags |

Die Tabelle ist **abschließend** und deckt die required gebundene FHIR-Codeliste `DaysOfWeek` vollständig ab.

### Konkrete Zeiten (`timeOfDay`)

Uhrzeiten werden anhand ihres Eingabestrings aufsteigend sortiert und im Format `HH:MM Uhr` ausgegeben (z. B. `08:00 Uhr`). Akzeptiert werden nullaufgefüllte Werte im Format `HH:MM` oder `HH:MM:SS` mit optionalen Sekundenbruchteilen. Stunde und Minute werden übernommen, Sekunden und Sekundenbruchteile entfallen. Ein nicht parsebarer oder außerhalb des zulässigen Uhrzeitbereichs liegender Wert führt zum Abbruch.
Die lexikographische Sortierung des Eingabestrings ist dabei äquivalent zur chronologischen Sortierung, weil FHIR `timeOfDay`-Werte nullaufgefüllt sein müssen (d. h. `08:00:00` statt `8:00:00`): Zwei Werte `HH1:MM1` und `HH2:MM2` sind genau dann in lexikographischer Reihenfolge, wenn HH1 < HH2, oder HH1 = HH2 und MM1 ≤ MM2.
Alle Uhrzeiten werden über **sämtliche** `Dosage`-Elemente hinweg eingesammelt und gemeinsam aufsteigend sortiert. Die Reihenfolge der `Dosage`-Elemente in der Ressource hat damit keinen Einfluss auf die Reihenfolge der Uhrzeiten im Text.

Unmittelbar aufeinanderfolgende Uhrzeiten mit **derselben** Dosis werden anschließend vor einem gemeinsamen Gedankenstrich mit Komma zusammengefasst, z. B. `08:00 Uhr, 20:00 Uhr — je 1 Stück`. Liegt eine Uhrzeit mit abweichender Dosis dazwischen, entsteht für jede Uhrzeit ein eigenes Segment; die aufsteigende Sortierung hat Vorrang vor der Zusammenfassung.

*Beispiel:* Das erste `Dosage`-Element enthält `timeOfDay = [08:00:00, 12:00:00]` und eine Dosis von `1 Stück`; das zweite enthält `timeOfDay = [20:00:00]` und eine Dosis von `2 Stück`. Das Ergebnis lautet:

```text
täglich: 08:00 Uhr, 12:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück
```

### Tagesabschnitt (`when`-Codes)

Die unterstützten Codes werden wie folgt abgebildet:

| Code | Text |
|------|------|
| `MORN` | morgens |
| `NOON` | mittags |
| `EVE` | abends |
| `NIGHT` | zur Nacht |

Die Tabelle ist **abschließend**; `when` ist required an `TimingWhenDgMPVS` gebunden, das genau diese vier Codes enthält. Ein Code außerhalb der Tabelle führt zum Abbruch — er würde sonst bei der Belegung übersprungen und ergäbe einen Text, der die zugehörige Gabe unterschlägt (etwa `0-0-0-0 Stück` trotz angegebener Dosis).

Ferner dürfen `when` und `timeOfDay` nicht gemeinsam auftreten (FHIR-Basisinvariante `tim-10`); der Algorithmus bricht in diesem Fall ab.

Je nach Schema erscheinen die Codes entweder als kompaktes, positionelles Muster (4‑Schema) oder als einzelne Abschnittsangaben analog zu Uhrzeiten (siehe Teil B).

### Einnahmeanlass (`asNeededFor`)

Der Einnahmeanlass wird bei Bedarfsmedikation vorangestellt als `bei {Anlass}` (z. B. `bei Kopfschmerzen`). Der Einnahmeanlass ist **optional**; fehlt er, wird generisch `bei Bedarf` gesetzt.

Es können **mehrere** Einnahmeanlässe angegeben sein (`asNeededFor 0..*`, fachlich ODER-verknüpft). Sie werden in der angegebenen Reihenfolge als **deutsche Aufzählung** verbunden: alle bis auf den letzten mit Komma, der letzte mit „ oder " (kein Komma vor „oder"):

* 2 Anlässe: `bei Kopfschmerzen oder Fieber`
* 3+ Anlässe: `bei Kopfschmerzen, Fieber oder Gliederschmerzen`

Details zur Zusammensetzung siehe [Schema für Bedarfsmedikation](#schema-für-bedarfsmedikation).

Ausgewertet werden nur Extensions mit der exakten kanonischen URL aus der [Feldreferenz](#feldreferenz). Von jeder passenden Extension wird ausschließlich `valueCodeableConcept.text` übernommen. Im Profil `DosageDgMP` ist `coding` auf `0..0` eingeschränkt und `.text` verpflichtend. Fehlt dennoch ein nicht leerer Text, bricht der Algorithmus mit einem Fehler ab; die Extension wird nicht stillschweigend ignoriert. Führender und abschließender Leerraum des Textes wird entfernt.

### Mindestabstand zwischen Gaben

Der Mindestabstand ist **ausschließlich bei einer reinen Bedarfsdosierung** zulässig, also bei `asNeededBoolean = true` ohne `timing` (Invariante `MindestabstandOnlyPureAsNeeded`). Der Baustein lautet `im Abstand von mindestens {Wert} {Zeiteinheit}` und steht vor der Dosis. Tritt er zusammen mit einem strukturierten Rhythmus auf, bricht der Algorithmus ab: Der Rhythmus legt den Abstand zwischen zwei Gaben bereits fest, eine zweite und schwächere Untergrenze daneben ließe offen, welche Angabe gilt — und den Mindestabstand stillschweigend zu übergehen wäre eine sicherheitsrelevante Auslassung. Der Algorithmus durchsucht `modifierExtension` nach der exakten kanonischen URL `MinimumIntervalBetweenAdministrations` und verwendet die erste passende Extension. `valueDuration`, `valueDuration.value` und `valueDuration.code` sind verpflichtend — im Profil auf `1..1` gesetzt und zusätzlich vom Algorithmus geprüft; der Wert muss numerisch und größer als `0` sein. Andernfalls bricht der Algorithmus mit einem Fehler ab. Die Formatierung des Wertes und der Einheit entspricht `boundsDuration`, jedoch ohne das Wort `für`.

Als Zeiteinheit sind **ausschließlich Minuten (`min`) und Stunden (`h`)** zulässig; `valueDuration.code` ist required an `MindestabstandUnitsOfTimeDgMPVS` gebunden, `valueDuration.system` ist auf UCUM festgelegt. Die Anzeigeeinheit `valueDuration.unit` muss zum Code passen (Invariante `MindestabstandUnitMatchesCode`) — der erzeugte Text leitet die Einheit aus `.code` ab, sodass ein abweichendes `.unit` sonst der Ressource widerspräche.

`valueDuration.comparator` ist auf `0..0` gestrichen: Ein Mindestabstand „> 4 Stunden" wäre unbestimmt, und die Textgenerierung stellt ausschließlich den exakten Wert dar.

### Maximalmenge (`maxDosePerPeriod`)

Die Maximalmenge wird der Dosis nachgestellt als `nicht mehr als {Wert} {Einheit} {Zeitraum}`. Als Bezugszeitraum ist ausschließlich **24 Stunden** oder **1 Tag** zulässig (durchgesetzt über die Invariante `MaxDosePerPeriodOnly24hOr1d`). Die Auswahl wird eingabetreu wiedergegeben:

* `24 h` → `in 24 Stunden`
* `1 d` → `pro Tag`

Die Einheit entspricht der Dosiereinheit.

Die Maximalmenge ist **ausschließlich bei einer reinen Bedarfsdosierung** zulässig, also bei `asNeededBoolean = true` ohne `timing` (Invariante `MaxDoseOnlyPureAsNeeded`). Tritt sie zusammen mit einem strukturierten Rhythmus auf, bricht der Algorithmus ab: Der Rhythmus legt bereits fest, wie viel im Bezugszeitraum angewendet wird, und die Angabe stillschweigend zu übergehen wäre eine sicherheitsrelevante Auslassung. Ohne Bedarfskennzeichen wird `maxDosePerPeriod` gar nicht gelesen; die nachfolgenden Pflichtfeldprüfungen greifen dort folglich nicht.

Ist `maxDosePerPeriod` vorhanden, müssen `numerator.value`, `numerator.unit`, `denominator.value` und `denominator.code` vorhanden sein. `numerator.value` muss numerisch und `numerator.unit` darf nicht leer sein. Als Nenner werden ausschließlich `1 d` und `24 h` akzeptiert. Fehlende oder andere Angaben führen zum Abbruch; es gibt keinen Fallback und keine unvollständige Ausgabe der Maximalmenge.

### Freitext-Hinweise (`patientInstruction`)

Ergänzende Einnahmehinweise werden aus `patientInstruction` (einzelner String, `0..1`) als abschließender Satz mit vorangestelltem `Hinweis:` wiedergegeben (z. B. `Hinweis: Mit ausreichend Wasser einnehmen`). Führender und abschließender Leerraum des Feldwerts wird entfernt; ein danach leerer Wert wird nicht ausgegeben.

Der Hinweis wird als **eigener Satz** angehängt. Der bisherige strukturierte Dosierungstext erhält einen abschließenden Punkt, gefolgt von `Hinweis: {Text}`. Ist bereits ein Punkt vorhanden, wird kein zweiter ergänzt. Bei profilkonformen Eingaben erzeugt der Algorithmus den Punkt regulär beim Anhängen des Hinweises. Beispiel: `1-0-1-0 Stück. Hinweis: Nach dem Essen`.

`additionalInstruction` wird **nicht** verwendet und ist im Profil `DosageDgMP` auf `0..0` gestrichen; es bleibt für künftige strukturierte Zusatzangaben reserviert.

Auch `route` wird vom Algorithmus nicht gelesen oder ausgegeben; es steht in der Liste zukünftig unterstützter Dosierkonfigurationen (siehe [Beispiele von erzeugten Dosiertexten](https://ig.fhir.de/igs/medication/dosierung-beispiele.html)).

`doseAndRate.rateQuantity`, `.rateRatio` und `.rateRange` werden vom Algorithmus nicht gelesen; sie stehen ebenfalls in der Liste zukünftig unterstützter Dosierkonfigurationen.

### Trennzeichen

* **Doppelpunkt mit Leerzeichen** (`: `) trennt die Dosieranweisung in zwei Abschnitte. Links des Doppelpunkts stehen, sofern vorhanden, der Zeitrahmen, der Einnahmeanlass und das Intervall.
* **Gedankenstrich mit Leerzeichen** (` — `) verbindet eine Zeit- oder Abschnittsangabe mit der zugehörigen Dosis sowie die Dosis mit der Maximalmenge im Falle einer Bedarfsmedikation.
* **Komma mit Leerzeichen** (`, `) trennt aufeinanderfolgende Segmente unterschiedlicher **Tages- oder Uhrzeiten**, unabhängig davon, ob sie aus derselben oder aus verschiedenen `Dosage`-Einträgen stammen.
* **Semikolon mit Leerzeichen** (`; `) trennt aufeinanderfolgende **Wochentagssegmente**, unabhängig davon, ob sie aus derselben oder aus verschiedenen `Dosage`-Einträgen stammen.
* **Bindestrich** (`-`) trennt die vier Positionen des 4‑Schemas.

#### Zeichenrepertoire

Die folgenden Zeichen sind für den erzeugten Text **verbindlich festgelegt**. Maßgeblich ist jeweils der Codepoint, nicht die optische Ähnlichkeit — mehrere der Zeichen haben verwechselbare Varianten, die **nicht** verwendet werden dürfen.

| Zeichen | Codepoint | Name | Verwendung | Nicht verwenden |
|---------|-----------|------|------------|-----------------|
| `—` | U+2014 | EM DASH | Zeit-/Abschnittsangabe ↔ Dosis; Dosis ↔ Maximalmenge | `–` U+2013, `―` U+2015, `-` U+002D |
| `-` | U+002D | HYPHEN-MINUS | die vier Positionen des 4‑Schemas | `‐` U+2010, `−` U+2212, `–` U+2013 |
| `,` | U+002C | COMMA | Segmenttrennung **und** deutsches Dezimalkomma | `،` U+060C |
| `;` | U+003B | SEMICOLON | Trennung von Wochentagssegmenten | `;` U+037E |
| `:` | U+003A | COLON | Abschnittstrennung sowie Stunde:Minute | `∶` U+2236 |
| `.` | U+002E | FULL STOP | Satzende vor `Hinweis:` sowie Tag.Monat.Jahr | `․` U+2024 |
| `x` | U+0078 | LATIN SMALL LETTER X | Frequenzmarker in `3 x täglich` | `×` U+00D7, `✕` U+2715 |
| ` ` | U+0020 | SPACE | einziges Trennzeichen zwischen Wörtern | `&nbsp;` U+00A0, U+2009, U+202F |

Für die Umlaute in den festen Wortbestandteilen (`täglich`, `wöchentlich`, `für`) gilt die **vorkomponierte NFC-Form**: `ä` U+00E4, `ö` U+00F6, `ü` U+00FC — **nicht** die zerlegte Form aus Grundbuchstabe und kombinierendem Trema (`a` + U+0308). Der gesamte erzeugte Text ist NFC-normalisiert. Ein `ß` kommt in keinem vom Algorithmus erzeugten Wortbestandteil vor.

Nicht Teil dieses Repertoires sind Zeichen, die **unverändert aus dem Input übernommen** werden: die Dosiereinheit (`doseQuantity.unit`), der Einnahmeanlass (`asNeededFor`), der Hinweis (`patientInstruction`) und der Freitext (`Dosage.text`). Sie werden weder ersetzt noch normalisiert.

Strukturierte Schemata erzeugen keine Zeilenumbrüche; ihr Text steht in einer Zeile. Die Freitext-Dosierung durchläuft die nachfolgende Normalisierung nicht und kann daher im Feld enthaltene Zeilenumbrüche beibehalten; lediglich der unter [Freitext-Dosierung](#freitext-dosierung) beschriebene `trim` wird angewendet. Diese Ausnahme ist notwendig, weil die Invariante `FreeTextMatchesRenderedText` exakte Gleichheit zwischen `renderedDosageInstruction` und `Dosage.text` verlangt.

**Normalisierung:** Nach dem Zusammensetzen wird der Text normalisiert – dies gilt für **alle Schemata außer der Freitext-Dosierung**:

* In strukturiert erzeugten Texten wird **jede** Folge von Leerraum – Leerzeichen, Tabs und Zeilenumbrüche, unabhängig von ihrer Herkunft – zu **einem** Leerzeichen reduziert. Damit steht ein strukturiert erzeugter Text auch dann in einer Zeile, wenn ein übernommenes Freitextfeld (`patientInstruction`, Einnahmeanlass, Dosiereinheit) selbst einen Umbruch enthält. Freitext-Dosierungen werden nicht normalisiert.
* Leerraum **unmittelbar vor** den Satzzeichen `;` `:` `.` `,` wird entfernt.
* Führende und abschließende Leerzeichen werden entfernt (trim).

Der Gedankenstrich (`—`) und Klammern bleiben dabei unangetastet.

**Deterministische Reihenfolge:** Bei profilkonformem Input ist die Reihenfolge der Segmente im erzeugten Text grundsätzlich **unabhängig von der Reihenfolge der `Dosage`-Elemente** in der Ressource. Segmente werden ausschließlich nach ihrem Inhalt sortiert (Uhrzeiten aufsteigend, Tagesabschnitte in fester Reihenfolge morgens → mittags → abends → zur Nacht, Wochentage kanonisch Montag → Sonntag).

---

## Schema-Erkennung

Bevor die Bausteine zusammengesetzt werden, wird genau **ein** Darstellungsschema bestimmt. Es gilt für die gesamte Ressource: Enthält sie mehrere `Dosage`-Elemente, muss **jedes** zu demselben Schema führen, sonst bricht der Algorithmus ab. Grundlage der Erkennung ist zwar das erste Element, ein abweichendes späteres Element würde bei der Textbildung aber übergangen — und mit ihm eine vollständige Gabe: Aus „morgens 1 Stück" und „montags 2 Stück" entstünde kommentarlos `1-0-0-0 Stück`. Die Invarianten `TimingOnlyOneType` und `TimingOnlyWhenOrTimeOfDay` schließen das für profilkonformen Input aus; der Algorithmus verlässt sich darauf nicht.

 Grundlage der Erkennung ist das **erste `Dosage`-Element** der Ressource; der profilkonforme Input stellt sicher, dass alle weiteren Elemente strukturell dazu passen und nur zusätzliche Segmente beisteuern.

### Ausgewertete Merkmale (auf `timing.repeat` des ersten Elements)

| Merkmal | Bedingung |
|---------|-----------|
| `hatText` | `Dosage.text` hat einen nicht leeren Wert |
| `hatTiming` | `Dosage.timing` hat ein nicht leeres Objekt |
| `hatDosis` | `Dosage.doseAndRate` ist vorhanden **und** nicht leer |
| `istBedarf` | `Dosage.asNeededBoolean = true` |
| `hatFrequenz` | der Schlüssel `repeat.frequency` ist vorhanden (unabhängig von seinem Wert) |
| `hatPeriode` | der Schlüssel `repeat.period` ist vorhanden (unabhängig von seinem Wert) |
| `hatPeriodeneinheit` | der Schlüssel `repeat.periodUnit` ist vorhanden (unabhängig von seinem Wert) |
| `hatWochentag` | `repeat.dayOfWeek` ist vorhanden **und** nicht leer |
| `hatWhenCodes` | `repeat.when` ist vorhanden **und** nicht leer |
| `hatUhrzeit` | `repeat.timeOfDay` ist vorhanden **und** nicht leer |
| `hatFrequenzMax` | der Schlüssel `repeat.frequencyMax` ist vorhanden |
| `hatPeriodenMax` | der Schlüssel `repeat.periodMax` ist vorhanden |

Abgeleitete Hilfsbedingungen:

* `istTagesmuster` = `repeat.period = 1` **und** `repeat.periodUnit = 'd'` **und nicht** `hatPeriodenMax` — dient nur der Abgrenzung von `istNichtTagesmuster` in Regel 7
* `istNichtTagesmuster` = `hatPeriode` **und** `hatPeriodeneinheit` **und nicht** `istTagesmuster`
* `istReinesIntervall` = `hatFrequenz` **und** `hatPeriode` **und** `hatPeriodeneinheit` **und nicht** (`hatWhenCodes` oder `hatUhrzeit` oder `hatWochentag`)
* `hatZulaessigeLegacyFelder(einheit)` = **nicht** `hatFrequenzMax` **und nicht** `hatPeriodenMax` **und** ((**nicht** `hatPeriode` **und nicht** `hatPeriodeneinheit`) **oder** (`repeat.period = 1` **und** `repeat.periodUnit = einheit`))

#### Legacy-Angaben

In früheren Fassungen des Medication IG DE waren `frequency`, `period` und `periodUnit` in **allen** Dosierschemata verpflichtend — auch dort, wo sie nur wiederholen, was Wochentage, Tagesabschnitte oder Uhrzeiten bereits ausdrücken. Sie sind heute nur noch dort erforderlich, wo sie tatsächlich ein Intervall beschreiben. Damit bestehende Verordnungsdaten gültig bleiben, werden sie weiterhin geduldet. Sie begründen kein Intervallschema und **ändern die Ausgabe nicht**: Eine Ressource mit und eine ohne diese Felder erzeugen denselben Text.

Die Bedingung `hatZulaessigeLegacyFelder` gilt für alle vier betroffenen Schemata; sie unterscheiden sich nur in der Periodeneinheit, die sich aus der impliziten Wiederholung des Schemas ergibt:

| Aufruf | geduldetes Paar | verwendet in |
|---|---|---|
| `hatZulaessigeLegacyFelder('wk')` | `period = 1`, `periodUnit = wk` | Regel 4 und 5 (Wochentage) |
| `hatZulaessigeLegacyFelder('d')` | `period = 1`, `periodUnit = d` | Regel 3 und 6 (Tagesabschnitte, Uhrzeiten) |

`frequency` wird in keiner der beiden Bedingungen geprüft: In diesen Schemata beeinflusst es die Schema-Erkennung nicht und wird nicht ausgegeben, weil die konkreten Zeitpunkte die Zahl der Gaben bereits festlegen. Die Invariante `TimingFrequencyCount` des Profils stellt sicher, dass ein angegebener Wert dieser Anzahl entspricht. Nur bei **wiederkehrenden Intervallen** (Regel 8) ist `frequency` keine Legacy-Angabe: Dort ist es konstituierend und erscheint im Text, etwa als `2 x alle 8 Stunden`.

Wochentagsschemata wiederholen sich implizit wöchentlich, tägliche Schemata implizit täglich — daher die unterschiedliche Einheit. Jede **andere** Periode beschreibt ein echtes Intervall: Bei `dayOfWeek` ist sie unzulässig, bei `when` oder `timeOfDay` führt sie über `istNichtTagesmuster` zu Regel 7. Eine variable Frequenz oder Periode ist bei Wochentagen ebenfalls ausgeschlossen, weil die Wochentage die Zahl der Anwendungen bereits festlegen.

Im Schema **Kombination von Zeitintervallen** (Regel 7) ist ausschließlich `frequency` eine Legacy-Angabe; `period` und `periodUnit` legen dort den Rhythmus fest.

### Prioritätsreihenfolge

Die Regeln werden **von oben nach unten** geprüft; die **erste** zutreffende Regel bestimmt das Schema:

| # | Schema | Bedingung |
|---|--------|-----------|
| 1 | **Freitext-Dosierung** | `hatText` **und nicht** `hatTiming` **und nicht** `hatDosis` |
| 2 | **Bedarfsmedikation (rein)** | `istBedarf` **und nicht** `hatTiming` |
| 3 | **4-Schema** (Tageszeiten) | `hatWhenCodes` **und nicht** `hatUhrzeit` **und nicht** `hatWochentag` **und** `hatZulaessigeLegacyFelder('d')` |
| 4 | **Wochentags-Bezug** | `hatWochentag` **und nicht** `hatWhenCodes` **und nicht** `hatUhrzeit` **und** `hatZulaessigeLegacyFelder('wk')` |
| 5 | **Kombination von Wochentagen** | `hatWochentag` **und** (`hatUhrzeit` **oder** `hatWhenCodes`) **und** `hatZulaessigeLegacyFelder('wk')` |
| 6 | **Uhrzeiten-Bezug** | `hatUhrzeit` **und nicht** `hatWochentag` **und nicht** `hatWhenCodes` **und** `hatZulaessigeLegacyFelder('d')` |
| 7 | **Kombination von Zeitintervallen** | `istNichtTagesmuster` **und** (`hatUhrzeit` **oder** `hatWhenCodes`) **und nicht** `hatWochentag` **und** `repeat.periodUnit` ∈ {`d`, `wk`, `mo`} |
| 8 | **Wiederkehrende Intervalle** | `istReinesIntervall` |
| – | **Abbruch** | trifft keine Regel zu |

**Bedarf als Querschnittsmerkmal:** Nur der **reine** Bedarf (ohne `timing`, Regel 2) ist ein eigenes Schema. Ist zusätzlich ein `timing` vorhanden, wird über die Regeln 3–8 das strukturierte Schema bestimmt; die Bedarfskennzeichnung (`asNeededBoolean`, Einnahmeanlass, Mindestabstand, Maximalmenge) wird dann beim Zusammensetzen als Präfix/Suffix ergänzt (siehe [Schema für Bedarfsmedikation](#schema-für-bedarfsmedikation)).

---

## Teil B: Aufbau je Schema

Ein generierter Dosierungstext folgt grundsätzlich dem Aufbau:

```
[{Zeitrahmen}: ] [{Intervall}: ] [{Wochentag} ][{Zeit- oder Tagesabschnittsangabe} — ]je {Dosis}[. Hinweis: {Instruktionen}]
```

`{…}` kennzeichnet einen Platzhalter, `[...]` einen optionalen Bestandteil, der nur erscheint, wenn die zugehörige Angabe vorliegt. Klammern können geschachtelt werden; eine äußere optionale Klammer entfällt vollständig, wenn alle inneren Bestandteile fehlen.

> Dieses Muster dient nur der groben Orientierung; **verbindlich sind die schemaspezifischen Muster** in den folgenden Abschnitten. Zwei Punkte sind dabei zu beachten: Der **Doppelpunkt ist nicht obligatorisch** — er trennt Zeitrahmen und Intervall von der Dosis und entfällt vollständig, wenn beides fehlt (das 4‑Schema ohne Zeitrahmen lautet schlicht `1-0-2-0 Stück`). Und **Wochentags- und Intervallschemata schließen sich gegenseitig aus**; ein `{Wochentag}` steht deshalb nie rechts eines Intervall-Doppelpunkts.

In den Schemata von Teil B bezeichnet `{Dosis}` den formatierten Dosiswert einschließlich optionaler Einheit, jedoch **ohne** das Wort `je`; deshalb steht in den ausgeschriebenen Mustern ausdrücklich `je {Dosis}`. Der in Teil A beschriebene vollständige Dosis-Baustein entspricht somit `je {Dosis}`.

Je nach Schema werden einzelne Bestandteile weggelassen oder unterschiedlich kombiniert. Stehen mehrere Uhrzeiten, Tagesabschnitte oder Wochentage zur Verfügung, entstehen getrennte Segmente. Das kompakte **4‑Schema** und die **Bedarfsmedikation** stellen Ausnahmen von diesem allgemeinen Aufbau dar.

### Schema mit Tageszeiten-Bezug (4-Schema)

```
[{Zeitrahmen}: ]<MORN>-<NOON>-<EVE>-<NIGHT> {Einheit}[. Hinweis: {Instruktionen}]
```

Nicht belegte Positionen erhalten den Wert `0`.

Die Werte werden über alle `Dosage`-Elemente eingesammelt. Für jedes Element wird dessen Dosis allen `when`-Codes dieses Elements zugeordnet. Die Dosis-Einheit der Ausgabe stammt aus dem ersten Element mit auswertbarer Dosis. Ein Tagesabschnitt darf nur einmal belegt sein; eine doppelte Belegung führt defensiv zu einem Fehler. Ein Code außerhalb der [Tagesabschnitts-Tabelle](#tagesabschnitt-when-codes) führt ebenfalls zum Abbruch. `frequency`, `frequencyMax`, `period`, `periodMax` und `periodUnit` beeinflussen die Ausgabe dieses Schemas nicht.

*Beispiel:* `für 5 Tage: 1-1-1-1 Kapseln`

**Variabilität:** Enthält eine der Positionen einen variablen Wert (Bereich), wird das kompakte Schema in die ausgeschriebene Segmentform (nur belegte Positionen) überführt, z. B. `morgens — je 1 bis 2 Stück, abends — je 2 Stück`. Feste 4‑Schemata bleiben kompakt (`1-0-2-0 Stück`).

### Schema mit Uhrzeiten-Bezug

```
[{Zeitrahmen} ]täglich: {Zeitgruppe} — je {Dosis}[, {Zeitgruppe2} — je {Dosis2} …][. Hinweis: {Instruktionen}]
```

Alle `timeOfDay`-Werte werden über sämtliche `Dosage`-Elemente hinweg gemeinsam aufsteigend sortiert. Eine `{Zeitgruppe}` fasst dabei die unmittelbar aufeinanderfolgenden Uhrzeiten zusammen, die sich dieselbe Dosis teilen; sie wird über einen Gedankenstrich mit dieser Dosis verbunden. Mehrere Gruppen werden mit Komma getrennt. Der Marker lautet in diesem Schema immer `täglich`; vorhandene Frequenzwerte werden hier nicht zusätzlich ausgegeben.

*Beispiele:* `täglich: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück` · bei zwei Uhrzeiten mit gleicher Dosis: `täglich: 08:00 Uhr, 20:00 Uhr — je 1 Stück` · trennt eine abweichende Dosis die Uhrzeiten, bleibt die Sortierung maßgeblich: `täglich: 01:00 Uhr — je 1 Stück, 18:00 Uhr — je 3 Stück, 23:00 Uhr — je 1 Stück`

### Schema mit Wochentags-Bezug

```
[{Zeitrahmen}: ]{Wochentag} — je {Dosis}[; {Wochentag2} — je {Dosis2} …][. Hinweis: {Instruktionen}]
```

Jeder belegte Tag bildet mit seiner Dosis ein Segment. Mehrere Segmente werden in kanonischer Reihenfolge der Wochentage sortiert und mit Semikolon getrennt; das gilt auch, wenn die Dosis zwischen mehreren oder allen Wochentagen übereinstimmt. `frequency`, `frequencyMax`, `period`, `periodMax` und `periodUnit` beeinflussen die Ausgabe dieses Schemas nicht; ein `periodUnit = 'wk'` erzeugt insbesondere kein zusätzliches „wöchentlich".

*Beispiel:* `montags — je 1 Stück; mittwochs — je 2 Stück`

Die Dosis-Einheit stammt aus dem ersten Element mit auswertbarer Dosis. Wird bei nicht profilkonformem Input derselbe Wochentag mehrfach mit unterschiedlicher Dosis belegt, bricht der Algorithmus ab: `ValueError("Doppelte Belegung des Wochentags '{code}' mit unterschiedlicher Dosis.")`

### Schema für wiederkehrende Intervalle

```
[{Zeitrahmen} ]{Intervall}: je {Dosis}[. Hinweis: {Instruktionen}]
```

*Beispiele:* `alle 4 Stunden: je 1 Stück` · mit Dosis-Bereich: `alle 8 Stunden: je 1 bis 2 Stück`

### Schema für Kombinationen von Zeitintervallen

```
[{Zeitrahmen} ]{Einnahmerhythmus}: {Zeit oder Abschnitt} — je {Dosis}[, … ][. Hinweis: {Instruktionen}]
```

Jede Uhrzeit oder jeder Tagesabschnitt bildet gemeinsam mit seiner Dosis ein Segment. Das gilt auch, wenn die Dosis zwischen mehreren oder allen Segmenten übereinstimmt. Segmente mit Tagesabschnitten werden in der festen Reihenfolge morgens, mittags, abends, zur Nacht sortiert; Segmente mit Uhrzeiten anhand des Eingabestrings aufsteigend. Treten – bei nicht profilkonformem Input über mehrere `Dosage`-Elemente hinweg – beide Arten gemeinsam auf, stehen **alle** Tagesabschnitte vor **allen** Uhrzeiten. Die Segmente werden mit Komma getrennt. Wird bei nicht profilkonformem Input derselbe Zeit-Schlüssel (Uhrzeit oder Tagesabschnitt) mehrfach mit unterschiedlicher Dosis belegt, bricht der Algorithmus ab: `ValueError("Doppelte Belegung des Zeit-Schlüssels '{zeit}' mit unterschiedlicher Dosis.")`; profilkonformer Input verhindert diesen Mehrdeutigkeitsfall.

Der gemeinsame Einnahmerhythmus wird aus `period`, `periodMax` und `periodUnit`
gebildet. Eine vorhandene `frequency` wird nicht ausgegeben, weil die Anzahl der
Anwendungen bereits aus den aufgeführten `timeOfDay`- beziehungsweise
`when`-Segmenten hervorgeht.


*Beispiel:* `alle 2 Tage: 08:00 Uhr — je 1 Stück, 18:00 Uhr — je 2 Stück`

### Schema für Kombinationen von Wochentagen

```
Aufbau (mit Uhrzeiten):        [{Zeitrahmen}: ]{Wochentag} {Zeit} — je {Dosis}[; …][. Hinweis: {Instruktionen}]
Aufbau (mit Tagesabschnitten): [{Zeitrahmen}: ]{Wochentag} <MORN>-<NOON>-<EVE>-<NIGHT> {Einheit}[; …][. Hinweis: {Instruktionen}]
```

Jeder belegte Tag bildet mit seinen Uhrzeiten oder seinem Tagesabschnitts-Muster ein Segment. Mehrere Segmente werden in kanonischer Reihenfolge der Wochentage sortiert und mit Semikolon getrennt; das gilt auch, wenn die Angabe zwischen mehreren oder allen Wochentagen übereinstimmt. Innerhalb eines Tages werden alle Uhrzeiten dieses Tages über sämtliche `Dosage`-Elemente hinweg gemeinsam aufsteigend sortiert; unmittelbar aufeinanderfolgende Uhrzeiten mit derselben Dosis stehen vor einem gemeinsamen Gedankenstrich. Uhrzeitgruppen werden mit Komma getrennt. Tagesabschnitte werden zum Vier-Positionen-Muster zusammengezogen.

*Beispiele:*

* `montags 08:00 Uhr — je 1 Stück, 12:00 Uhr — je 2 Stück; mittwochs 20:00 Uhr — je 1 Stück`
* `montags 1-0-1-0 Stück; mittwochs 2-1-2-0 Stück`

Bei der Kombination mit Tagesabschnitten stammt die gemeinsame Einheit aus dem ersten Element mit auswertbarer Dosis. Wird bei nicht profilkonformem Input dieselbe Kombination aus Wochentag und Tagesabschnitt mehrfach mit unterschiedlicher Dosis belegt, bricht der Algorithmus ab: `ValueError("Doppelte Belegung der Kombination aus Wochentag '{code}' und Zeit-/Tagesabschnitt '{zeit}' mit unterschiedlicher Dosis.")` Wie beim reinen Wochentags-Schema beeinflussen `frequency` sowie das redundante Paar `period = 1`, `periodUnit = wk` die Ausgabe nicht. `frequencyMax`, `periodMax` und jede andere Periode sind in diesem Schema nicht zulässig (siehe [Schema-Erkennung](#schema-erkennung)).

**Variabilität:** Enthält **irgendein** Tag einen variablen Wert (Bereich), wird die ausgeschriebene Segmentform für **alle** Tage verwendet, damit die Notation über den gesamten Text einheitlich bleibt — z. B. `montags morgens — je 1 bis 2 Stück; mittwochs abends — je 2 Stück`. Sind alle Werte fest, bleiben alle Tage kompakt (`montags 1-0-1-0 Stück; mittwochs 2-1-2-0 Stück`).

### Schema für Bedarfsmedikation

Eine Bedarfsmedikation liegt vor, wenn auf Ebene der `Dosage` `asNeededBoolean = true` gesetzt ist. Sie kann als **reine Bedarfsdosierung** (ohne `timing`) oder als **Kennzeichnung eines strukturierten Dosierschemas** auftreten (siehe [Bedarfsmedikation](https://ig.fhir.de/igs/medication/schema-bedarfsmedikation.html)).

Bei einer **reinen Bedarfsdosierung** muss die Ressource genau ein `Dosage`-Element enthalten (Invariante `AsNeededSingleDosageOnly`). Mehrere Dosen ohne zeitliche Zuordnung wären nicht eindeutig zu einem gemeinsamen Text zusammenführbar. Der Algorithmus bricht deshalb auch bei nicht vorab validiertem Input mit mehreren `Dosage`-Elementen ab.

```
[{Zeitrahmen} ]bei {Einnahmeanlass}: [im Abstand von mindestens {Mindestabstand} ]je {Dosis}[ — nicht mehr als {Maximalmenge}][. Hinweis: {Instruktionen}]
```

* Sofern vorhanden, steht der **Zeitrahmen** am Anfang, gefolgt vom **Einnahmeanlass** und einem **Doppelpunkt**. Der Doppelpunkt steht damit direkt hinter dem Einnahmeanlass.
* Ist kein Einnahmeanlass angegeben, wird generisch `bei Bedarf` gesetzt.
* Auch hier wird **nicht** großgeschrieben; `bei Kopfschmerzen: …` und `bei Bedarf: …` bleiben Fragmente wie jeder andere erzeugte Text.
* Ein optionaler **Mindestabstand** (`modifierExtension[MinimumIntervalBetweenAdministrations]`) steht rechts des Doppelpunkts vor der Dosis. Er ist nur bei reiner Bedarfsdosierung zulässig; bei strukturiertem Bedarf folgt dort stattdessen das jeweilige Schema (Intervall, 4‑Schema …).
  Die **Maximalmenge** wird genau einmal am Ende der Dosierungsanweisung angefügt. Enthält die Anweisung mehrere Uhrzeit-, Tagesabschnitts- oder Wochentagssegmente, steht die Maximalmenge nach dem letzten Segment. Sie gilt für die Gesamtmenge im angegebenen Zeitraum. Ein anschließender `Hinweis: ` folgt erst danach.

*Beispiele:*

* `bei Kopfschmerzen: im Abstand von mindestens 4 Stunden je 1 Stück — nicht mehr als 6 Stück in 24 Stunden`
* `bei Bedarf: täglich 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück — nicht mehr als 6 Stück pro Tag`
* `bei Kopfschmerzen: alle 8 Stunden je 1 Stück — nicht mehr als 4 Stück in 24 Stunden`
* `bei Bedarf: 1-0-2-0 Stück`

### Freitext-Dosierung

```
{Text}
```

Enthält die `Dosage` ausschließlich freien Text (`text` vorhanden, `timing` **und** `doseAndRate` leer), wird dieser übernommen. Alle drei Bedingungen gehören zur Erkennungsregel: Stünde neben dem Text eine strukturierte Dosis, müsste der Algorithmus raten, welche der beiden Angaben gilt — deshalb greift dann nicht die Freitext-Regel, sondern die reguläre Schema-Erkennung.

Bei reinem Freitext darf die Ressource **genau ein** `Dosage`-Element enthalten (Invariante `FreeTextSingleDosageOnly`), und `Dosage.text` ist `0..1`; bei profilkonformem Input gibt es also genau **ein** Textfeld. Der Algorithmus entfernt an dessen Anfang und Ende Leerraum. Der verbleibende Inhalt wird ansonsten unverändert ausgegeben.

*Beispiel:* `Nach Bedarf bei Schmerzen`

Zwei Hinweise zum Verhalten bei nicht profilkonformem Input — hier bricht der Algorithmus bewusst **nicht** ab, weil `DosageDE` beide Konstellationen lediglich als Warnung führt (`FreeTextSingleDosageOnlyWarning`, `DosageStructuredOrFreeTextWarning`) und ein Abbruch damit auch gültige DE-Instanzen träfe:

* Liegen **mehrere** reine Freitext-Elemente vor, wird jeder Text einzeln getrimmt; leere Werte entfallen, die übrigen werden in Dokumentreihenfolge mit einem Leerzeichen verbunden.
* `Dosage.text` wird in **allen strukturierten Schemata vollständig ignoriert** — das Feld wird dort ausschließlich für die Schema-Erkennung gelesen und erscheint nie im erzeugten Text.

---

## Feldreferenz und Mehrfach-Dosage

### Feldreferenz

Die folgende Tabelle nennt für jeden dynamischen Baustein den genauen Lese-Pfad relativ zum `Dosage`-Element. Maßgeblich für Kardinalität und Definition sind die Profil- und Extension-Seiten des [Medication IG DE](https://ig.fhir.de/igs/medication/); diese Tabelle beschreibt, welchen Unterpfad der Algorithmus tatsächlich ausliest.

| Baustein | Lese-Pfad (relativ zu `Dosage`) | Ausgelesene Werte |
|----------|--------------------------------|-------------------|
| Dosis (fest) | `doseAndRate[0].doseQuantity` | `.value`, `.unit` |
| Dosis (Bereich) | `doseAndRate[0].doseRange` | `.low.value`, `.high.value`, `.unit` (für `low` und `high` identisch — erzwungen durch Invariante `DoseRangeLowAndHighSameUnit`) |
| Dauer | `timing.repeat.boundsDuration` | `.value`, Einheit aus `.code` |
| Start-/Endzeitpunkt | `timing.repeat.boundsPeriod` | `.start`, `.end` |
| Intervall | `timing.repeat.frequency` / `.frequencyMax` / `.period` / `.periodMax` / `.periodUnit` | Unter-/Obergrenzen und Einheit |
| Wochentage | `timing.repeat.dayOfWeek` | Code-Liste |
| Uhrzeiten | `timing.repeat.timeOfDay` | Zeit-Liste |
| Tagesabschnitt | `timing.repeat.when` | Code-Liste |
| Bedarfskennzeichen | `asNeededBoolean` | `true` |
| Einnahmeanlass | `extension` mit URL `…/extension-Dosage.asNeededFor` → `valueCodeableConcept.text` | Freitext |
| Mindestabstand | `modifierExtension` mit URL `…/MinimumIntervalBetweenAdministrations` → `valueDuration` | `.value`, Einheit aus `.code` |
| Maximalmenge | `maxDosePerPeriod` | `numerator.value`, `numerator.unit`; `denominator.value` + `denominator.code` (nur `1 d` oder `24 h`) |
| Hinweis | `patientInstruction` | einzelner String (`0..1`) |
| Freitext | `text` | String |

**Extension-URLs (kanonisch):**

* Einnahmeanlass: `http://hl7.org/fhir/5.0/StructureDefinition/extension-Dosage.asNeededFor`
* Mindestabstand: `http://ig.fhir.de/igs/medication/StructureDefinition/MinimumIntervalBetweenAdministrations`

Beide Extensions werden über ihre **exakte kanonische `url`** identifiziert.

> Zur `asNeededFor`-Extension: Die kanonische URL `http://hl7.org/fhir/5.0/StructureDefinition/extension-Dosage.asNeededFor` stammt aus FHIR R5, wird hier aber gemäß dem Cross-Version-Extension-Pattern bewusst für ein R4-Profil (FHIR 4.0.1) zurückportiert. Das ist ein im FHIR-Ökosystem etabliertes Vorgehen, um R5-Konzepte in R4-Implementierungen vorwegzunehmen.

> Alle vom Algorithmus nicht ausgewerteten `Timing`- und `Dosage`-Felder (z. B. Count, CountMax, Method, Site, Rate\*, MaxDosePerAdministration, MaxDosePerLifetime, Offset, BoundsRange, Event) sind in der vollständigen Liste der zukünftig unterstützten Dosierkonfigurationen auf [Beispiele von erzeugten Dosiertexten](https://ig.fhir.de/igs/medication/dosierung-beispiele.html) aufgeführt.

### Aggregation mehrerer Dosage-Elemente

Für **unterschiedliche** Dosierungen, die sich nicht in einem einzelnen `Dosage`-Element abbilden lassen (z. B. unterschiedliche Dosis je Wochentag oder je Uhrzeit), werden **mehrere** `Dosage`-Elemente verwendet. Invarianten (z. B. `TimingSingleDosageForTimeOfDay`, `TimingSingleDosageForWhen`) verhindern dabei eine **unnötige** Aufteilung: Mehrere Elemente sind nur zulässig, wenn jedes Element eine eindeutige vollständige Dosis einschließlich ihres Datentyps (`Quantity` oder `Range`) trägt. Für die Textgenerierung gilt:

* **Segmente** (Uhrzeit-, Tagesabschnitts- und Wochentagssegmente) werden über **alle** `Dosage`-Elemente eingesammelt und gemeinsam sortiert. Ein Segment kann daher aus demselben oder aus verschiedenen `Dosage`-Einträgen stammen; im erzeugten Text erscheinen sie zusammengeführt (siehe Trennzeichen-Regeln). Dies betrifft die Schemata 4‑Schema, Uhrzeiten, Wochentage, Wochentag-Kombinationen und Intervall-Kombinationen.
* Die **Rahmen-Angaben** – Zeitrahmen (Dauer/Start-Ende), Bedarfskennzeichen inkl. Einnahmeanlass, Mindestabstand und Maximalmenge sowie der abschließende Hinweis – werden **ausschließlich aus dem ersten** `Dosage`-Element gelesen. Dass sie über alle Elemente konsistent sind, ist keine bloße Annahme, sondern wird durch Invarianten erzwungen: `TimingOnlyOneBounds` (Dauer sowie Start/Ende), `AsNeededIdentical`, `AsNeededForIdentical` und `PatientInstructionIdentical`. Ohne sie könnte eine abweichende Angabe in einem späteren Element unbemerkt entfallen — bei Maximalmenge, Mindestabstand oder Bedarfskennzeichen mit unmittelbarer Auswirkung auf die Arzneimittelsicherheit.
* Bei den Schemata **wiederkehrende Intervalle** und **reine Bedarfsmedikation** ist jeweils genau ein `Dosage`-Element zulässig. Dies erzwingen `TimingIntervalOnlyOneFrequency` beziehungsweise `AsNeededSingleDosageOnly`; eine Segment-Aggregation findet daher nicht statt.

Bei profilkonformem Input ist die resultierende Reihenfolge der Segmente **deterministisch** und hängt nicht von der Reihenfolge der `Dosage`-Elemente ab (Uhrzeiten aufsteigend, Tagesabschnitte in fester Reihenfolge, Wochentage kanonisch).

Die gemeinsame Dosis-Einheit aggregierender 4‑ und Wochentagsschemata wird aus der ersten angetroffenen auswertbaren Dosis übernommen; `DosageDoseUnitSameCode` stellt ihre Konsistenz über alle beteiligten Elemente sicher.

---

## Zusammensetzung typischer Muster

Für eine Übersicht der im Medication IG DE bereitgestellten Beispiele siehe [Beispiele von erzeugten Dosiertexten](https://ig.fhir.de/igs/medication/dosierung-beispiele.html).

## Fehler und Validierung

Die formale Definition zulässiger Felder und Kombinationen liegt in den Timing- und Dosierungs-Invarianten des Medication IG DE (siehe [Constraints](https://ig.fhir.de/igs/medication/dosierung-constraints.html)). Der Algorithmus führt **keine vollständige Validierung** und keine Auflistung unzulässiger Felder durch. Sein konkretes Fehlerverhalten lautet:

* nicht unterstützter `resourceType`: Abbruch mit `ValueError("Unsupported resource type: {resourceType}")`
* nicht klassifizierbare Merkmalskombination: Abbruch mit `ValueError("Die Dosierung entspricht keinem unterstützten Dosierungsschema.")`. Es wird **kein** Ersatztext zurückgegeben — ein solcher würde als generierte Dosieranweisung publiziert und dort eine Aussage vortäuschen, die der Algorithmus nicht treffen kann.
* `timeOfDay` und `when` im selben `Dosage`-Element (Verstoß gegen die FHIR-Basisinvariante `tim-10`): Abbruch mit `ValueError("timeOfDay und when dürfen nicht gemeinsam angegeben werden (tim-10).")`
* mehrere `Dosage`-Elemente, sobald eines davon eine reine Bedarfsdosierung (`asNeededBoolean = true` ohne `timing`) ist: Abbruch mit `ValueError("Reine Bedarfsmedikation erlaubt genau ein Dosage-Element.")`
* fehlendes oder leeres `doseAndRate`: Abbruch mit `ValueError("doseAndRate ist für die Textgenerierung erforderlich.")`
* `doseAndRate[0]` ohne `doseQuantity` oder `doseRange`: Abbruch mit `ValueError("Dosisangabe in doseAndRate[0] fehlt.")`
* `doseQuantity` ohne `.value` oder `.unit`: Abbruch mit `ValueError("doseQuantity.value ist für die Textgenerierung erforderlich.")` beziehungsweise `ValueError("doseQuantity.unit ist für die Textgenerierung erforderlich.")`
* nicht numerischer Dosiswert in `doseQuantity.value`, `doseRange.low.value` oder `doseRange.high.value`: Abbruch mit `ValueError("<Feld> muss numerisch sein.")`. Zahlen und numerische Strings werden akzeptiert, Boolesche Werte nicht
* `doseQuantity.value <= 0`: Abbruch mit `ValueError("doseQuantity.value muss größer als 0 sein.")`
* `doseRange` ohne erforderliche obere Grenze: Abbruch mit `ValueError("doseRange.high.value ist für die Textgenerierung erforderlich.")`; eine fehlende Einheit führt entsprechend zu `ValueError("doseRange.high.unit ist für die Textgenerierung erforderlich.")`
* `doseRange.high.value <= 0`: Abbruch mit `ValueError("doseRange.high.value muss größer als 0 sein.")`
* vorhandenes `doseRange.low` ohne `.value` oder `.unit`: Abbruch mit der entsprechenden Fehlermeldung für `doseRange.low.value` beziehungsweise `doseRange.low.unit`
* `maxDosePerPeriod` zusammen mit einem `timing`: Abbruch mit `ValueError("Eine Maximalmenge ist nur bei reiner Bedarfsmedikation zulaessig, nicht zusammen mit einem strukturierten Rhythmus.")`
* mehrere `Dosage`-Elemente mit unterschiedlichem Schema: Abbruch mit `ValueError("Alle Dosage-Elemente müssen demselben Schema folgen; Element 1 ergibt '{schema1}', Element {n} '{schemaN}'.")`
* vorhandenes `doseRange.low.value < 0`: Abbruch mit `ValueError("doseRange.low.value darf nicht negativ sein.")`. Der Wert `0` ist hier — anders als bei `doseQuantity` und `doseRange.high` — zulässig, weil er die Untergrenze einer variablen Dosis wie „0 bis 2 Stück“ bildet
* unterschiedliche Einheiten in `doseRange.low` und `doseRange.high`: Abbruch mit `ValueError("doseRange.low.unit und doseRange.high.unit müssen übereinstimmen.")`
* vorhandenes `boundsDuration` ohne `.value` oder `.code`: Abbruch mit einer entsprechenden Pflichtfeldmeldung; ein nicht numerischer Wert oder ein Wert `<= 0` führt zu `ValueError("boundsDuration.value muss größer als 0 sein.")`
* gleichzeitig vorhandenes `boundsPeriod` und `boundsDuration`: Abbruch mit `ValueError("boundsPeriod und boundsDuration dürfen nicht gleichzeitig vorhanden sein.")`
* `boundsPeriod` ohne `start` und `end`: Abbruch mit `ValueError("boundsPeriod muss start und/oder end enthalten.")`
* nicht parsebares oder unvollständiges `boundsPeriod.start` beziehungsweise `.end` sowie eine Uhrzeit ohne Zeitzone: Abbruch mit einer Meldung, dass das Feld ein parsebares FHIR-`dateTime` mit vollständigem Datum sein und eine Uhrzeit eine Zeitzone enthalten muss
* nicht parsebares oder außerhalb des zulässigen Bereichs liegendes `timeOfDay`: Abbruch mit `ValueError("timeOfDay muss im Format HH:MM oder HH:MM:SS[.Bruchteile] angegeben sein.")`
* `asNeededFor` ohne nicht leeres `valueCodeableConcept.text`: Abbruch mit `ValueError("asNeededFor.valueCodeableConcept.text ist für die Textgenerierung erforderlich.")`
* Extension `MinimumIntervalBetweenAdministrations` ohne `valueDuration`: Abbruch mit `ValueError("MinimumIntervalBetweenAdministrations.valueDuration ist für die Textgenerierung erforderlich.")`; für fehlende Unterfelder und Werte `<= 0` gelten die entsprechenden Meldungen mit dem Pfad `MinimumIntervalBetweenAdministrations.valueDuration`
* `maxDosePerPeriod` ohne `numerator.value`, `numerator.unit`, `denominator.value` oder `denominator.code`: Abbruch mit einer entsprechenden Pflichtfeldmeldung
* nicht numerisches `maxDosePerPeriod.numerator.value`: Abbruch mit `ValueError("maxDosePerPeriod.numerator.value muss numerisch sein.")`
* anderer Nenner als `1 d` oder `24 h`: Abbruch mit `ValueError("maxDosePerPeriod.denominator muss 1 d oder 24 h sein.")`
* Intervall-Kombination ohne `period` oder `periodUnit`: Abbruch mit `ValueError("Intervall-Kombinationen erfordern period und periodUnit.")`
* `when`-Code außerhalb der [Tagesabschnitts-Tabelle](#tagesabschnitt-when-codes): Abbruch mit `ValueError("Nicht unterstützter Tagesabschnitt (when): '{code}'.")`
* doppelte Belegung eines Tagesabschnitts im reinen 4‑Schema: Abbruch mit `ValueError("Doppelte Belegung des Tagesabschnitts '{code}' im 4-Schema.")`
* doppelte Belegung desselben Wochentags mit unterschiedlicher Dosis im Wochentags-Schema: Abbruch mit `ValueError("Doppelte Belegung des Wochentags '{code}' mit unterschiedlicher Dosis.")`
* doppelte Belegung derselben Kombination aus Wochentag und Tagesabschnitt mit unterschiedlicher Dosis: Abbruch mit `ValueError("Doppelte Belegung der Kombination aus Wochentag '{code}' und Zeit-/Tagesabschnitt '{zeit}' mit unterschiedlicher Dosis.")`
* doppelte Belegung desselben Zeit-Schlüssels mit unterschiedlicher Dosis in einer Intervall-Kombination: Abbruch mit `ValueError("Doppelte Belegung des Zeit-Schlüssels '{zeit}' mit unterschiedlicher Dosis.")`
* Zeiteinheit außerhalb der [Einheiten-Tabelle](#einheiten-und-pluralisierung) in `periodUnit`, `boundsDuration.code` oder beim Mindestabstand: Abbruch mit `ValueError("Nicht unterstützte Zeiteinheit: '{code}'.")`

Der Algorithmus ist so ausgelegt, dass er im Zweifel **abbricht, statt einen zweifelhaften Text zu erzeugen**: Eine Angabe, die er nicht eindeutig darstellen kann, führt zum Fehler und nicht zu einem Ersatz- oder Teiltext. Die wenigen dokumentierten Ausnahmen betreffen Konstellationen, die das Profil `DosageDE` lediglich als Warnung führt (mehrere Freitext-Elemente, Freitext neben strukturierten Angaben) — dort würde ein Abbruch auch gültige DE-Instanzen treffen.

Andere Profilverletzungen können je nach fehlendem Feld dennoch zu einem unvollständigen Text oder zu einem Laufzeitfehler führen. Die Profilvalidierung muss deshalb vor der Textgenerierung erfolgen.

## Versionierung

Die Version des verwendeten Algorithmus MUSS über die Extension [GeneratedDosageInstructionsMeta](https://ig.fhir.de/igs/medication/StructureDefinition-GeneratedDosageInstructionsMeta.html) gesetzt werden. So lassen sich Textinhalt und verwendete Algorithmus-Version nachvollziehbar prüfen.

Diese Seite beschreibt die Algorithmus-Version **2.0.0-ballot**. Die Nummer bezeichnet den hier festgelegten Algorithmus, nicht ein einzelnes Programm: Die Beispielimplementierung führt sie in `__version__` und gibt sie beim Erzeugen der Beispiele in `algorithmVersion` weiter. Eine eigene Implementierung trägt dieselbe Nummer ein, sobald sie diesen Algorithmus umsetzt.

Damit bestimmt dieses Dokument die Versionsfolge: **Eine neue Versionsnummer entsteht genau dann, wenn sich diese Spezifikation ändert.** Korrekturen, die ausschließlich die Referenzimplementierung, ihre Tests oder die CI betreffen, ändern das festgelegte Verhalten nicht und lassen die Nummer unberührt. Die Versionshistorie führt [CHANGELOG.md](CHANGELOG.md); dort trennt jeder Eintrag beides voneinander.

Ob eine Änderung die Haupt- oder die Nebenversion erhöht, richtet sich danach, ob sich bereits erzeugte Texte ändern können: Ein geänderter oder entfallener Baustein und jede Verschärfung der Eingabeprüfung erhöhen die Hauptversion, weil bestehende Ausgaben davon abweichen. Ein zusätzliches Schema oder eine gelockerte Prüfung, die vorhandene Ausgaben unberührt lässt, erhöht die Nebenversion.

## Quellen / weiterführende Hinweise

* UK Core Implementation Guide for Medicines (Dose to Text Translation)
* NHS CUI User Interface Design Guidance (2015)
* Australian Commission: National Guidelines for On-Screen Display of Medicines Information (2017)
