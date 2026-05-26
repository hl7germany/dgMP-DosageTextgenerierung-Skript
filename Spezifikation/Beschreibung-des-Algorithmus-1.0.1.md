# Spezifikation: dgMP-Dosierungstext-Generierung

**Version:** 1.0.1
**Sprache der Ausgabe:** Deutsch (`de-DE`)
**Zweck:** Sprach-unabhängige Vorschrift zur Reimplementierung des Skripts `medication-dosage-to-text.py` in beliebigen Programmiersprachen.

Dieses Dokument beschreibt vollständig und implementierungs-unabhängig, wie aus einer FHIR-Medikationsressource (R4) ein menschenlesbarer deutscher Dosierungstext erzeugt wird. Die Vorschrift ist normativ für die Referenzimplementierung; Beispiele sind illustrativ.
Dieses Dokument beschreibt vollständig und implementierungs-unabhängig, wie aus einer FHIR-Medikationsressource (R4) ein menschenlesbarer deutscher Dosierungstext erzeugt wird. Die Vorschrift ist normativ für die Referenzimplementierung; Beispiele sind illustrativ.

---

## 1. Eingabe und Ausgabe

### 1.1 Eingabe

Eine FHIR-R4-Ressource eines der folgenden Typen:

| `resourceType`         | Feld mit Dosierungen     |
|------------------------|--------------------------|
| `MedicationRequest`    | `dosageInstruction[]`    |
| `MedicationDispense`   | `dosageInstruction[]`    |
| `MedicationStatement`  | `dosage[]`               |

Andere `resourceType`-Werte führen zu einem Fehler (`ValueError` / vergleichbare Exception in der Zielsprache) mit der Meldung `Unsupported resource type: <typ>`.

### 1.2 Ausgabe

Ein String mit dem deutschen Dosierungstext. Bei fehlenden Dosierungen wird der leere String `""` zurückgegeben.

### 1.3 Python-Script-Verhalten

Das Python Skript `medication-dosage-to-text.py` implementiert die beschriebene Logik und verhält sich wie folgt:

- Aufruf: `python medication-dosage-to-text.py <medication-resource.json>`
- Bei fehlendem Argument: Ausgabe einer Hilfemeldung auf `stderr` und Exit-Code `1`
- Bei nicht vorhandener Datei: Fehlertext auf `stderr` und Exit-Code `1`
- Bei ungültigem JSON: Fehlertext auf `stderr` und Exit-Code `1`
- Bei `ValueError` aus der Generierung: Fehlertext auf `stderr` und Exit-Code `1`
- Bei sonstigen unerwarteten Fehlern: Fehlertext auf `stderr` und Exit-Code `1`
- Bei Erfolg: Dosierungstext auf `stdout`, Exit-Code `0`

---

## 2. Konstanten und Übersetzungstabellen

Diese Tabellen sind verbindlich. Schlüssel werden case-sensitive verglichen.

### 2.1 Tageszeit-Codes (FHIR `when`) und Reihenfolge

Reihenfolge im 4-Schema: **MORN → NOON → EVE → NIGHT**

| FHIR-Code | Deutsche Übersetzung |
|-----------|----------------------|
| `MORN`    | `morgens`            |
| `NOON`    | `mittags`            |
| `EVE`     | `abends`             |
| `NIGHT`   | `zur Nacht`          |

### 2.2 Wochentag-Codes (FHIR `dayOfWeek`) und Reihenfolge

Reihenfolge: **mon → tue → wed → thu → fri → sat → sun**

| FHIR-Code | Deutsche Übersetzung |
|-----------|----------------------|
| `mon`     | `montags`            |
| `tue`     | `dienstags`          |
| `wed`     | `mittwochs`          |
| `thu`     | `donnerstags`        |
| `fri`     | `freitags`           |
| `sat`     | `samstags`           |
| `sun`     | `sonntags`           |

Unbekannte Tagescodes werden ans Ende sortiert (Sortierindex `99`) und unverändert übernommen.

### 2.3 Zeit-Einheiten (FHIR `periodUnit` / `boundsDuration.code`)

| FHIR-Code | Singular  | Plural    |
|-----------|-----------|-----------|
| `s`       | Sekunde   | Sekunden  |
| `min`     | Minute    | Minuten   |
| `h`       | Stunde    | Stunden   |
| `d`       | Tag       | Tage      |
| `wk`      | Woche     | Wochen    |
| `mo`      | Monat     | Monate    |
| `a`       | Jahr      | Jahre     |

Wahl Singular/Plural: **Singular** genau dann, wenn der Wert **exakt `1`** beträgt; sonst **Plural**.
Unbekannte Codes werden unverändert ausgegeben (Fallback).

---

## 3. Algorithmus auf hoher Ebene

```
1. dosageInstructions ← extrahiere Liste der Dosierungen aus der Ressource (Kap. 1.1)
2. Falls Liste leer → return ""
3. schemaTyp ← bestimme Schema (Kap. 4)
4. Wende den schemaspezifischen Text-Generator an (Kap. 5)
5. Bei unbekanntem Schema → return "Unbekanntes Dosierungsschema: <schemaTyp>"
```

---

## 4. Schema-Erkennung (Priorität & Bedingungen)

Die Schemaermittlung erfolgt **anhand der ersten Dosierung** der Liste (`dosageInstructions[0]`). Der FHIR-Constraint `TimingOnlyOneType` des Profils [TimingDgMP](https://ig.fhir.de/igs/medication/StructureDefinition-TimingDgMP.html) garantiert, dass alle Einträge konsistent zum selben Schema gehören.

Die folgenden Regeln werden **in Reihenfolge** geprüft; die erste zutreffende Regel bestimmt das Schema. Trifft keine Regel zu, lautet das Schema `Unknown` und es wird `"Unbekanntes Dosierungsschema: Unknown"` ausgegeben.

Bezugspunkt aller Bedingungen ist das `timing.repeat`-Objekt der ersten Dosierung. Eine Liste gilt als „vorhanden", wenn sie existiert **und** mindestens ein Element enthält. Ein „tägliches Muster" liegt vor, wenn `period == 1` **und** `periodUnit == "d"`.

| # | Schema                         | Bedingungen |
|---|--------------------------------|-------------|
| 1 | **FreeText**                   | Feld `text` ist gesetzt **und** Feld `timing` fehlt. |
| 2 | **4-Schema**                   | `frequency` gesetzt; tägliches Muster; `when` vorhanden; `timeOfDay` **und** `dayOfWeek` nicht vorhanden. |
| 3 | **DayOfWeek**                  | `dayOfWeek` vorhanden; `frequency`, `period`, `periodUnit` gesetzt; weder `when` noch `timeOfDay` vorhanden. |
| 4 | **DayOfWeek + Time/4-Schema**  | `dayOfWeek` vorhanden; `frequency`, `period`, `periodUnit` gesetzt; **mindestens eines** von `timeOfDay` oder `when` vorhanden. |
| 5 | **TimeOfDay**                  | `frequency` gesetzt; tägliches Muster; `timeOfDay` vorhanden; weder `dayOfWeek` noch `when` vorhanden. |
| 6 | **Interval + Time/4-Schema**   | `frequency`, `period`, `periodUnit` gesetzt; **kein** tägliches Muster; `dayOfWeek` nicht vorhanden; **mindestens eines** von `timeOfDay` oder `when` vorhanden. |
| 7 | **Interval**                   | `frequency`, `period`, `periodUnit` gesetzt; weder `when` noch `timeOfDay` noch `dayOfWeek` vorhanden. |

---

## 5. Schema-spezifische Text-Generierung

Allgemeine Konventionen:

- Trenner zwischen Zeitpunkten/Tagen innerhalb einer Dosierungsanweisung: **Komma + Leerzeichen** (`", "`).
- Trenner zwischen separaten Anweisungen (Tages-/Zeit-Blöcken): **Semikolon + Leerzeichen** (`"; "`).
- Trenner zwischen Zeit und Dosis: ein Gedankenstrich (`" — "`, U+2014 mit umgebenden Leerzeichen).
- Dosis-Präfix bei „individueller Dosis je Zeitpunkt": `je` (z. B. `je 1 Stück`).
- Bei vorhandenem Begrenzungszeitraum (`boundsDuration`) wird er **vorangestellt** mit Doppelpunkt-Trenner: `für N Tage: <Rest>`.

### 5.1 FreeText

**Verarbeitung:**
1. Aus jeder Dosierung den Inhalt des Felds `text` entnehmen, mit `trim()` (führende/abschließende Whitespaces entfernen).
2. Leere Strings ignorieren.
3. Alle verbleibenden Texte mit einem Leerzeichen verbinden (`" ".join(...)`).

**Beispiel:**

| Eingabe (`text`-Felder)       | Ausgabe                  |
|-------------------------------|--------------------------|
| `["Nach Bedarf", "bei Schmerzen"]` | `Nach Bedarf bei Schmerzen` |

### 5.2 4-Schema (Morgens–Mittags–Abends–Nacht)

**Verarbeitung:**
1. Initialisiere Dosis-Map: `{MORN: 0, NOON: 0, EVE: 0, NIGHT: 0}`.
2. **bounds_text** ← extrahiere `boundsDuration` (Kap. 6.4) aus der **ersten** Dosierung, die `boundsDuration` enthält; sonst `""`.
3. **unit_text** ← Einheit der Dosis aus der **ersten** Dosierung, die eine Dosismenge liefert (Kap. 6.1); sonst `""`.
4. Für jede Dosierung in Eingabe-Reihenfolge:
   - Lies `when_codes = repeat.when` (Liste).
   - Extrahiere Dosismenge (Kap. 6.1). Falls vorhanden `(dose_value, dose_unit)`:
     - Für jeden `when_code` aus `when_codes`, der in `{MORN, NOON, EVE, NIGHT}` enthalten ist: **überschreibe** `dose_map[when_code] = dose_value` (kein Aufsummieren; letzte Zuweisung gewinnt bei Doppelnennung).
5. Erzeuge das Pattern: Werte für `MORN, NOON, EVE, NIGHT` in dieser Reihenfolge, je mit `formatDecimal` (Kap. 6.5) formatieren, verbunden mit `-` → z. B. `"1-0-2-0"`.
6. Wenn `unit_text` nicht leer: `pattern = pattern + " " + unit_text`.
7. Wenn `bounds_text` nicht leer: `return bounds_text + ": " + pattern`; sonst `return pattern`.

**Beispiele:**

| `when` / `dose` | Ausgabe |
|---|---|
| `MORN`=1, `EVE`=2, Einheit `Stück` | `1-0-2-0 Stück` |
| Wie oben + `boundsDuration={value:7,code:"d"}` | `für 7 Tage: 1-0-2-0 Stück` |

### 5.3 TimeOfDay

**Verarbeitung:**
1. **bounds_text** ← `boundsDuration` aus der **ersten** Dosierung, die `boundsDuration` enthält; sonst `""`.
2. Initialisiere `time_dose_parts = []`.
3. Für jede Dosierung in Eingabe-Reihenfolge:
   - `time_list = repeat.timeOfDay` (Liste von "HH:MM" oder "HH:MM:SS").
   - Wenn `time_list` leer → Dosierung überspringen.
   - Sortiere `time_list` **lexikografisch**.
   - Formatiere jede Zeit mit `formatTimeGerman` (Kap. 6.3) → `formatted_times`.
   - Erzeuge `dose_text` mit `extractDoseTextWithPrefix` (Kap. 6.2). Wenn leer → Dosierung überspringen.
   - `times_combined = formatted_times.join(", ")`.
   - Hänge `times_combined + " — " + dose_text` an `time_dose_parts` an.
4. Wenn `time_dose_parts` leer → `return ""`.
5. `combined = time_dose_parts.join("; ")`.
6. Wenn `bounds_text` nicht leer: `return bounds_text + " täglich: " + combined`; sonst `return "täglich: " + combined`.

**Beispiel:** `timeOfDay=["08:00","20:00"]`, Dosis `1 Stück` → `täglich: 08:00 Uhr, 20:00 Uhr — je 1 Stück`

### 5.4 DayOfWeek

**Verarbeitung:**
1. **bounds_text** ← `boundsDuration` aus der **ersten** Dosierung, die `boundsDuration` enthält; sonst `""`.
2. **unit_text** ← Einheit der Dosis aus der **ersten** Dosierung, die eine Dosismenge liefert; sonst `""`.
3. Map `day_to_dose: {dayCode → dose_value}`, initial leer.
4. Für jede Dosierung in Eingabe-Reihenfolge:
   - `day_codes = repeat.dayOfWeek`.
   - Extrahiere Dosis. Falls vorhanden:
     - Für jeden `day_code` aus `day_codes`: `day_to_dose[day_code] = dose_value` (überschreibend).
5. Wenn `day_to_dose` leer → `return ""`.
6. Sortiere die Schlüssel nach DAY_ORDER (Kap. 2.2); unbekannte Tage erhalten Sortierindex `99`.
7. Für jeden Tag in sortierter Reihenfolge:
   - `day_name = DAY_TRANSLATIONS[day_code]` (oder unverändert bei Unbekannt).
   - `formatted_dose = formatDecimal(dose_value)`.
   - `dose_text = "je " + formatted_dose` + (falls `unit_text` nicht leer) `" " + unit_text`.
   - Anhängen: `day_name + " — " + dose_text` an `day_text_parts`.
8. `combined_days = day_text_parts.join("; ")`.
9. Wenn `bounds_text` nicht leer: `return bounds_text + ": " + combined_days`; sonst `return combined_days`.

**Beispiel:** `mon=1`, `wed=2`, Einheit `Stück` → `montags — je 1 Stück; mittwochs — je 2 Stück`

### 5.5 Interval

Es wird nur die **erste** Dosierung (`dosageInstructions[0]`) verwendet.

**Verarbeitung:**
1. `frequency_text = generateFrequencyDescription(dosage)` (Kap. 6.6).
2. `dose_text = extractDoseTextWithPrefix(dosage)` (Kap. 6.2).
3. `bounds_text = extractBoundsText(dosage)` (Kap. 6.4).
4. `zeit_praefix = [bounds_text, frequency_text].filter(nichtLeer).join(" ")` (Begrenzungszeitraum gefolgt von Frequenz; bildet die linke Seite des Doppelpunkts).
5. Ergebnis:
   - Wenn `zeit_praefix` und `dose_text` beide nicht leer: `zeit_praefix + ": " + dose_text`.
   - Sonst wenn `zeit_praefix` nicht leer: `zeit_praefix`.
   - Sonst wenn `dose_text` nicht leer: `dose_text`.
   - Sonst: `""`.

**Beispiele:**

| Eingabe | Ausgabe |
|---|---|
| `frequency=3, period=1, periodUnit="d"`, Dosis `1 Stück` | `3 x täglich: je 1 Stück` |
| `frequency=1, period=8, periodUnit="h"`, Dosis `1 Stück` | `alle 8 Stunden: je 1 Stück` |
| `frequency=1, period=1, periodUnit="wk"`, Dosis `2 mg` | `wöchentlich: je 2 mg` |

### 5.6 DayOfWeek + Time/4-Schema (Kombination)

Das kombinierte Schema hat zwei Varianten. Anhand der ersten Dosierung wird entschieden, welche Variante zur Anwendung kommt (`timeOfDay` / `when` gelten als „vorhanden", wenn die jeweilige Liste existiert und nicht leer ist):

- `timeOfDay` vorhanden **und** `when` nicht vorhanden → **Variante A** (DayOfWeek + TimeOfDay, Kap. 5.6.1)
- `when` vorhanden (mit oder ohne `timeOfDay`) → **Variante B** (DayOfWeek + When, Kap. 5.6.2)
- Andernfalls (Fallback) → **Variante B**

#### 5.6.1 Variante A: DayOfWeek + TimeOfDay

1. Gruppiere Dosierungen nach Wochentag in `day_to_dosages: {dayCode → [dosage,...]}`. Ein Eintrag kann in mehreren Tagen vorkommen (Eintrag wird je Tag einmal hinzugefügt).
2. `bounds_text` aus erster Dosierung mit `boundsDuration` ermitteln.
3. Sortiere Tagesschlüssel nach `DAY_ORDER`.
4. Für jeden Tag:
   - Für jede zugeordnete Dosierung in der ursprünglichen Reihenfolge:
     - `time_list = repeat.timeOfDay`, lexikografisch sortieren.
     - Formatiere jede Zeit mit `formatTimeGerman`.
     - `dose_text = extractDoseTextWithPrefix(...)`.
     - Wenn Zeiten **und** Dosis vorhanden: hänge `times.join(", ") + " — " + dose_text` an `time_dose_parts` an.
   - Wenn `time_dose_parts` für diesen Tag nicht leer: hänge `day_name + " " + time_dose_parts.join("; ")` an `day_text_parts` an.
5. `combined = day_text_parts.join("; ")`.
6. Mit oder ohne `bounds_text` formatieren (analog 5.4).

**Beispiel:** `mon, 08:00, 1 Stück` und `wed, 20:00, 2 Stück` → `montags 08:00 Uhr — je 1 Stück; mittwochs 20:00 Uhr — je 2 Stück`

#### 5.6.2 Variante B: DayOfWeek + When (4-Schema pro Tag)

1. **bounds_text** ← `boundsDuration` aus der **ersten** Dosierung, die `boundsDuration` enthält; sonst `""`.
2. **unit_text** ← Einheit der Dosis aus der **ersten** Dosierung, die eine Dosismenge liefert; sonst `""`.
3. Map `day_to_patterns: {dayCode → {MORN:0, NOON:0, EVE:0, NIGHT:0}}`, initial leer (Tage werden bei Bedarf angelegt).
4. Für jede Dosierung in Eingabe-Reihenfolge:
   - `day_codes = repeat.dayOfWeek`, `when_codes = repeat.when`.
   - Dosismenge extrahieren. Falls vorhanden:
     - Für jeden Tag im Eintrag, dann für jeden `when_code` aus `when_codes`, der in `{MORN,NOON,EVE,NIGHT}` enthalten ist: `day_to_patterns[day_code][when_code] = dose_value` (überschreibend).
5. Falls `day_to_patterns` leer → `""`.
6. Tage sortieren (DAY_ORDER). Für jeden Tag:
   - Bilde aus `day_to_patterns[day_code]` einen Pattern-String, indem die Werte der vier Slots **in der Reihenfolge MORN, NOON, EVE, NIGHT** mit `formatDecimal` formatiert und mit `-` verbunden werden (z. B. `1-0-1-0`).
   - `day_text = day_name + " " + pattern` + (falls `unit_text` nicht leer) `" " + unit_text`.
7. Mit `"; "` joinen, evtl. `bounds_text` voranstellen.

**Beispiel:** `mon` MORN=1, EVE=1, `wed` MORN=2, NOON=1, EVE=2; Einheit leer → `montags 1-0-1-0; mittwochs 2-1-2-0`

### 5.7 Interval + Time/4-Schema (Kombination)

1. Erste Dosierung liefert Intervall-Parameter und `bounds_text`.
2. Aus `repeat.period` (Default `1`) und `repeat.periodUnit` (Default `"d"`) wird der **Intervalltext** **fest** wie folgt gebildet (die Originalimplementierung ignoriert `frequency` an dieser Stelle):

   | Bedingung                | Intervalltext                |
   |--------------------------|------------------------------|
   | `periodUnit == "d"` und `period == 1` | `täglich` |
   | `periodUnit == "d"` und `period != 1` | `alle <formatDecimal(period)> Tage` |
   | `periodUnit == "wk"` und `period == 1` | `wöchentlich` |
   | `periodUnit == "wk"` und `period != 1` | `alle <formatDecimal(period)> Wochen` |
   | sonst                    | `alle <formatDecimal(period)> <periodUnit>` (Einheitencode **unverändert**) |

3. Gruppiere alle Dosierungen nach Zeit-Schlüssel `time_to_dosages: {key → [dosage,...]}`:
   - Wenn `repeat.timeOfDay` nicht leer: Für jeden Eintrag aus `timeOfDay` Dosierung dem entsprechenden Schlüssel zuordnen.
   - Sonst wenn `repeat.when` nicht leer: Für jeden `when_code`, der in `{MORN, NOON, EVE, NIGHT}` enthalten ist, Dosierung dem Schlüssel zuordnen. Unbekannte `when`-Codes werden **ignoriert**.
4. Sortier-Reihenfolge der Zeit-Schlüssel:
   - `when`-Codes zuerst (Sortierschlüssel `(0, index_in_WHEN_CODES_ORDER)`).
   - `timeOfDay`-Strings danach (Sortierschlüssel `(1, time_string)`, lexikografisch).
5. Für jeden sortierten Zeit-Schlüssel:
   - Anzeige:
     - Wenn Schlüssel ein `when`-Code: Übersetzung aus WHEN_CODE_TRANSLATIONS.
     - Sonst: `formatTimeGerman(key)`.
   - **Aufsummierung** der Dosen: `total_dose = Σ dose_value` über alle Dosierungen unter diesem Schlüssel. Einheit ist die **erste** gefundene `dose_unit`.
   - `dose_text = "je " + formatDecimal(total_dose)` + (falls Einheit) `" " + unit`.
   - Anhängen `"<display> — <dose_text>"` an `time_dose_parts`.
6. `combined = time_dose_parts.join("; ")`.
7. Wenn `bounds_text` nicht leer: `return bounds_text + " " + interval_text + ": " + combined`; sonst `return interval_text + ": " + combined`.

**Beispiel:** `period=2, periodUnit="d"`, drei Dosierungen je `08:00` und `18:00` mit Einheit `Stück` → `alle 2 Tage: 08:00 Uhr — je 1 Stück; 18:00 Uhr — je 2 Stück`

---

## 6. Hilfsfunktionen (verbindliche Semantik)

### 6.1 `extractDoseQuantity(dosage) → (value, unit) | null`

1. `doseAndRate = dosage.doseAndRate` (Liste; falls fehlt: leer).
2. Wenn leer → `null`.
3. `first = doseAndRate[0]`.
4. `doseQuantity = first.doseQuantity`. Wenn nicht vorhanden → `null`.
5. `value = doseQuantity.value` (Default `0`), `unit = doseQuantity.unit` (Default `""`).
6. Return `(value, unit)`.

### 6.2 `extractDoseTextWithPrefix(dosage) → string`

1. Ermittle die Dosismenge: `doseQuantity = extractDoseQuantity(dosage)`.
2. Wenn keine Dosismenge vorhanden ist, gib `""` zurück.
3. Entpacke die Dosismenge: `(dose_value, unit) = doseQuantity`.
4. Formatiere den Zahlenwert: `formatted_dose = formatDecimal(dose_value)`. (Kap. 6.5).
5. Wenn `unit` nicht leer ist, gib `"je " + formatted_dose + " " + unit` zurück.
6. Sonst gib `"je " + formatted_dose` zurück.

### 6.3 `formatTimeGerman(time_string) → string`

1. Trenne `time_string` an `:` → Teile.
2. `hour = parseInt(parts[0])`, `minute = parts[1] || "00"`.
3. Bei Fehler (Parsing/Bereich): `return time_string` unverändert.
4. `return zeroPad(hour, 2) + ":" + minute + " Uhr"`. (Stunde immer 2-stellig, Minute übernehmen wie gelesen.)

Hinweis: `minute` wird **nicht** numerisch neu formatiert, sondern als String belassen (z. B. `"30"` → `"30"`, `"05"` → `"05"`). Sekunden-Teile, falls vorhanden, werden ignoriert.

### 6.4 `extractBoundsText(dosage) → string`

1. `boundsDuration = dosage.timing.repeat.boundsDuration`. Wenn nicht vorhanden → `""`.
2. `value = boundsDuration.value` (Default `0`), `unit_code = boundsDuration.code` (Default `""`).
3. Wenn `value` `0` ist oder `unit_code` leer ist, gib `""` zurück.
4. `formatted_value = formatDecimal(value)`.
5. `formatted_unit = formatTimeUnitGerman(value, unit_code)` (Kap. 6.7).
6. `return "für " + formatted_value + " " + formatted_unit`.

### 6.5 `formatDecimal(value) → string`

- Wenn `value == floor(value)` (ganze Zahl): Ausgabe als Integer-String (z. B. `1` statt `1.0`).
- Sonst: Standard-String-Repräsentation mit **Punkt durch Komma** ersetzt (deutsches Dezimaltrennzeichen). Beispiel: `1.5` → `"1,5"`.

### 6.6 `generateFrequencyDescription(dosage) → string`

Aus `repeat`:

1. Wenn `frequency`, `period`, `periodUnit` **alle drei** `null/undefined` → `""`.
2. `periodUnit == "d"` **und** `period == 1`:
   - `frequency == 1` → `"täglich"`
   - sonst → `"<frequency> x täglich"` (`frequency` wird **roh** ausgegeben, ohne `formatDecimal`)
3. `periodUnit == "wk"` **und** `period == 1`:
   - `frequency == 1` → `"wöchentlich"`
   - sonst → `"<frequency> x wöchentlich"`
4. Wenn `frequency == 1` (mit anderen Perioden):
   - `"alle " + formatPeriodDescription(period, periodUnit)`
5. Sonst (frequency > 1 mit Intervall):
   - `"<frequency> x alle " + formatPeriodDescription(period, periodUnit)`

`formatPeriodDescription(period, unit)` = `formatDecimal(period) + " " + formatTimeUnitGerman(period, unit)`.

### 6.7 `formatTimeUnitGerman(value, unit_code) → string`

- Wenn `value == 1`: Wert aus TIME_UNITS_SINGULAR.
- Sonst: Wert aus TIME_UNITS_PLURAL.
- Fallback bei unbekanntem Code: gib `unit_code` unverändert zurück.

---

## 7. Sortier- und Reihenfolge-Regeln (Zusammenfassung)

| Kontext                            | Sortierung |
|------------------------------------|------------|
| Wochentage in der Ausgabe          | DAY_ORDER (mon→sun), unbekannte ans Ende (`99`) |
| `when`-Slots im 4-Pattern          | WHEN_CODES_ORDER (MORN→NOON→EVE→NIGHT) |
| Zeit-Schlüssel in Schema 5.7 (gemischt aus `when` und `timeOfDay`) | Zuerst alle `when`-Codes in WHEN_CODES_ORDER, danach alle `timeOfDay`-Werte lexikografisch sortiert |
| `timeOfDay`-Werte (überall sonst)  | Lexikografisch (entspricht chronologisch bei `HH:MM`) |
| Mehrere Anweisungen pro Tag (Variante A) | In Eingabe-Reihenfolge der Dosierungen |
| Dosierungen für TimeOfDay-Schema (5.3) | In Eingabe-Reihenfolge der Dosierungen |
| Dosierungen für Interval+Time-Schema (5.7) | Gruppiert nach Zeit-Schlüssel; pro Gruppe Reihenfolge unerheblich (es wird summiert) |

---

## 8. Trenner-Konventionen (Zusammenfassung)

| Element                                           | Trenner |
|---------------------------------------------------|---------|
| Mehrere Zeitpunkte innerhalb einer Dosierung      | `", "` (Komma + Space) |
| Mehrere (Zeit-Dosis)-Blöcke innerhalb eines Tages | `"; "` (Semikolon + Space) |
| Mehrere Tagesblöcke                                | `"; "` |
| Zeit/Tagespart und Dosis                           | `" — "` (Em-Dash U+2014 mit umgebenden Spaces) |
| `bounds_text` und Rest in Schemata 5.2, 5.4, 5.6  | `": "` |
| `bounds_text` und Folge in Schema 5.3             | `" täglich: "` (Leerzeichen statt Doppelpunkt direkt nach bounds) |
| `bounds_text` und Folge in Schema 5.5             | `" "` (Leerzeichen) zwischen Bounds und Frequenz, dann `": "` vor Dosis |
| `bounds_text` und Folge in Schema 5.7             | `" "` (Leerzeichen) zwischen Bounds und Intervall, dann `": "` |
| Dosis-Werte im 4-Pattern                          | `"-"` (Bindestrich) |

---

## 9. Fehler- und Sonderfälle

1. **Leere Dosierungsliste:** `return ""`.
2. **Nicht unterstützter `resourceType`:** Ausnahme `Unsupported resource type: <typ>`.
3. **`text`-Felder mit Whitespace:** `trim()` vor Verkettung. Leere Strings überspringen.
4. **Doppelte `when`-Codes im 4-Schema:** Letzter Wert gewinnt (überschreibend); kein Aufsummieren.
5. **Unbekannte `when`-Codes:** In Schemata 5.2 / 5.6.2 werden sie ignoriert. In Schema 5.7 werden Dosierungen mit nur unbekannten `when`-Codes nicht aufgenommen.
6. **Unbekannte `dayOfWeek`-Codes:** Werden ans Ende sortiert (Index 99) und unverändert ausgegeben.
7. **Fehlende Dosis bei TimeOfDay-/Combo-Schemata:** Eintrag wird übersprungen.
8. **Fehlerhaftes Zeit-Format in `formatTimeGerman`:** Originalstring wird ausgegeben.
9. **`boundsDuration` ohne `value` oder `code`:** Keine Bounds-Text-Ausgabe.
10. **`formatDecimal(0)`:** `"0"` (Integer-Form).
11. **`frequency` wird in Schema 5.7 ignoriert** (Replikation der Originalimplementierung).
12. **`formatTimeUnitGerman` mit unbekanntem Code:** Code unverändert ausgeben.

---

## 10. Vollständige End-to-End-Beispiele

### 10.1 4-Schema mit Bounds

**Eingabe (`MedicationRequest`):**
```json
{
  "resourceType": "MedicationRequest",
  "dosageInstruction": [
    {
      "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d",
        "when": ["MORN"], "boundsDuration": {"value": 7, "code": "d"}}},
      "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}]
    },
    {
      "timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d",
        "when": ["EVE"]}},
      "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stück"}}]
    }
  ]
}
```
**Ausgabe:** `für 7 Tage: 1-0-2-0 Stück`

### 10.2 TimeOfDay

**Eingabe (`dosageInstruction`):**
```json
[{"timing": {"repeat": {"frequency": 2, "period": 1, "periodUnit": "d",
   "timeOfDay": ["08:00","20:00"]}},
  "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}]}]
```
**Ausgabe:** `täglich: 08:00 Uhr, 20:00 Uhr — je 1 Stück`

### 10.3 DayOfWeek

**Eingabe:**
```json
[{"timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d",
   "dayOfWeek": ["mon"]}},
  "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}]},
 {"timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d",
   "dayOfWeek": ["wed"]}},
  "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stück"}}]}]
```
**Ausgabe:** `montags — je 1 Stück; mittwochs — je 2 Stück`

### 10.4 Interval

**Eingabe:**
```json
[{"timing": {"repeat": {"frequency": 1, "period": 8, "periodUnit": "h"}},
  "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}]}]
```
**Ausgabe:** `alle 8 Stunden: je 1 Stück`

### 10.5 DayOfWeek + TimeOfDay

**Eingabe:**
```json
[{"timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d",
   "dayOfWeek": ["mon"], "timeOfDay": ["08:00"]}},
  "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}]},
 {"timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d",
   "dayOfWeek": ["wed"], "timeOfDay": ["20:00"]}},
  "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stück"}}]}]
```
**Ausgabe:** `montags 08:00 Uhr — je 1 Stück; mittwochs 20:00 Uhr — je 2 Stück`

### 10.6 DayOfWeek + When

**Eingabe:**
```json
[{"timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d",
   "dayOfWeek": ["mon","wed"], "when": ["MORN","EVE"]}},
  "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}]}]
```
**Ausgabe:** `montags 1-0-1-0 Stück; mittwochs 1-0-1-0 Stück`

### 10.7 Interval + Time

**Eingabe:**
```json
[{"timing": {"repeat": {"frequency": 1, "period": 2, "periodUnit": "d",
   "timeOfDay": ["08:00"]}},
  "doseAndRate": [{"doseQuantity": {"value": 1, "unit": "Stück"}}]},
 {"timing": {"repeat": {"frequency": 1, "period": 2, "periodUnit": "d",
   "timeOfDay": ["18:00"]}},
  "doseAndRate": [{"doseQuantity": {"value": 2, "unit": "Stück"}}]}]
```
**Ausgabe:** `alle 2 Tage: 08:00 Uhr — je 1 Stück; 18:00 Uhr — je 2 Stück`

### 10.8 FreeText

**Eingabe:**
```json
[{"text": "Nach Bedarf"}, {"text": "bei Schmerzen"}]
```
**Ausgabe:** `Nach Bedarf bei Schmerzen`

---

## 11. Hinweise zur Portierung

- **Numerik:** Dosis- und Periodenwerte können ganzzahlig oder dezimal sein. `formatDecimal` muss erkennen, ob der Wert äquivalent zu einer ganzen Zahl ist (`value == floor(value)`).
- **Stringkodierung:** Em-Dash (`—`, U+2014) sicherstellen (UTF-8). Bindestrich im 4-Pattern ist ASCII-Hyphen `-`.
- **Stabile Schlüsselreihenfolge:** Iteration über Maps muss in der Zielsprache deterministisch erfolgen (z. B. `LinkedHashMap` in Java, `dict` in Python). Sortierungen sind durch DAY_ORDER / WHEN_CODES_ORDER / lex. Sortierung der Strings festgelegt.
- **Optionalität:** Felder können fehlen. Defaults: leere Listen, leere Strings, `null` für fehlende Objekte; `period`/`frequency` fehlend ⇒ wie spezifiziert behandeln.
- **FHIR-Constraint `TimingOnlyOneType`:** Die Implementierung verlässt sich auf konsistente Eingaben und prüft das Schema nur an der ersten Dosierung. Die Eingabevalidierung gegen FHIR-Profile ist nicht Teil dieser Spezifikation.

---

## 12. Versionshinweise

Diese Spezifikation entspricht **`__version__ = "1.0.1"`** der Referenzimplementierung. Änderungen am Algorithmus sind in `CHANGELOG.md` dokumentiert.
