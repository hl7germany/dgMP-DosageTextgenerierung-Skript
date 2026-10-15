Diese Seite beschreibt die Erzeugung eines menschenlesbaren Dosierungstextes aus einer gesamten Arzneimittel‑Ressource (`MedicationRequest`, `MedicationDispense` oder `MedicationStatement`).

**Verbindlich ist der auf dieser Seite beschriebene Algorithmus.** Er ist die normative Festlegung der Textgenerierung; Implementierungen müssen ihn nachbilden, unabhängig von der gewählten Programmiersprache. Die aktuelle Version des Algorithmus ist **2.0.0-ballot** (siehe [Versionierung](#versionierung)).

Zur Veranschaulichung steht eine **Beispielimplementierung** als [Python-Skript](https://github.com/hl7germany/dgMP-DosageTextgenerierung-Skript/blob/main/medication-dosage-to-text.py) bereit, mit der auch die Beispieltexte dieses Implementation Guides erzeugt werden. Das Skript führt die umgesetzte Algorithmus-Version in `__version__`; sie entspricht der hier angegebenen.

**Teil A** beschreibt, wie jede einzelne Angabe einer `Dosage` in Text überführt wird. **Teil B** beschreibt, wie diese Bausteine je Schema zu einem vollständigen Dosierungstext zusammengesetzt werden.

Der gesamte Fließtext dieser Seite ist verbindlich, ebenso die Codeblöcke mit Mustern und Pseudocode. Eingerückte Blöcke (`>`) enthalten ausschließlich Unverbindliches: Orientierungshilfen, Hintergrund und Verweise auf andere Dokumente.

> Variable Angaben (Frequenz, Periode, Einzeldosis) werden durchgängig mit dem Wort „bis" gebildet (z. B. „1 bis 2 Stück"). Enthält das kompakte 4‑Schema einen variablen Wert oder verschiedene Einheiten, wird es in die ausgeschriebene Segmentform überführt (siehe [4‑Schema](#schema-mit-tageszeiten-bezug-4-schema)).

---

## Grundsätze

**Vorbedingung der Textgenerierung ist eine gegen die dgMP-Profile des Medication IG DE validierte Ressource.** Im Profil gestrichene Elemente sind nicht Teil der Verarbeitung. Der Algorithmus prüft weder Wertebereiche noch Kardinalitäten oder Invarianten, die den Text nicht berühren. Er bricht nur aus drei Gründen ab:

1. Der Text ist **nicht bildbar**: Eine Angabe fehlt, ist nicht lesbar oder liegt außerhalb der festgelegten Tabellen.
2. Der Text wäre **falsch oder mehrdeutig**: Er würde eine Angabe der Ressource unterschlagen oder ließe sich in zwei Bedeutungen lesen.
3. Ein gelesenes Feld hat den **falschen JSON-Datentyp**.

In diesen Fällen bricht der Algorithmus ab; es gibt keinen Ersatz- oder Teiltext. Ein Wert von `0` ist kein Abbruchgrund; ein negativer Dosiswert führt zum Abbruch, weil er keine sinnvolle Anweisung darstellt (Grund 1). Jede Meldung ist unter [Fehler und Validierung](#fehler-und-validierung) festgelegt; die Abschnitte dieser Seite verweisen mit „Grund 1“ bis „Grund 3“ auf die Aufzählung oben.

Jeder strukturiert erzeugte Text ist ein Fragment in einer Zeile: Der Algorithmus schreibt den Textanfang nicht groß (`bei Kopfschmerzen: …`, `3 x täglich: …`) und hängt keinen Schlusspunkt an; ein Punkt am Ende kann nur aus einem übernommenen Teil stammen (Dosiereinheit, Hinweis). Die Freitext-Dosierung wird unverändert übernommen.

Ohne Abbruch gehen nicht in den Text ein: Felder außerhalb der [Feldreferenz](#feldreferenz) mit Ausnahme einer `modifierExtension` mit anderer URL, die zum Abbruch führt (Schritt 3); `Dosage.text` in strukturierten Schemata; `asNeededBoolean` und Einnahmeanlass an einer Freitext-Dosierung; abweichende Rahmen-Angaben weiterer `Dosage`-Elemente (siehe [Aggregation](#aggregation-mehrerer-dosage-elemente)). Grund 2 bezieht sich nur auf gelesene Angaben.

---

## Gesamtalgorithmus

Die Verarbeitung erfolgt in dieser Reihenfolge:

1. Anhand von `resourceType` wird die Liste der Dosierungen gelesen:
   * `MedicationRequest.dosageInstruction`
   * `MedicationDispense.dosageInstruction`
   * `MedicationStatement.dosage`
2. Bei einem anderen Ressourcentyp wird abgebrochen (`Unsupported resource type: {resourceType}`, Grund 1; fehlt `resourceType`, ist `{resourceType}` leer). Ist die gelesene Liste leer oder fehlt sie, ist das Ergebnis ein leerer String.
3. Jedes gelesene Feld muss den JSON-Datentyp seines FHIR-Typs haben: `decimal` eine Zahl, `positiveInt` eine ganze Zahl, `boolean` ein boolescher Wert, `string`, `code`, `time` und `dateTime` ein String, Listenfelder (`dayOfWeek`, `when`, `timeOfDay`, `doseAndRate`, `extension`, `modifierExtension`) eine Liste, Strukturfelder (`timing`, `timing.repeat`, `boundsDuration`, `boundsPeriod`, die Elemente von `doseAndRate` mit `doseQuantity`, `doseRange`, `low`, `high`, `maxDosePerPeriod` mit `numerator` und `denominator`, die Elemente von `extension` und `modifierExtension` mit `valueCodeableConcept` beziehungsweise `valueDuration`) ein Objekt. Strings, auch numerische wie `"2"`, und boolesche Werte gelten nicht als Zahl; ein Feld mit dem Wert `null` gilt als vorhanden mit falschem Typ. Geprüft werden nur Felder, die der Algorithmus liest, in **jedem** `Dosage`-Element: von `doseAndRate` nur der erste Eintrag, von `extension` und `modifierExtension` neben der `url` nur die Werte der beiden bekannten Extensions (siehe [Feldreferenz](#feldreferenz)). Ein falscher Typ führt zum Abbruch (Grund 3). Ebenfalls zum Abbruch führt ein vorhandener `comparator` in einer gelesenen `Quantity` (`doseQuantity`, `doseRange.low`/`.high`, `maxDosePerPeriod.numerator`/`.denominator`, `boundsDuration`, `valueDuration`); der Text würde den Vergleichsoperator unterschlagen (Grund 2). Eine `modifierExtension` mit einer anderen URL als der des Mindestabstands führt zum Abbruch (`Nicht unterstützte modifierExtension: '{url}'.`, Grund 2): Sie verändert die Bedeutung des Elements und darf nicht entfallen. Die Prüfung erfolgt vor der Schema-Erkennung.
4. Setzt eines der `Dosage`-Elemente `timeOfDay` **und** `when` gemeinsam (FHIR-Basisinvariante `tim-10`), wird abgebrochen (Grund 2). Danach wird für jedes `Dosage`-Element in Dokumentreihenfolge geprüft, auch für Freitext-Elemente: (a) jede `asNeededFor`-Extension trägt einen nicht leeren Text und das Element das Bedarfskennzeichen; (b) ein Mindestabstand ist vollständig, das Element trägt das Bedarfskennzeichen, kein `timing` und ist keine Freitext-Dosierung; (c) eine Maximalmenge ist vollständig mit Nenner `1 d` oder `24 h`, das Element trägt das Bedarfskennzeichen, kein `timing` und ist keine Freitext-Dosierung. Die erste verletzte Bedingung bestimmt die Meldung (siehe [Einnahmeanlass](#einnahmeanlass-asneededfor), [Mindestabstand](#mindestabstand-zwischen-gaben) und [Maximalmenge](#maximalmenge-maxdoseperperiod)).
5. Enthält die Liste eine reine Bedarfsdosierung (`asNeededBoolean = true` ohne `timing`, auch ein Freitext-Element) und insgesamt nicht genau ein `Dosage`-Element, wird abgebrochen (Grund 2).
6. Das Darstellungsschema wird anhand des **ersten** `Dosage`-Elements in der unter [Schema-Erkennung](#schema-erkennung) angegebenen Priorität bestimmt. Zuerst wird für jedes weitere Element geprüft, dass es dasselbe Schema ergibt (Meldung „Alle Dosage-Elemente müssen demselben Schema folgen …“, auch wenn das erste Element keiner Regel entspricht und `Unknown` ergibt); trifft danach für das erste Element keine Regel zu, wird abgebrochen (Grund 1). Es wird **kein** Ersatztext erzeugt.
7. Der schemaspezifische Generator sammelt die Dosis-/Zeitsegmente über alle `Dosage`-Elemente; welche Angaben nur aus dem ersten Element stammen, ist unter [Aggregation mehrerer Dosage-Elemente](#aggregation-mehrerer-dosage-elemente) festgelegt.
8. Der Generator setzt den Text zusammen: links des Doppelpunkts Zeitrahmen, Bedarfsangaben und Rhythmus-Teil, rechts den Kern des Schemas (siehe [Teil B](#teil-b-aufbau-je-schema)). Danach werden – außer bei Freitext – Maximalmenge und `patientInstruction` ergänzt.
9. Abschließend wird der Text – außer bei Freitext – normalisiert.

Das folgende Pseudocode-Gerüst zeigt den vollständigen Kontrollfluss:

```text
dosierungen = extrahiereDosierungen(resource)
wenn dosierungen leer: return ""

wenn irgendein gelesenes Feld den falschen JSON-Datentyp hat
oder eine gelesene Quantity einen comparator traegt
oder eine modifierExtension eine unbekannte url hat:
  Fehler

wenn irgendeine dosierung timeOfDay und when gemeinsam setzt:
  Fehler

fuer jede dosierung in Dokumentreihenfolge:
  fuer jeden Einnahmeanlass: wenn Text leer oder kein Bedarfskennzeichen: Fehler
  wenn Mindestabstand: wenn unvollstaendig, kein Bedarfskennzeichen,
                       timing vorhanden oder Freitext-Dosierung: Fehler
  wenn Maximalmenge:   wenn unvollstaendig, Nenner nicht 1 d/24 h,
                       kein Bedarfskennzeichen, timing vorhanden
                       oder Freitext-Dosierung: Fehler

wenn irgendeine dosierung reine Bedarfsdosierung ist
und anzahl(dosierungen) != 1:
  Fehler

schema = erkenneSchema(dosierungen[0])   # ggf. unbekannt
fuer jede weitere dosierung:
  wenn erkenneSchema(dosierung) != schema: Fehler
wenn schema unbekannt: Fehler

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

Dezimalwerte werden mit **deutschem Dezimalkomma** ausgegeben (z. B. `1,5`). Die Zahl wird mit **genau der Genauigkeit** ausgegeben, mit der sie in der Ressource steht: `1` → `1`, `1.0` → `1,0`, `2.50` → `2,50`. FHIR legt fest, dass die Genauigkeit eines `decimal` einschließlich nachfolgender Nullen Bedeutung trägt (`0.010` ist nicht `0.01`) und auch für die Darstellung zu erhalten ist. Eine Implementierung muss das JSON deshalb mit einem Parser lesen, der diese Genauigkeit erhält (etwa `BigDecimal`, in Python `parse_float=Decimal`); ein Gleitkomma-Parser verwirft nachfolgende Nullen bereits beim Einlesen. Exponentialschreibweise aus der Ressource wird als Dezimalzahl ausgegeben (`1e-2` → `0,01`). Die Anzahl der Nachkommastellen ist nicht eingeschränkt; Werte werden ohne Rundung übernommen. Dieselbe Darstellung gilt für alle Zahlen im Text (Frequenz, Periode, Dauer, Mindestabstand, Maximalmenge).

Eine Dosis ist in **jedem** strukturierten Schema erforderlich. Fehlt `doseAndRate`, bricht der Algorithmus ab (Grund 1).

`doseQuantity.value` und `doseQuantity.unit` sind verpflichtend; eine Einheit, die leer ist oder nur aus Leerraum besteht, gilt als fehlend (ebenso `doseRange.high.unit`). Fehlt eine dieser Angaben, bricht der Algorithmus ab (Grund 1). `je 0 Stück` wird ausgegeben; ein negativer Wert führt zum Abbruch (`doseQuantity.value darf nicht negativ sein.`, Grund 1).

Bei `doseRange` muss die Obergrenze mit `high.value` und `high.unit` vorhanden sein. Ist zusätzlich `low` vorhanden, muss auch `low.value` vorhanden sein. Die Ausgabeeinheit stammt aus `high.unit`; `low.unit` erscheint nicht im Text und wird nicht verlangt. Ist `low.unit` vorhanden und weicht von `high.unit` ab, bricht der Algorithmus ab (Grund 2). Eine fehlende Pflichtangabe führt ebenso zum Abbruch wie ein `doseAndRate[0]` ohne `doseQuantity` und ohne `doseRange` (Grund 1); ein negativer Wert in `low` oder `high` ebenfalls (`doseRange.low.value darf nicht negativ sein.` beziehungsweise `doseRange.high.value darf nicht negativ sein.`).

Der so gebildete Dosis-Baustein – einschließlich der **Bereichsform** (`je {von} bis {bis} {Einheit}`) – ist in **allen** Schemata einsetzbar; überall dort, wo in Teil B der Platzhalter `{Dosis}` steht, kann ein fester Wert **oder** ein Bereich stehen (z. B. `alle 8 Stunden: je 1 bis 2 Stück`).

**Ausnahme:** Im kompakten 4‑Schema entfällt das vorangestellte `je`; dort erscheinen die Dosiswerte positionell (siehe Teil B).

### Zeitrahmen

#### Dauer (`boundsDuration`)

Eine begrenzte Anwendungsdauer wird vorangestellt als `für {Wert} {Einheit}`. Die Einheit wird nach den Regeln unter [Einheiten und Pluralisierung](#einheiten-und-pluralisierung) ausgegeben, z. B. `für 1 Tag` bzw. `für 7 Tage`.

`boundsDuration.value` und `boundsDuration.code` sind verpflichtend, sobald `boundsDuration` vorhanden ist; fehlt eine der Angaben, bricht der Algorithmus ab (Grund 1).

#### Start- und Endzeitpunkt (`boundsPeriod`)

Start- und/oder Endzeitpunkt werden vorangestellt:

* nur Start (offenes Ende): `ab dem {Startdatum}[ um {Uhrzeit}]`
* Start und Ende: `vom {Startdatum}[ um {Uhrzeit}] bis zum {Enddatum}[ um {Uhrzeit}]`
* nur Ende: `bis zum {Enddatum}[ um {Uhrzeit}]`

Das Datum wird im Format `TT.MM.JJJJ`, eine vorhandene Uhrzeit im Format `HH:MM Uhr` ausgegeben. Sekunden und Sekundenbruchteile werden nicht dargestellt; FHIR erlaubt beliebig viele Bruchteilstellen und die Schaltsekunde `60`, beides wird akzeptiert.

Sind `boundsPeriod` und `boundsDuration` gleichzeitig vorhanden, bricht der Algorithmus ab (Grund 2). Ein vorhandenes `boundsPeriod` muss `start` und/oder `end` enthalten (Grund 1). Jeder vorhandene Wert muss als FHIR-`dateTime` mit vollständigem Datum `JJJJ-MM-TT` parsebar sein (Grund 1). Bei einer reinen Datumsangabe erfolgt keine Zeitzonenverarbeitung. Enthält der Wert eine Uhrzeit, muss gemäß FHIR eine Zeitzone als `Z` oder Offset vorhanden sein. Der Zeitpunkt wird in die verbindliche IANA-Zielzeitzone `Europe/Berlin` umgerechnet; erst danach werden das gegebenenfalls verschobene Datum sowie Stunde und Minute formatiert. Die Umrechnung berücksichtigt automatisch Sommer- und Winterzeit.

*Beispiel:* `2026-06-05T23:30:45Z` wird in `Europe/Berlin` zu `06.06.2026 um 01:30 Uhr`, im Text also `ab dem 06.06.2026 um 01:30 Uhr`.

### Einnahmerhythmus (`frequency` / `period` / `periodUnit`)

Aus `frequency`, `frequencyMax`, `period`, `periodMax` und `periodUnit` entsteht der einleitende Rhythmus:

* tägliches Muster (`periodUnit='d'`, `period=1`, `periodMax` fehlt): `täglich` bei `frequency=1` und fehlendem `frequencyMax`, sonst `{Frequenzwert} x täglich`
* wöchentliches Muster (`periodUnit='wk'`, `period=1`, `periodMax` fehlt): `wöchentlich` bei `frequency=1` und fehlendem `frequencyMax`, sonst `{Frequenzwert} x wöchentlich`
* monatliches Muster (`periodUnit='mo'`, `period=1`, `periodMax` fehlt): `monatlich` bei `frequency=1` und fehlendem `frequencyMax`, sonst `{Frequenzwert} x monatlich`
* sonstige Perioden bei einer **festen Frequenz von genau 1** (`frequency=1`, `frequencyMax` fehlt): `alle {Periodenwert} {Einheit}` (z. B. `alle 8 Stunden`)
* sonstige Perioden bei einem **Frequenzbereich** (`frequencyMax` vorhanden, auch bei `frequency=1`) oder einer festen Frequenz größer als 1: `{Frequenzwert} x alle {Periodenwert} {Einheit}` (z. B. `1 bis 2 x alle 8 Stunden` beziehungsweise `2 x alle 8 Stunden`)

`{Frequenzwert}` bezeichnet entweder `frequency` allein oder `frequency bis frequencyMax`; `{Periodenwert}` entsprechend `period` allein oder `period bis periodMax`. Die Perioden-Einheit wird nach den Regeln unter [Einheiten und Pluralisierung](#einheiten-und-pluralisierung) ausgegeben. Beispiele für Bereiche sind `2 bis 3 x täglich` und `alle 2 bis 3 Tage`. Eine Periode `1` mit vorhandenem `periodMax` ist ein Periodenbereich und fällt unter die sonstigen Perioden: `alle 1 bis 3 Tage`, nicht `täglich`.

Diese Frequenzdarstellung gilt für das reine Intervallschema. In der Intervall-Kombination wird eine vorhandene `frequency` nicht ausgegeben; der gemeinsame Einnahmerhythmus wird ausschließlich aus `period`, `periodMax` und `periodUnit` gebildet, mit denselben Kurzformen für `1 wk` und `1 mo` ohne `periodMax`.

Fehlen `frequency`, `period` und `periodUnit` vollständig, wird kein Baustein für den Einnahmerhythmus erzeugt; das ist nur in Schemata möglich, deren zeitlicher Bezug durch `when`, `timeOfDay` oder `dayOfWeek` bestimmt wird. Das reine Intervallschema erfordert `frequency`, `period` und `periodUnit`, die Intervall-Kombination `period` und `periodUnit`. Sind die erforderlichen Angaben unvollständig, greift keine Schema-Regel und die Verarbeitung bricht ab.

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

Die Tabelle ist **abschließend**; ein Code außerhalb der Tabelle führt zum Abbruch (Grund 1). Der Algorithmus prüft nicht, ob ein Code für das jeweilige Feld zulässig ist.

> Welche Codes je Feld zulässig sind, legen die gebundenen ValueSets des Profils fest (`PeriodUnitsOfTimeDgMPVS`, `DurationUnitsOfTimeDgMPVS`, `MindestabstandUnitsOfTimeDgMPVS`).

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

Die Tabelle ist **abschließend**; ein Code außerhalb der Tabelle führt zum Abbruch (Grund 1).

### Konkrete Zeiten (`timeOfDay`)

Uhrzeiten werden anhand ihres Eingabestrings aufsteigend sortiert und im Format `HH:MM Uhr` ausgegeben (z. B. `08:00 Uhr`). Akzeptiert werden nullaufgefüllte Werte im Format `HH:MM` oder `HH:MM:SS` mit optionalen Sekundenbruchteilen. Stunde und Minute werden übernommen, Sekunden und Sekundenbruchteile entfallen (auch die Schaltsekunde `60` wird akzeptiert). Ein nicht parsebarer oder außerhalb des zulässigen Uhrzeitbereichs liegender Wert führt zum Abbruch (Grund 1). Da die Werte nullaufgefüllt sind, entspricht die Sortierung nach dem Eingabestring der chronologischen Reihenfolge. Alle Uhrzeiten werden über **sämtliche** `Dosage`-Elemente hinweg eingesammelt und gemeinsam aufsteigend sortiert. Die Reihenfolge der `Dosage`-Elemente in der Ressource hat damit keinen Einfluss auf die Reihenfolge der Uhrzeiten im Text.

Im Uhrzeiten-Schema und in der Wochentags-Kombination werden unmittelbar aufeinanderfolgende Uhrzeiten mit **derselben** Dosis anschließend vor einem gemeinsamen Gedankenstrich mit Komma zusammengefasst, z. B. `08:00 Uhr, 20:00 Uhr — je 1 Stück`; in der Intervall-Kombination bildet jede Uhrzeit ein eigenes Segment. Liegt eine Uhrzeit mit abweichender Dosis dazwischen, entsteht für jede Uhrzeit ein eigenes Segment; die aufsteigende Sortierung hat Vorrang vor der Zusammenfassung.

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

Die Tabelle ist **abschließend**; ein Code außerhalb der Tabelle führt zum Abbruch (Grund 1). `when` und `timeOfDay` dürfen nicht gemeinsam auftreten (`tim-10`, siehe Schritt 4).

Je nach Schema erscheinen die Codes entweder als kompaktes, positionelles Muster (4‑Schema) oder als einzelne Abschnittsangaben analog zu Uhrzeiten (siehe Teil B).

### Einnahmeanlass (`asNeededFor`)

Der Einnahmeanlass wird bei Bedarfsmedikation vorangestellt als `bei {Anlass}` (z. B. `bei Kopfschmerzen`). Der Einnahmeanlass ist **optional**; fehlt er, wird generisch `bei Bedarf` gesetzt. Ein Einnahmeanlass ohne Bedarfskennzeichen führt zum Abbruch (`Ein Einnahmeanlass (asNeededFor) setzt asNeededBoolean = true voraus.`, Grund 2).

Es können **mehrere** Einnahmeanlässe angegeben sein (`asNeededFor 0..*`, fachlich ODER-verknüpft). Sie werden in der angegebenen Reihenfolge als **deutsche Aufzählung** verbunden: alle bis auf den letzten mit Komma, der letzte mit „ oder " (kein Komma vor „oder"):

* 2 Anlässe: `bei Kopfschmerzen oder Fieber`
* 3+ Anlässe: `bei Kopfschmerzen, Fieber oder Gliederschmerzen`

Details zur Zusammensetzung siehe [Schema für Bedarfsmedikation](#schema-für-bedarfsmedikation).

Ausgewertet werden nur Extensions mit der exakten kanonischen URL aus der [Feldreferenz](#feldreferenz). Von jeder passenden Extension wird ausschließlich `valueCodeableConcept.text` übernommen; fehlt ein nicht leerer Text, bricht der Algorithmus ab (Grund 1). Führender und abschließender Leerraum des Textes wird entfernt.

### Mindestabstand zwischen Gaben

Der Baustein lautet `im Abstand von mindestens {Wert} {Zeiteinheit}` und steht vor der Dosis. Der Mindestabstand ist nur bei einer reinen Bedarfsdosierung (`asNeededBoolean = true`, kein `timing`) mit `doseAndRate` zulässig (Invariante `MinimumIntervalOnlyPureAsNeeded`). Andernfalls bricht der Algorithmus ab (Grund 2): ohne Bedarfskennzeichen mit `Ein Mindestabstand setzt asNeededBoolean = true voraus.`, zusammen mit einem `timing` mit `Ein Mindestabstand ist nur bei reiner Bedarfsmedikation zulässig, nicht zusammen mit einem strukturierten Rhythmus.`, an einer Freitext-Dosierung mit `Ein Mindestabstand ist bei einer Freitext-Dosierung nicht darstellbar.`; fehlt bei einer reinen Bedarfsdosierung ohne Text das `doseAndRate`, gilt die Dosis-Regel (`doseAndRate ist für die Textgenerierung erforderlich.`, Grund 1).

Der Algorithmus durchsucht `modifierExtension` nach der exakten kanonischen URL `MinimumIntervalBetweenAdministrations` und verwendet die erste passende Extension. `valueDuration`, `valueDuration.value` und `valueDuration.code` sind verpflichtend; fehlt eine der Angaben, bricht der Algorithmus ab (Grund 1), und zwar vor der Prüfung der Vorbedingungen (Schritt 4). Die Formatierung von Wert und Einheit entspricht `boundsDuration`, jedoch ohne das Wort `für`; die Einheit wird aus `valueDuration.code` nach der [Einheiten-Tabelle](#einheiten-und-pluralisierung) abgeleitet.

> Das Profil beschränkt `valueDuration.code` auf `min` und `h` (`MindestabstandUnitsOfTimeDgMPVS`).

### Maximalmenge (`maxDosePerPeriod`)

Die Maximalmenge wird der Dosis nachgestellt als `nicht mehr als {Wert} {Einheit} {Zeitraum}`. Als Bezugszeitraum ist ausschließlich **24 Stunden** oder **1 Tag** zulässig (Invariante `MaxDosePerPeriodOnly24hOr1d`). Der Nenner wird numerisch geprüft und unabhängig von seiner Schreibweise (`24` oder `24.0`) fest ausgegeben:

* `24 h` → `in 24 Stunden`
* `1 d` → `pro Tag`

`{Einheit}` ist `numerator.unit`, wörtlich übernommen.

Die Maximalmenge ist nur bei einer reinen Bedarfsdosierung (`asNeededBoolean = true`, kein `timing`) mit `doseAndRate` zulässig (Invariante `MaxDoseOnlyPureAsNeeded`). Andernfalls bricht der Algorithmus ab (Grund 2): ohne Bedarfskennzeichen mit `Eine Maximalmenge setzt asNeededBoolean = true voraus.`, zusammen mit einem `timing` mit `Eine Maximalmenge ist nur bei reiner Bedarfsmedikation zulässig, nicht zusammen mit einem strukturierten Rhythmus.`, an einer Freitext-Dosierung mit `Eine Maximalmenge ist bei einer Freitext-Dosierung nicht darstellbar.`; fehlt bei einer reinen Bedarfsdosierung ohne Text das `doseAndRate`, gilt die Dosis-Regel (Grund 1).

Ist `maxDosePerPeriod` vorhanden, müssen `numerator.value`, `numerator.unit` (nicht leer), `denominator.value` und `denominator.code` vorhanden sein; als Nenner werden ausschließlich `1 d` und `24 h` akzeptiert. Fehlende oder andere Angaben führen zum Abbruch (Grund 1), und zwar vor der Prüfung der Vorbedingungen (Schritt 4).

### Freitext-Hinweise (`patientInstruction`)

Ergänzende Einnahmehinweise werden aus `patientInstruction` (einzelner String, `0..1`) als abschließender Satz mit vorangestelltem `Hinweis:` wiedergegeben (z. B. `Hinweis: Mit ausreichend Wasser einnehmen`). Führender und abschließender Leerraum des Feldwerts wird entfernt; ein danach leerer Wert wird nicht ausgegeben.

Der Hinweis wird als **eigener Satz** angehängt. Der bisherige strukturierte Dosierungstext erhält einen abschließenden Punkt, gefolgt von `Hinweis: {Text}`. Endet der Text, nach Entfernen abschließenden Leerraums, bereits mit einem Punkt, wird kein zweiter ergänzt. Beispiel: `täglich: 1-0-1-0 Stück. Hinweis: Nach dem Essen`.

`additionalInstruction`, `route` und `doseAndRate.rate[x]` werden nicht gelesen (siehe [Feldreferenz](#feldreferenz)).

### Trennzeichen

* **Doppelpunkt mit Leerzeichen** (`: `) trennt die Dosieranweisung in zwei Abschnitte. In den strukturierten Schemata stehen links des Doppelpunkts, sofern vorhanden, der Zeitrahmen und das Intervall beziehungsweise der Marker `täglich`; beide teilen sich einen Doppelpunkt (`für 7 Tage alle 2 Tage: …`). Bei Bedarfsmedikation gilt dasselbe: Zeitrahmen, Einnahmeanlass und Intervall stehen links des Doppelpunkts, ein Komma trennt den Einnahmeanlass vom Intervall (`bei Kopfschmerzen, alle 8 Stunden: je 1 Stück`). Ohne Intervall steht der Doppelpunkt direkt hinter dem Einnahmeanlass (`bei Kopfschmerzen: je 1 Stück`).
* **Gedankenstrich mit Leerzeichen** (` — `) verbindet eine Zeit- oder Abschnittsangabe mit der zugehörigen Dosis sowie die Dosis mit der Maximalmenge im Falle einer Bedarfsmedikation.
* **Komma mit Leerzeichen** (`, `) trennt aufeinanderfolgende Segmente unterschiedlicher **Tages- oder Uhrzeiten**, unabhängig davon, ob sie aus derselben oder aus verschiedenen `Dosage`-Einträgen stammen. Bei Bedarfsmedikation mit Intervall trennt es außerdem den Einnahmeanlass vom Intervall (`bei Blutzucker über 250, 2 x täglich: …`).
* **Semikolon mit Leerzeichen** (`; `) trennt aufeinanderfolgende **Wochentagssegmente**, unabhängig davon, ob sie aus derselben oder aus verschiedenen `Dosage`-Einträgen stammen.
* **Bindestrich** (`-`) trennt die vier Positionen des 4‑Schemas.

#### Zeichenrepertoire

Die folgenden Zeichen sind für den erzeugten Text **verbindlich festgelegt**. Maßgeblich ist jeweils der Codepoint, nicht die optische Ähnlichkeit — mehrere der Zeichen haben verwechselbare Varianten, die **nicht** verwendet werden dürfen.

| Zeichen | Codepoint | Name | Verwendung | Nicht verwenden |
|---------|-----------|------|------------|-----------------|
| `—` | U+2014 | EM DASH | Zeit-/Abschnittsangabe ↔ Dosis; Dosis ↔ Maximalmenge | `–` U+2013, `―` U+2015, `-` U+002D |
| `-` | U+002D | HYPHEN-MINUS | die vier Positionen des 4‑Schemas | `‐` U+2010, `−` U+2212, `–` U+2013 |
| `,` | U+002C | COMMA | Segmenttrennung, Einnahmeanlass ↔ Intervall bei Bedarf **und** deutsches Dezimalkomma | `،` U+060C |
| `;` | U+003B | SEMICOLON | Trennung von Wochentagssegmenten | `;` U+037E |
| `:` | U+003A | COLON | Abschnittstrennung sowie Stunde:Minute | `∶` U+2236 |
| `.` | U+002E | FULL STOP | Satzende vor `Hinweis:` sowie Tag.Monat.Jahr | `․` U+2024 |
| `x` | U+0078 | LATIN SMALL LETTER X | Frequenzmarker in `3 x täglich` | `×` U+00D7, `✕` U+2715 |
| ` ` | U+0020 | SPACE | einziges Trennzeichen zwischen Wörtern | `&nbsp;` U+00A0, U+2009, U+202F |

Für die Umlaute in den festen Wortbestandteilen (`täglich`, `wöchentlich`, `für`) gilt die **vorkomponierte NFC-Form**: `ä` U+00E4, `ö` U+00F6, `ü` U+00FC — **nicht** die zerlegte Form aus Grundbuchstabe und kombinierendem Trema (`a` + U+0308). Alle vom Algorithmus erzeugten Wortbestandteile sind NFC-normalisiert; aus dem Input übernommene Teile (siehe unten) werden nicht normalisiert, der Gesamttext ist also genau dann NFC, wenn es der Input ist. Ein `ß` kommt in keinem vom Algorithmus erzeugten Wortbestandteil vor.

Nicht Teil dieses Repertoires sind Zeichen, die **unverändert aus dem Input übernommen** werden: die Dosiereinheit (`doseQuantity.unit`), der Einnahmeanlass (`asNeededFor`), der Hinweis (`patientInstruction`) und der Freitext (`Dosage.text`). Ihre Zeichen werden weder ersetzt noch normalisiert; einzig Leerraum in den übernommenen Teilen strukturierter Texte unterliegt der nachfolgenden Normalisierung.

Strukturierte Schemata erzeugen keine Zeilenumbrüche; ihr Text steht in einer Zeile. Die Freitext-Dosierung durchläuft die nachfolgende Normalisierung nicht und wird unverändert übernommen, einschließlich enthaltener Zeilenumbrüche und führenden oder abschließenden Leerraums (`FreeTextMatchesRenderedText` verlangt exakte Gleichheit mit `Dosage.text`).

**Normalisierung:** Nach dem Zusammensetzen wird der Text normalisiert – dies gilt für **alle Schemata außer der Freitext-Dosierung**:

* In strukturiert erzeugten Texten wird **jede** Folge von Leerraum – jedes Unicode-Leerraumzeichen, also auch Tabs, Zeilenumbrüche und geschützte Leerzeichen wie U+00A0, unabhängig von ihrer Herkunft – zu **einem** Leerzeichen (U+0020) reduziert. Damit steht ein strukturiert erzeugter Text auch dann in einer Zeile, wenn ein übernommenes Freitextfeld (`patientInstruction`, Einnahmeanlass, Dosiereinheit) selbst einen Umbruch enthält. Freitext-Dosierungen werden nicht normalisiert.
* Leerraum **unmittelbar vor** den Satzzeichen `;` `:` `.` `,` wird entfernt.
* Führende und abschließende Leerzeichen werden entfernt (trim).

Der Gedankenstrich (`—`) und Klammern bleiben dabei unangetastet.

**Deterministische Reihenfolge:** In strukturierten Schemata ist die Reihenfolge der Segmente im erzeugten Text **unabhängig von der Reihenfolge der `Dosage`-Elemente** in der Ressource. Segmente werden ausschließlich nach ihrem Inhalt sortiert (Uhrzeiten aufsteigend, Tagesabschnitte in fester Reihenfolge morgens → mittags → abends → zur Nacht, Wochentage kanonisch Montag → Sonntag).

---

## Schema-Erkennung

Bevor die Bausteine zusammengesetzt werden, wird genau **ein** Darstellungsschema bestimmt. Grundlage der Erkennung ist das **erste `Dosage`-Element**; das Schema gilt für die gesamte Ressource. Enthält sie mehrere Elemente, muss **jedes** zu demselben Schema führen, sonst bricht der Algorithmus ab (Grund 2).

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

In den Regeln 3 bis 6 werden `frequency` (mit beliebigem Wert) sowie das Paar `period = 1` mit der Periodeneinheit des Schemas (siehe Tabelle) als Legacy-Angaben geduldet: Sie begründen kein Intervallschema und **ändern die Ausgabe nicht**; eine Ressource mit und eine ohne diese Felder erzeugen denselben Text.

> In früheren Fassungen des Medication IG DE waren die drei Felder in allen Schemata verpflichtend; die Duldung hält solche Bestandsdaten gültig.

Die Bedingung `hatZulaessigeLegacyFelder` gilt für alle vier betroffenen Schemata; sie unterscheiden sich nur in der Periodeneinheit, die sich aus der impliziten Wiederholung des Schemas ergibt:

| Aufruf | geduldetes Paar | verwendet in |
|---|---|---|
| `hatZulaessigeLegacyFelder('wk')` | `period = 1`, `periodUnit = wk` | Regel 4 und 5 (Wochentage) |
| `hatZulaessigeLegacyFelder('d')` | `period = 1`, `periodUnit = d` | Regel 3 und 6 (Tagesabschnitte, Uhrzeiten) |

`frequency` wird in keiner der beiden Bedingungen geprüft; in diesen Schemata beeinflusst es weder die Schema-Erkennung noch die Ausgabe. Nur bei **wiederkehrenden Intervallen** (Regel 8) ist `frequency` keine Legacy-Angabe: Dort ist es konstituierend und erscheint im Text, etwa als `2 x alle 8 Stunden`.

Jede **andere** Periode beschreibt ein echtes Intervall: Bei `dayOfWeek` ist sie unzulässig, bei `when` oder `timeOfDay` führt sie über `istNichtTagesmuster` zu Regel 7. Eine variable Frequenz oder Periode ist bei Wochentagen ebenfalls ausgeschlossen.

> FHIR R4 merkt zu `timeOfDay` und `dayOfWeek` an, dass `frequency` und `period` nicht zusammen mit ihnen verwendet werden sollten; formalisiert ist nur `tim-10`. Der Medication IG DE lässt die Kombination zu: Die Legacy-Angaben halten Bestandsdaten gültig, die Intervall-Kombination bildet wöchentliche und monatliche Rhythmen mit konkreten Zeitpunkten ab.

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
| 7 | **Kombination von Zeitintervallen** | `istNichtTagesmuster` **und** (`hatUhrzeit` **oder** `hatWhenCodes`) **und nicht** `hatWochentag` **und nicht** `hatFrequenzMax` **und** `repeat.periodUnit` ∈ {`d`, `wk`, `mo`} |
| 8 | **Wiederkehrende Intervalle** | `istReinesIntervall` |
| – | **Abbruch** | trifft keine Regel zu |

**Bedarf als Querschnittsmerkmal:** Nur der **reine** Bedarf (ohne `timing`, Regel 2) ist ein eigenes Schema. Ist zusätzlich ein `timing` vorhanden, wird über die Regeln 3–8 das strukturierte Schema bestimmt; die Bedarfskennzeichnung (`asNeededBoolean`, Einnahmeanlass, Mindestabstand, Maximalmenge) wird dann beim Zusammensetzen als Präfix/Suffix ergänzt (siehe [Schema für Bedarfsmedikation](#schema-für-bedarfsmedikation)).

---

## Teil B: Aufbau je Schema

Ein generierter Dosierungstext folgt grundsätzlich dem Aufbau:

```
[[{Zeitrahmen} ][{Intervall}]: ][{Wochentag} ][{Zeit- oder Tagesabschnittsangabe} — ]je {Dosis}[. Hinweis: {Instruktionen}]
```

`{…}` kennzeichnet einen Platzhalter, `[...]` einen optionalen Bestandteil, der nur erscheint, wenn die zugehörige Angabe vorliegt. Klammern können geschachtelt werden; eine äußere optionale Klammer entfällt vollständig, wenn alle inneren Bestandteile fehlen.

> Dieses Muster dient nur der Orientierung; **verbindlich sind die schemaspezifischen Muster** in den folgenden Abschnitten. Der Doppelpunkt entfällt, wenn Zeitrahmen und Intervall fehlen (`montags — je 1 Stück`); Wochentags- und Intervallschemata schließen sich gegenseitig aus.

In den Schemata von Teil B bezeichnet `{Dosis}` den formatierten Dosiswert einschließlich Einheit, jedoch **ohne** das Wort `je`; deshalb steht in den ausgeschriebenen Mustern ausdrücklich `je {Dosis}`. Der in Teil A beschriebene vollständige Dosis-Baustein entspricht somit `je {Dosis}`.

Links des Doppelpunkts steht der **Rhythmus-Teil**: im 4‑Schema und im Uhrzeiten-Schema stets der Marker `täglich`, im Intervallschema der Rhythmus nach Teil A, in der Intervall-Kombination der Rhythmus aus `period`, `periodMax` und `periodUnit`; Wochentagsschemata haben keinen Rhythmus-Teil. Rechts des Doppelpunkts steht der **Kern des Schemas** (Muster, Segmente oder Dosis). Je nach Schema werden einzelne Bestandteile weggelassen oder unterschiedlich kombiniert. Stehen mehrere Uhrzeiten, Tagesabschnitte oder Wochentage zur Verfügung, entstehen getrennte Segmente. Das kompakte **4‑Schema** und die **Bedarfsmedikation** stellen Ausnahmen von diesem allgemeinen Aufbau dar.

### Schema mit Tageszeiten-Bezug (4-Schema)

```
[{Zeitrahmen} ]täglich: <MORN>-<NOON>-<EVE>-<NIGHT> {Einheit}[. Hinweis: {Instruktionen}]
```

Nicht belegte Positionen erhalten den Wert `0`.

Die Werte werden über alle `Dosage`-Elemente eingesammelt. Für jedes Element wird dessen Dosis samt Einheit allen `when`-Codes dieses Elements zugeordnet. Das kompakte Muster trägt eine gemeinsame Einheit, die aller belegten Positionen. Wird derselbe Tagesabschnitt mehrfach mit **unterschiedlicher** Dosis belegt, bricht der Algorithmus ab (Grund 2); dieselbe Dosis mehrfach ergibt denselben Text und ist wie in den übrigen Schemata zulässig. Eine Position, die explizit mit der Dosis `0` belegt ist, gilt als belegt und ist von einer nicht belegten Position zu unterscheiden; im kompakten Muster sehen beide gleich aus (`0`), in der ausgeschriebenen Form bleibt nur die belegte erhalten. Ein Code außerhalb der [Tagesabschnitts-Tabelle](#tagesabschnitt-when-codes) führt ebenfalls zum Abbruch.

Wie beim [Uhrzeiten-Schema](#schema-mit-uhrzeiten-bezug) lautet der Marker in diesem Schema immer `täglich`: Das Muster allein lässt offen, ob es an jedem Tag gilt. `frequency` sowie das Paar `period = 1`, `periodUnit = d` beeinflussen die Ausgabe dieses Schemas nicht. Mit `frequencyMax`, `periodMax` oder einer anderen Periode greift diese Regel nicht; die [Schema-Erkennung](#schema-erkennung) führt dann zu einem anderen Schema oder zum Abbruch.

*Beispiele:* `täglich: 1-0-2-0 Stück` · mit Zeitrahmen: `für 5 Tage täglich: 1-1-1-1 Kapseln`

**Ausgeschriebene Form:** Enthält eine der Positionen einen variablen Wert (Bereich) oder tragen die belegten Positionen **nicht alle dieselbe Einheit**, wird das kompakte Schema in die ausgeschriebene Segmentform (nur belegte Positionen) überführt, z. B. `täglich: morgens — je 1 bis 2 Stück, abends — je 2 Stück`. Jedes Segment trägt die Einheit seiner Dosis: `täglich: morgens — je 1 Stück, abends — je 2 Messlöffel`. Verglichen wird der Feldwert der Einheit (`doseQuantity.unit` beziehungsweise `doseRange.high.unit`) zeichengenau, vor der Leerraum-Normalisierung; der Code wird nicht verglichen. In der ausgeschriebenen Form bildet jeder belegte Tagesabschnitt ein eigenes Segment; gleiche Dosen werden nicht zusammengefasst. Eine explizit mit `0` belegte Position erscheint als Segment `morgens — je 0 Stück`. Feste 4‑Schemata mit einer Einheit bleiben kompakt (`täglich: 1-0-2-0 Stück`).

### Schema mit Uhrzeiten-Bezug

```
[{Zeitrahmen} ]täglich: {Zeitgruppe} — je {Dosis}[, {Zeitgruppe2} — je {Dosis2} …][. Hinweis: {Instruktionen}]
```

Alle `timeOfDay`-Werte werden über sämtliche `Dosage`-Elemente hinweg gemeinsam aufsteigend sortiert. Eine `{Zeitgruppe}` fasst dabei die unmittelbar aufeinanderfolgenden Uhrzeiten zusammen, die sich dieselbe Dosis teilen; sie wird über einen Gedankenstrich mit dieser Dosis verbunden. Mehrere Gruppen werden mit Komma getrennt. Der Marker lautet in diesem Schema immer `täglich`; vorhandene Frequenzwerte werden hier nicht zusätzlich ausgegeben. Dieselbe Uhrzeit (`HH:MM`) mit unterschiedlicher Dosis — auch über mehrere `Dosage`-Elemente hinweg — führt zum Abbruch (`Doppelte Belegung der Uhrzeit '{HH:MM Uhr}' mit unterschiedlicher Dosis.`, Grund 2); mit derselben Dosis wird sie nur einmal ausgegeben.

*Beispiele:* `täglich: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück` · bei zwei Uhrzeiten mit gleicher Dosis: `täglich: 08:00 Uhr, 20:00 Uhr — je 1 Stück` · trennt eine abweichende Dosis die Uhrzeiten, bleibt die Sortierung maßgeblich: `täglich: 01:00 Uhr — je 1 Stück, 18:00 Uhr — je 3 Stück, 23:00 Uhr — je 1 Stück`

### Schema mit Wochentags-Bezug

```
[{Zeitrahmen}: ]{Wochentag} — je {Dosis}[; {Wochentag2} — je {Dosis2} …][. Hinweis: {Instruktionen}]
```

Jeder belegte Tag bildet mit seiner Dosis ein Segment. Mehrere Segmente werden in kanonischer Reihenfolge der Wochentage sortiert und mit Semikolon getrennt; das gilt auch, wenn die Dosis zwischen mehreren oder allen Wochentagen übereinstimmt. `frequency` sowie das Paar `period = 1`, `periodUnit = wk` beeinflussen die Ausgabe dieses Schemas nicht; ein `periodUnit = 'wk'` erzeugt insbesondere kein zusätzliches „wöchentlich". Mit `frequencyMax`, `periodMax` oder einer anderen Periode greift diese Regel nicht; die [Schema-Erkennung](#schema-erkennung) führt dann zu einem anderen Schema oder zum Abbruch.

*Beispiel:* `montags — je 1 Stück; mittwochs — je 2 Stück`

Jedes Segment trägt die Einheit seines Elements (`montags — je 1 Stück; mittwochs — je 2 Messlöffel`). Wird derselbe Wochentag mehrfach mit unterschiedlicher Dosis belegt, bricht der Algorithmus ab (Grund 2): `ValueError("Doppelte Belegung des Wochentags '{code}' mit unterschiedlicher Dosis.")`

### Schema für wiederkehrende Intervalle

```
[{Zeitrahmen} ]{Intervall}: je {Dosis}[. Hinweis: {Instruktionen}]
```

*Beispiele:* `alle 4 Stunden: je 1 Stück` · mit Dosis-Bereich: `alle 8 Stunden: je 1 bis 2 Stück`

Es ist genau ein `Dosage`-Element zulässig; bei mehreren bricht der Algorithmus ab (`Wiederkehrende Intervalle erlauben genau ein Dosage-Element.`, Grund 2).

### Schema für Kombinationen von Zeitintervallen

```
[{Zeitrahmen} ]{Einnahmerhythmus}: {Zeit oder Abschnitt} — je {Dosis}[, … ][. Hinweis: {Instruktionen}]
```

Jede Uhrzeit oder jeder Tagesabschnitt bildet gemeinsam mit seiner Dosis ein Segment. Das gilt auch, wenn die Dosis zwischen mehreren oder allen Segmenten übereinstimmt. Segmente mit Tagesabschnitten werden in der festen Reihenfolge morgens, mittags, abends, zur Nacht sortiert; Segmente mit Uhrzeiten anhand des Eingabestrings aufsteigend. Treten über mehrere `Dosage`-Elemente hinweg beide Arten gemeinsam auf, stehen **alle** Tagesabschnitte vor **allen** Uhrzeiten. Die Segmente werden mit Komma getrennt. Maßgeblich für „dieselbe Uhrzeit" ist wie im Uhrzeiten-Schema die dargestellte Form `HH:MM` — `08:00` und `08:00:00` sind dieselbe Uhrzeit. Dieselbe Uhrzeit oder derselbe Tagesabschnitt mit derselben Dosis wird nur einmal ausgegeben; mit unterschiedlicher Dosis bricht der Algorithmus ab (Grund 2), mit denselben Meldungen wie im Uhrzeiten-Schema beziehungsweise im 4‑Schema: `ValueError("Doppelte Belegung der Uhrzeit '{HH:MM Uhr}' mit unterschiedlicher Dosis.")`, `ValueError("Doppelte Belegung des Tagesabschnitts '{code}' mit unterschiedlicher Dosis.")`.

Der gemeinsame Einnahmerhythmus wird aus `period`, `periodMax` und `periodUnit` des **ersten** `Dosage`-Elements gebildet. Weicht der Rhythmus eines weiteren Elements davon ab, bricht der Algorithmus ab (Grund 2): `ValueError("Alle Dosage-Elemente einer Intervall-Kombination müssen denselben Einnahmerhythmus tragen.")`. Eine vorhandene `frequency` wird nicht ausgegeben.

*Beispiel:* `alle 2 Tage: 08:00 Uhr — je 1 Stück, 18:00 Uhr — je 2 Stück`

### Schema für Kombinationen von Wochentagen

```
Aufbau (mit Uhrzeiten):        [{Zeitrahmen}: ]{Wochentag} {Zeit} — je {Dosis}[; …][. Hinweis: {Instruktionen}]
Aufbau (mit Tagesabschnitten): [{Zeitrahmen}: ]{Wochentag} <MORN>-<NOON>-<EVE>-<NIGHT> {Einheit}[; …][. Hinweis: {Instruktionen}]
```

Jeder belegte Tag bildet mit seinen Uhrzeiten oder seinem Tagesabschnitts-Muster ein Segment. Mehrere Segmente werden in kanonischer Reihenfolge der Wochentage sortiert und mit Semikolon getrennt; das gilt auch, wenn die Angabe zwischen mehreren oder allen Wochentagen übereinstimmt. Innerhalb eines Tages werden alle Uhrzeiten dieses Tages über sämtliche `Dosage`-Elemente hinweg gemeinsam aufsteigend sortiert; unmittelbar aufeinanderfolgende Uhrzeiten mit derselben Dosis stehen vor einem gemeinsamen Gedankenstrich. Uhrzeitgruppen werden mit Komma getrennt; für sie gilt die Duplikatregel des [Uhrzeiten-Schemas](#schema-mit-uhrzeiten-bezug). Tagesabschnitte werden zum Vier-Positionen-Muster zusammengezogen. Ob Uhrzeiten oder Tagesabschnitte verwendet werden, wird über **alle** `Dosage`-Elemente bestimmt; beides gemischt — auch an verschiedenen Tagen — führt zum Abbruch (`Wochentags-Kombinationen mit Uhrzeiten und mit Tagesabschnitten dürfen nicht gemischt werden.`, Grund 2).

*Beispiele:*

* `montags 08:00 Uhr — je 1 Stück, 12:00 Uhr — je 2 Stück; mittwochs 20:00 Uhr — je 1 Stück`
* `montags 1-0-1-0 Stück; mittwochs 2-1-2-0 Stück`

Bei der Kombination mit Tagesabschnitten trägt jeder Tag die Einheit seiner Positionen; verschiedene Einheiten an verschiedenen Tagen bleiben kompakt (`montags 1-0-0-0 Stück; mittwochs 2-0-0-0 mg`). Wird dieselbe Kombination aus Wochentag und Tagesabschnitt mehrfach mit unterschiedlicher Dosis belegt, bricht der Algorithmus ab (Grund 2): `ValueError("Doppelte Belegung der Kombination aus Wochentag '{code}' und Zeit-/Tagesabschnitt '{zeit}' mit unterschiedlicher Dosis.")` Wie beim reinen Wochentags-Schema beeinflussen `frequency` sowie das redundante Paar `period = 1`, `periodUnit = wk` die Ausgabe nicht. Mit `frequencyMax`, `periodMax` oder einer anderen Periode greift diese Regel nicht; die [Schema-Erkennung](#schema-erkennung) führt dann zu einem anderen Schema oder zum Abbruch.

**Ausgeschriebene Form:** Enthält **irgendein** Tag einen variablen Wert (Bereich) oder Positionen mit verschiedenen Einheiten, wird die ausgeschriebene Segmentform für **alle** Tage verwendet — z. B. `montags morgens — je 1 bis 2 Stück; mittwochs abends — je 2 Stück`. Der Wochentag steht einmal vor seinen Segmenten, die mit Komma getrennt werden (`montags morgens — je 1 bis 2 Stück, abends — je 2 Stück`); gleiche Dosen werden nicht zusammengefasst. Sind alle Werte fest, bleiben alle Tage kompakt (`montags 1-0-1-0 Stück; mittwochs 2-1-2-0 Stück`).

### Schema für Bedarfsmedikation

Eine Bedarfsmedikation liegt vor, wenn auf Ebene der `Dosage` `asNeededBoolean = true` gesetzt ist. Sie kann als **reine Bedarfsdosierung** (ohne `timing`) oder als **Kennzeichnung eines strukturierten Dosierschemas** auftreten (siehe [Bedarfsmedikation](https://ig.fhir.de/igs/medication/schema-bedarfsmedikation.html)).

Bei einer **reinen Bedarfsdosierung** muss die Ressource genau ein `Dosage`-Element enthalten (Invariante `AsNeededSingleDosageOnly`); bei mehreren bricht der Algorithmus ab (Grund 2).

```
Reine Bedarfsdosierung:     bei {Einnahmeanlass}: [im Abstand von mindestens {Mindestabstand} ]je {Dosis}[ — nicht mehr als {Maximalmenge}][. Hinweis: {Instruktionen}]
Bedarf mit Schema:         [{Zeitrahmen} ]bei {Einnahmeanlass}[, {Intervall}]: {Kern des Schemas}[. Hinweis: {Instruktionen}]
```

* Sofern vorhanden, steht der **Zeitrahmen** am Anfang, gefolgt vom **Einnahmeanlass**. Bei der reinen Bedarfsdosierung kann kein Zeitrahmen vorliegen, weil er in `timing.repeat` steht; er tritt nur bei strukturiertem Bedarf auf (`ab dem 05.06.2026 bei Bedarf, täglich: …`).
* Bei strukturiertem Bedarf folgt das **Intervall** beziehungsweise der Marker `täglich` des Schemas — wie ohne Bedarf links des Doppelpunkts —, durch ein Komma vom Einnahmeanlass getrennt: `bei Kopfschmerzen, alle 8 Stunden: je 1 Stück`. Schemata ohne Intervall (Wochentage) haben keinen solchen Teil: `bei Bedarf: montags — je 1 Stück`. Der **Doppelpunkt** steht damit immer am Ende des Teils, der sagt, wann und weshalb angewendet wird.
* Ist kein Einnahmeanlass angegeben, wird generisch `bei Bedarf` gesetzt.
* Ein optionaler [Mindestabstand](#mindestabstand-zwischen-gaben) steht rechts des Doppelpunkts vor der Dosis.
* Die [Maximalmenge](#maximalmenge-maxdoseperperiod) wird mit Gedankenstrich hinter der Dosis angefügt; ein `Hinweis: ` folgt erst danach.

*Beispiele:*

* `bei Kopfschmerzen: im Abstand von mindestens 4 Stunden je 1 Stück — nicht mehr als 6 Stück in 24 Stunden`
* `bei Bedarf, täglich: 08:00 Uhr — je 1 Stück, 20:00 Uhr — je 2 Stück`
* `bei Kopfschmerzen, alle 8 Stunden: je 1 Stück`
* `bei Bedarf, täglich: 1-0-2-0 Stück`
* `bei Bedarf: montags — je 1 Stück; mittwochs — je 2 Stück`

### Freitext-Dosierung

```
{Text}
```

Enthält die `Dosage` ausschließlich freien Text (`text` vorhanden, `timing` **und** `doseAndRate` leer), wird dieser übernommen. Steht neben dem Text ein `timing` oder ein `doseAndRate`, greift die reguläre Schema-Erkennung.

Das Profil verlangt bei reinem Freitext genau ein `Dosage`-Element (`FreeTextSingleDosageOnly`). Der Inhalt wird unverändert ausgegeben, auch führender und abschließender Leerraum (siehe [Zeichenrepertoire](#zeichenrepertoire)).

*Beispiel:* `Nach Bedarf bei Schmerzen`

Zwei Konstellationen, die das Profil ausschließt (`FreeTextSingleDosageOnly`, `DosageStructuredOrFreeText`), führen nicht zum Abbruch:

* Liegen **mehrere** reine Freitext-Elemente vor, werden sie unverändert in Dokumentreihenfolge mit einem Leerzeichen verbunden. Trägt eines davon `asNeededBoolean = true`, greift Schritt 5 und der Algorithmus bricht ab.
* `Dosage.text` wird in **allen strukturierten Schemata vollständig ignoriert** — das Feld wird dort ausschließlich für die Schema-Erkennung gelesen und erscheint nie im erzeugten Text.

`asNeededBoolean` und ein Einnahmeanlass an einer Freitext-Dosierung gehen nicht in den Text ein. Ein Mindestabstand oder eine Maximalmenge daneben führt zum Abbruch (siehe [Mindestabstand](#mindestabstand-zwischen-gaben) und [Maximalmenge](#maximalmenge-maxdoseperperiod)).

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

> Die URL der `asNeededFor`-Extension stammt aus FHIR R5 und wird als Cross-Version-Extension im R4-Profil verwendet.

> Alle vom Algorithmus nicht ausgewerteten `Timing`- und `Dosage`-Felder (z. B. `additionalInstruction`, `route`, `rate[x]`, `count`, `countMax`, `method`, `site`, `maxDosePerAdministration`, `maxDosePerLifetime`, `offset`, `boundsRange`, `event`) sind in der vollständigen Liste der aktuell nicht unterstützten Dosierkonfigurationen auf [Beispiele von erzeugten Dosiertexten](https://ig.fhir.de/igs/medication/dosierung-beispiele.html) aufgeführt.

### Aggregation mehrerer Dosage-Elemente

Für **unterschiedliche** Dosierungen, die sich nicht in einem einzelnen `Dosage`-Element abbilden lassen (z. B. unterschiedliche Dosis je Wochentag oder je Uhrzeit), werden **mehrere** `Dosage`-Elemente verwendet. Für die Textgenerierung gilt:

* **Segmente** (Uhrzeit-, Tagesabschnitts- und Wochentagssegmente) werden über **alle** `Dosage`-Elemente eingesammelt und gemeinsam sortiert. Ein Segment kann daher aus demselben oder aus verschiedenen `Dosage`-Einträgen stammen; im erzeugten Text erscheinen sie zusammengeführt (siehe Trennzeichen-Regeln). Dies betrifft die Schemata 4‑Schema, Uhrzeiten, Wochentage, Wochentag-Kombinationen und Intervall-Kombinationen.
* Die **Rahmen-Angaben** – Zeitrahmen (Dauer/Start-Ende), Bedarfskennzeichen inkl. Einnahmeanlass, Mindestabstand und Maximalmenge sowie der abschließende Hinweis – werden **ausschließlich aus dem ersten** `Dosage`-Element gelesen. Weicht eine Rahmen-Angabe in einem weiteren Element ab, bricht der Algorithmus **nicht** ab; ihre Gleichheit sichern die Invarianten `TimingOnlyOneBounds`, `AsNeededIdentical`, `AsNeededForIdentical` und `PatientInstructionIdentical`. Unabhängig davon gelten in jedem Element die Typ- und `comparator`-Prüfung (Schritt 3) und die Prüfungen aus Schritt 4; die Pflichtangaben von `boundsDuration` und die Parsebarkeit von `boundsPeriod` werden nur im ersten Element geprüft. In der Intervall-Kombination muss der Einnahmerhythmus aller Elemente übereinstimmen.
* Bei den Schemata **wiederkehrende Intervalle** und **reine Bedarfsmedikation** ist genau ein `Dosage`-Element zulässig; bei mehreren bricht der Algorithmus ab (Grund 2).
* **Dieselbe Dosis** bedeutet in allen Duplikatprüfungen dieselbe Textdarstellung des Wertes und denselben Feldwert der Einheit, zeichengenau vor der Leerraum-Normalisierung: `1` und `1,0` sind verschieden, ebenso `1 Stück` und `1 Tablette` oder `Stück` und `Stück `. Bei Gleichheit bleibt der zuerst gelesene Wert.
* **Vergleichsart:** Bedingungen auf Werte (`period = 1`, Singular bei `1`, Nenner `1 d` oder `24 h`) vergleichen numerisch (`1.0` gilt als `1`); die Gleichheit von Dosen und Einnahmerhythmen vergleicht die Textdarstellung (`2` und `2,0` sind verschieden).

In strukturierten Schemata ist die Reihenfolge der Segmente **deterministisch** und hängt nicht von der Reihenfolge der `Dosage`-Elemente ab (Uhrzeiten aufsteigend, Tagesabschnitte in fester Reihenfolge, Wochentage kanonisch).

## Fehler und Validierung

Die formale Definition zulässiger Felder und Kombinationen liegt in den Invarianten des Medication IG DE (siehe [Constraints](https://ig.fhir.de/igs/medication/dosierung-constraints.html)). Der Algorithmus bricht ausschließlich aus den drei [Gründen](#grundsätze) ab, mit folgenden Meldungen:

* nicht unterstützter `resourceType`: Abbruch mit `ValueError("Unsupported resource type: {resourceType}")`
* falscher JSON-Datentyp eines gelesenen Feldes: Abbruch mit `ValueError("<Feld> muss numerisch sein.")` (`decimal`), `ValueError("<Feld> muss eine ganze Zahl sein.")` (`positiveInt`), `ValueError("<Feld> muss ein String sein.")` (`string`, `code`, `time`, `dateTime`), `ValueError("<Feld> muss eine Liste sein.")`, `ValueError("<Feld> muss ein Objekt sein.")` beziehungsweise `ValueError("asNeededBoolean muss ein boolescher Wert sein.")`. `<Feld>` ist der Pfad relativ zum `Dosage`-Element, etwa `timing.repeat.period`; Listenelemente tragen `[]` (`timing.repeat.when[]`, `doseAndRate[]`, `extension[].valueCodeableConcept`). Unterhalb von `doseAndRate[0]` beginnt der Pfad bei `doseQuantity` beziehungsweise `doseRange` (`doseQuantity.value`, `doseRange.low.comparator`); das Element selbst heißt `Dosage`, die Liste darüber `dosageInstruction` beziehungsweise `dosage`. Die Platzhalter `{code}` und `{zeit}` in den Meldungen unten sind der Code beziehungsweise Wert, wie er in der Ressource steht
* nicht klassifizierbare Merkmalskombination: Abbruch mit `ValueError("Die Dosierung entspricht keinem unterstützten Dosierungsschema.")`. Es wird **kein** Ersatztext zurückgegeben.
* `timeOfDay` und `when` im selben `Dosage`-Element (Verstoß gegen die FHIR-Basisinvariante `tim-10`): Abbruch mit `ValueError("timeOfDay und when dürfen nicht gemeinsam angegeben werden (tim-10).")`
* mehrere `Dosage`-Elemente, sobald eines davon eine reine Bedarfsdosierung (`asNeededBoolean = true` ohne `timing`) ist: Abbruch mit `ValueError("Reine Bedarfsmedikation erlaubt genau ein Dosage-Element.")`
* fehlendes oder leeres `doseAndRate`: Abbruch mit `ValueError("doseAndRate ist für die Textgenerierung erforderlich.")`
* `doseAndRate[0]` ohne `doseQuantity` oder `doseRange`: Abbruch mit `ValueError("Dosisangabe in doseAndRate[0] fehlt.")`
* `doseQuantity` ohne `.value` oder `.unit`: Abbruch mit `ValueError("doseQuantity.value ist für die Textgenerierung erforderlich.")` beziehungsweise `ValueError("doseQuantity.unit ist für die Textgenerierung erforderlich.")`
* nicht numerischer Dosiswert in `doseQuantity.value`, `doseRange.low.value` oder `doseRange.high.value`: Abbruch mit `ValueError("<Feld> muss numerisch sein.")`
* negativer Dosiswert in `doseQuantity.value`, `doseRange.low.value` oder `doseRange.high.value`: Abbruch mit `ValueError("<Feld> darf nicht negativ sein.")`
* `doseRange` ohne erforderliche obere Grenze: Abbruch mit `ValueError("doseRange.high.value ist für die Textgenerierung erforderlich.")`; eine fehlende Einheit führt entsprechend zu `ValueError("doseRange.high.unit ist für die Textgenerierung erforderlich.")`
* vorhandenes `doseRange.low` ohne `.value`: Abbruch mit `ValueError("doseRange.low.value ist für die Textgenerierung erforderlich.")`
* `maxDosePerPeriod` zusammen mit einem `timing`: Abbruch mit `ValueError("Eine Maximalmenge ist nur bei reiner Bedarfsmedikation zulässig, nicht zusammen mit einem strukturierten Rhythmus.")`
* Mindestabstand (`MinimumIntervalBetweenAdministrations`) zusammen mit einem strukturierten Rhythmus: Abbruch mit `ValueError("Ein Mindestabstand ist nur bei reiner Bedarfsmedikation zulässig, nicht zusammen mit einem strukturierten Rhythmus.")`
* mehrere `Dosage`-Elemente mit unterschiedlichem Schema: Abbruch mit `ValueError("Alle Dosage-Elemente müssen demselben Schema folgen; Element 1 ergibt '{schema1}', Element {n} '{schemaN}'.")`. Die Bezeichner sind die Schema-Namen der Referenzimplementierung: `FreeText`, `AsNeeded`, `4-Schema`, `DayOfWeek`, `DayOfWeek and Time/4-Schema`, `TimeOfDay`, `Interval and Time/4-Schema`, `Interval`; trifft keine Regel zu, `Unknown`
* vorhandenes `doseRange.low.unit`, das von `doseRange.high.unit` abweicht: Abbruch mit `ValueError("doseRange.low.unit und doseRange.high.unit müssen übereinstimmen.")`
* vorhandenes `boundsDuration` ohne `.value` oder `.code`: Abbruch mit `ValueError("boundsDuration.value ist für die Textgenerierung erforderlich.")` beziehungsweise `ValueError("boundsDuration.code ist für die Textgenerierung erforderlich.")`; ein nicht numerischer Wert fällt bereits unter die Typprüfung aus Schritt 3 (`timing.repeat.boundsDuration.value muss numerisch sein.`)
* gleichzeitig vorhandenes `boundsPeriod` und `boundsDuration`: Abbruch mit `ValueError("boundsPeriod und boundsDuration dürfen nicht gleichzeitig vorhanden sein.")`
* `boundsPeriod` ohne `start` und `end`: Abbruch mit `ValueError("boundsPeriod muss start und/oder end enthalten.")`
* nicht parsebares oder unvollständiges `boundsPeriod.start` beziehungsweise `.end` sowie eine Uhrzeit ohne Zeitzone: Abbruch mit `ValueError("boundsPeriod.{start|end} muss ein parsebares FHIR-dateTime mit vollständigem Datum im Format JJJJ-MM-TT sein; eine Uhrzeit erfordert eine Zeitzone.")`
* nicht parsebares oder außerhalb des zulässigen Bereichs liegendes `timeOfDay`: Abbruch mit `ValueError("timeOfDay muss im Format HH:MM oder HH:MM:SS[.Bruchteile] angegeben sein.")`
* `asNeededFor` ohne nicht leeres `valueCodeableConcept.text`: Abbruch mit `ValueError("asNeededFor.valueCodeableConcept.text ist für die Textgenerierung erforderlich.")`
* Extension `MinimumIntervalBetweenAdministrations` ohne `valueDuration`: Abbruch mit `ValueError("MinimumIntervalBetweenAdministrations.valueDuration ist für die Textgenerierung erforderlich.")`; für fehlende Unterfelder gilt `ValueError("MinimumIntervalBetweenAdministrations.valueDuration.value ist für die Textgenerierung erforderlich.")` beziehungsweise `ValueError("MinimumIntervalBetweenAdministrations.valueDuration.code ist für die Textgenerierung erforderlich.")`, nicht numerische Werte fallen bereits unter die Typprüfung aus Schritt 3 (`modifierExtension[].valueDuration.value muss numerisch sein.`)
* `maxDosePerPeriod` ohne `numerator.value`, `numerator.unit`, `denominator.value` oder `denominator.code`: Abbruch mit `ValueError("maxDosePerPeriod.<Unterfeld> ist für die Textgenerierung erforderlich.")`, etwa `maxDosePerPeriod.numerator.value ist für die Textgenerierung erforderlich.`
* nicht numerisches `maxDosePerPeriod.numerator.value`: Abbruch mit `ValueError("maxDosePerPeriod.numerator.value muss numerisch sein.")`
* anderer Nenner als `1 d` oder `24 h`: Abbruch mit `ValueError("maxDosePerPeriod.denominator muss 1 d oder 24 h sein.")`
* `when`-Code außerhalb der [Tagesabschnitts-Tabelle](#tagesabschnitt-when-codes): Abbruch mit `ValueError("Nicht unterstützter Tagesabschnitt (when): '{code}'.")`
* `dayOfWeek`-Code außerhalb der [Wochentags-Tabelle](#wochentage-dayofweek): Abbruch mit `ValueError("Nicht unterstützter Wochentag (dayOfWeek): '{code}'.")`
* doppelte Belegung eines Tagesabschnitts mit unterschiedlicher Dosis im reinen 4‑Schema oder in einer Intervall-Kombination: Abbruch mit `ValueError("Doppelte Belegung des Tagesabschnitts '{code}' mit unterschiedlicher Dosis.")`
* doppelte Belegung desselben Wochentags mit unterschiedlicher Dosis im Wochentags-Schema: Abbruch mit `ValueError("Doppelte Belegung des Wochentags '{code}' mit unterschiedlicher Dosis.")`
* doppelte Belegung derselben Kombination aus Wochentag und Tagesabschnitt mit unterschiedlicher Dosis: Abbruch mit `ValueError("Doppelte Belegung der Kombination aus Wochentag '{code}' und Zeit-/Tagesabschnitt '{zeit}' mit unterschiedlicher Dosis.")`
* dieselbe Uhrzeit mit unterschiedlicher Dosis im Uhrzeiten-Schema, in der Wochentags-Kombination oder in einer Intervall-Kombination: Abbruch mit `ValueError("Doppelte Belegung der Uhrzeit '{HH:MM Uhr}' mit unterschiedlicher Dosis.")`
* Uhrzeiten und Tagesabschnitte gemischt in einer Wochentags-Kombination (über Elemente oder Tage hinweg): Abbruch mit `ValueError("Wochentags-Kombinationen mit Uhrzeiten und mit Tagesabschnitten dürfen nicht gemischt werden.")`
* abweichender Einnahmerhythmus (`period`, `periodMax`, `periodUnit`) eines weiteren `Dosage`-Elements in einer Intervall-Kombination: Abbruch mit `ValueError("Alle Dosage-Elemente einer Intervall-Kombination müssen denselben Einnahmerhythmus tragen.")`
* `modifierExtension` mit anderer URL als der des Mindestabstands: Abbruch mit `ValueError("Nicht unterstützte modifierExtension: '{url}'.")`
* vorhandener `comparator` in einer gelesenen `Quantity`: Abbruch mit `ValueError("<Feld>.comparator wird nicht unterstützt.")`, etwa `doseQuantity.comparator wird nicht unterstützt.`
* mehr als ein `Dosage`-Element im Intervall-Schema: Abbruch mit `ValueError("Wiederkehrende Intervalle erlauben genau ein Dosage-Element.")`
* Einnahmeanlass, Mindestabstand oder Maximalmenge ohne `asNeededBoolean = true`: Abbruch mit `ValueError("Ein Einnahmeanlass (asNeededFor) setzt asNeededBoolean = true voraus.")`, `ValueError("Ein Mindestabstand setzt asNeededBoolean = true voraus.")` beziehungsweise `ValueError("Eine Maximalmenge setzt asNeededBoolean = true voraus.")`
* Mindestabstand oder Maximalmenge an einer Freitext-Dosierung: Abbruch mit `ValueError("Ein Mindestabstand ist bei einer Freitext-Dosierung nicht darstellbar.")` beziehungsweise `ValueError("Eine Maximalmenge ist bei einer Freitext-Dosierung nicht darstellbar.")`
* Zeiteinheit außerhalb der [Einheiten-Tabelle](#einheiten-und-pluralisierung) in `periodUnit`, `boundsDuration.code` oder beim Mindestabstand: Abbruch mit `ValueError("Nicht unterstützte Zeiteinheit: '{code}'.")`

## Versionierung

Die Version des verwendeten Algorithmus MUSS über die Extension [GeneratedDosageInstructionsMeta](https://ig.fhir.de/igs/medication/StructureDefinition-GeneratedDosageInstructionsMeta.html) gesetzt werden. So lassen sich Textinhalt und verwendete Algorithmus-Version nachvollziehbar prüfen.

Diese Seite beschreibt die Algorithmus-Version **2.0.0-ballot**. Die Nummer bezeichnet den hier festgelegten Algorithmus, nicht ein einzelnes Programm: Die Beispielimplementierung führt sie in `__version__` und gibt sie beim Erzeugen der Beispiele in `algorithmVersion` weiter. Eine eigene Implementierung trägt dieselbe Nummer ein, sobald sie diesen Algorithmus umsetzt.

Damit bestimmt dieses Dokument die Versionsfolge: **Eine neue Versionsnummer entsteht genau dann, wenn sich diese Spezifikation ändert.** Korrekturen, die ausschließlich die Referenzimplementierung, ihre Tests oder die CI betreffen, ändern das festgelegte Verhalten nicht und lassen die Nummer unberührt. Die Versionshistorie führt [CHANGELOG.md](CHANGELOG.md); dort trennt jeder Eintrag beides voneinander.

Ob eine Änderung die Haupt- oder die Nebenversion erhöht, richtet sich danach, ob sich bereits erzeugte Texte ändern können: Ein geänderter oder entfallener Baustein und jede Verschärfung der Eingabeprüfung erhöhen die Hauptversion, weil bestehende Ausgaben davon abweichen. Ein zusätzliches Schema oder eine gelockerte Prüfung, die vorhandene Ausgaben unberührt lässt, erhöht die Nebenversion.

## Quellen / weiterführende Hinweise

* UK Core Implementation Guide for Medicines (Dose to Text Translation)
* NHS CUI User Interface Design Guidance (2015)
* Australian Commission: National Guidelines for On-Screen Display of Medicines Information (2017)
