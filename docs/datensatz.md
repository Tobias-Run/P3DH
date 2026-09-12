# Der Datensatz

Beschreibung von `p3dh_long.parquet` — die aufgelöste, EUR-normalisierte Long-Form
aller verarbeiteten Pillar-3-Offenlegungen. Eine Zeile = **ein gemeldeter Fakt**
(Institut × Stichtag × Template × Zelle).

Diese Datei ist die Datensatz-Beschreibung. `zweig_b_queries.md` ist das
Query-Kochbuch — dort stehen Beispiele, hier steht, was die Spalten bedeuten und
wo die Fallen liegen.

## Bezug

| | |
|---|---|
| Parquet | `https://cdn.jsdelivr.net/gh/Tobias-Run/P3DH@data/state/p3dh_long.parquet` |
| Manifest | `.../state/manifest.json` — gezählte Kennzahlen, Commit, Codebook-Fingerabdruck |
| Größe | ~30 MB |

```python
import duckdb
con = duckdb.connect()
con.execute("CREATE VIEW p AS SELECT * FROM 'p3dh_long.parquet'")
```

> ⚠️ **Der `data`-Branch hat keine Historie.** Er wird bei jedem Pipeline-Lauf
> force-gepusht und trägt genau einen Commit; der vorige Stand ist danach weg. Wer
> einen bestimmten Stand zitieren oder reproduzieren muss, nimmt das
> **Release-Asset**, nicht den Branch. `manifest.json` sagt, welcher Stand vorliegt.

## Abdeckung

Alle Zahlen stammen aus `manifest.json` und werden bei jedem Lauf aus dem Parquet
**gezählt**, nicht gepflegt.

| | |
|---|---|
| Fakten | 2.295.224 |
| Reports | 882 (Institut × Konsolidierungskreis × Stichtag) |
| Institute | 474 |
| Länder | 30 |
| Templates | 192 |
| Stichtage | 2025-06-30 · 2025-09-30 · 2025-10-31 · 2025-12-31 · 2026-03-31 |

**Es ist keine Stichprobe.** Von 489 Instituten im EDAP-Katalog reichen 476
XBRL-CSV ein, und alle 476 sind verarbeitet; die übrigen 13 veröffentlichen
ausschließlich qualitative PDF-Pakete (`*DISDOCS`), die außerhalb des Scopes
liegen. Der Katalog zählt 4.278 Einreichungen, weil 2.539 davon Korrekturfassungen
derselben Meldung sind — es zählt jeweils nur die neueste („latest wins").

## Schema

29 Spalten. `NULL` heißt durchgängig „nicht bekannt", nie „null".

### Wer meldet

| Spalte | Typ | Bedeutung |
|---|---|---|
| `entityID` | VARCHAR | Melder-Identität wie eingereicht, `rs:<LEI>.<CON\|IND>` |
| `lei` | VARCHAR | Legal Entity Identifier |
| `scope` | VARCHAR | Konsolidierungskreis: `CON` (konsolidiert) oder `IND` (Einzelinstitut). **Nicht mischen** — dasselbe Institut kann beides melden |
| `bank_name` | VARCHAR | Name über GLEIF; `NULL`, wenn der LEI dort nicht auflösbar war |
| `country` | VARCHAR | Sitzland des Melders |
| `entity_type` | VARCHAR | Rechtsform-/Einheitstyp aus den EDAP-Metadaten |
| `institution_type` | VARCHAR | Größenklasse aus den EDAP-Metadaten — die Schichtungsvariable für Peer-Gruppen |
| `files_gsii_module` | BOOLEAN | reicht das GSIIDIS-Modul ein (global systemrelevant) |

### Wann und nach welchem Meldewerk

| Spalte | Typ | Bedeutung |
|---|---|---|
| `refPeriod` | VARCHAR | Stichtag der Offenlegung, `YYYY-MM-DD` |
| `framework_version` | VARCHAR | Reporting Framework `4.1` oder `4.2` |

> 🚨 **`framework_version` und `refPeriod` sind hier nicht unabhängig.** RF 4.2
> umfasst **ausschließlich** den Stichtag 2026-03-31, alle übrigen Stichtage sind
> RF 4.1. Jeder Vergleich zwischen den Meldewerk-Versionen ist damit zugleich ein
> Zeitvergleich — die beiden Effekte lassen sich in diesem Bestand **nicht**
> trennen.

### Wo in der Tabelle

| Spalte | Typ | Bedeutung |
|---|---|---|
| `template_id` | VARCHAR | Meldetabelle, z. B. `60.00.A` (OV1) |
| `template_title` | VARCHAR | Klartexttitel aus dem EBA-Layout |
| `cell_row` / `cell_col` | VARCHAR | Zeilen-/Spaltencode, z. B. `0120` / `0010` |
| `row_label` / `col_label` | VARCHAR | aufgelöste Beschriftung aus dem DPM |
| `open_axis_dims` | VARCHAR | Rohdimensionen offener Achsen, `spalte=wert;…` |
| `open_axis_country` | VARCHAR | aus `eba_GA:`-Codes aufgelöstes Land — **nur** wenn ISO 3166-1, sonst `NULL` |
| `datapoint_code` | VARCHAR | DPM-Datenpunkt (`dp…`) |

### Der Wert

| Spalte | Typ | Bedeutung |
|---|---|---|
| `fact_value` | DOUBLE | gemeldeter Wert, typisiert |
| `fact_value_raw` | VARCHAR | gemeldeter Wert als Zeichenkette, unverändert |
| `data_type` | VARCHAR | DPM-Datentyp (monetär, Prozent, Anzahl …) |
| `currency` | VARCHAR | Meldewährung **des Fakts** — kann innerhalb eines Reports wechseln |
| `fx_rate` | DOUBLE | EZB-Kurs zum Stichtag |
| `fact_value_eur` | DOUBLE | `fact_value × fx_rate` für monetäre Fakten, sonst `NULL` |
| `decimals_monetary` | INTEGER | gemeldete Genauigkeit |

### Qualität und Herkunft

| Spalte | Typ | Bedeutung |
|---|---|---|
| `unit_ambiguous` | BOOLEAN | Template auf der Sperrliste, siehe unten |
| `template_reported` | BOOLEAN | hat das Institut dieses Template als gemeldet **deklariert** (`filing-indicators`) |
| `source_file` | VARCHAR | Quell-ZIP, aus dem der Fakt stammt |

## Referenztabellen

Neben dem Parquet liegen im Repo kleine, statische Referenztabellen:

| Datei | Inhalt | Herkunft |
|---|---|---|
| `codebook/dpm_codebook.csv` | Datenpunkt → Template/Zeile/Spalte + Labels | EBA DPM 2.0 |
| `codebook/template_titles.csv` | Template → Klartexttitel | EBA Annotated Table Layout |
| `codebook/framework_bridge.csv` | Zellen über den Meldewerkswechsel 4.1 ↔ 4.2 | beobachtungsbasiert aus dem Bestand |
| `codebook/geo_names.csv` | ISO-2 → Ländername | ISO 3166-1 |
| `codebook/country_gdp.csv` | Land → BIP (laufende US-Dollar) + Jahr | Weltbank, `NY.GDP.MKTP.CD` |
| `codebook/bank_aliases.csv` | LEI → Kurzname des Instituts | gepflegt |
| `processed/lei_relations.csv` | LEI → direkte und oberste Konzernmutter | GLEIF Level-2-Daten |
| `processed/disclosure_lag.csv` | Einreichung → Abstand zum Stichtag + Perzentil in der Klasse | `submission_ts` aus dem Harvest-Manifest |
| `processed/rwa_density.csv` | Institut → RWA-Dichte, Risikomix, Ansatz (SA/IRB) | KM1 `61.00` + OV1 `60.00.A` |
| `processed/coverage_gap.csv` | beaufsichtigte Einheit → meldet sie, ihre Gruppe, oder niemand | EZB-Liste der beaufsichtigten Einheiten |

### `country_gdp.csv` ist **deskriptiv**

Gedacht zur **Normierung**, nicht als Regressor: ein Länderexposure von 5 Mrd EUR
bedeutet in Malta etwas anderes als in Deutschland, und erst am BIP relativiert
werden Exposures über unterschiedlich große Volkswirtschaften vergleichbar.

Als Grundlage für Korrelationen taugt es **nicht**. Der Wert ist je Land
konstant, die effektive Stichprobe damit ~30 statt ~450; und Länder mit hohem BIP
haben strukturell andere Bankensysteme, sodass ein Zusammenhang „hohes BIP ↔
höhere Kapitalquote" vermutlich ein Größenklassen-Effekt wäre.

| | |
|---|---|
| Abgedeckt | 212 von 250 Ländern · **99,68 %** des Exposures |
| Nicht abgedeckt | Offshore-Plätze (Britische Jungferninseln, Jersey, Guernsey) und Taiwan — die Weltbank veröffentlicht dafür kein BIP |
| Jahr | je Land der jüngste verfügbare Wert, in der Zeile mitgeführt |
| Währung | laufende US-Dollar. Wer gegen `fact_value_eur` rechnet, muss umrechnen |

Der Join läuft über den **ISO-Code**, nicht über den Namen: von 216 gemeinsamen
Codes tragen 32 bei der Weltbank einen anderen Namen als bei uns („Korea, Rep."
gegen „Korea, Republic of"). Ein Namensabgleich hätte sie verloren.

### `lei_relations.csv` — wer gehört zu wem

Je Institut eine Zeile mit der direkten und der obersten Konzernmutter. **Wer
über Institute summiert, braucht diese Tabelle**, sonst zählt er Konzernmutter
und Tochter doppelt.

| Spalte | Bedeutung |
|---|---|
| `lei` | das Institut |
| `direct_parent_lei` / `ultimate_parent_lei` | Mutter, sofern GLEIF eine kennt |
| `direct_parent_status` / `ultimate_parent_status` | `parent`, `exception` oder `nichts_gemeldet` |
| `direct_parent_reason` / `ultimate_parent_reason` | bei `exception` der GLEIF-Grund |

Gemessen über alle 508 Institute:

| | | |
|---|---:|---|
| Mutter **selbst im Bestand** | **66** | 13,0 % — hier tritt Doppelzählung real auf |
| oberste Mutter im Bestand | 74 | |
| Mutter irgendwo, aber außerhalb | 121 | unkritisch, die meldet hier nicht |
| keine Mutter im Bestand möglich | 300 | |
| Mutter da, wer, ist unbekannt | 21 | die Dunkelziffer |

#### „Kein Parent" ist nicht „eigenständig"

Der wichtigste Punkt an dieser Tabelle. Antwortet GLEIF auf die Parent-Abfrage
mit 404, heißt das **nicht**, dass keine Mutter existiert — nur, dass keine
hinterlegt ist. Daneben gibt es die *Reporting Exception* mit einem Grund, und
die Gründe sagen Verschiedenes:

| Grund | Zahl | heißt |
|---|---:|---|
| `NO_KNOWN_PERSON` | 164 | wirklich niemand darüber |
| `NON_CONSOLIDATING` | 111 | niemand konsolidiert das Institut |
| `NATURAL_PERSONS` | 25 | natürliche Personen kontrollieren es |
| `NO_LEI` | 12 | es **gibt** eine Mutter, sie hat nur keinen LEI |
| `NON_PUBLIC` | 5 | Beziehung nicht öffentlich — unbekannt |

Dazu 187 Institute mit hinterlegter Mutter und 4, zu denen GLEIF weder das eine
noch das andere sagt (`nichts_gemeldet`).

Daraus folgen **zwei verschiedene Mengen**, die man nicht vermischen darf:

- *eigenständig* sind nur die ersten beiden Gründe.
- *kann niemanden doppelt zählen* umfasst zusätzlich `NATURAL_PERSONS` — diese
  Institute werden zwar kontrolliert, aber von natürlichen Personen. Die stehen
  nie im Bestand (der ist nach LEI verschlüsselt) und melden keine Säule-3-Daten.

`NO_LEI` gehört in **keine** von beiden: der direkte Weg ist versperrt, eine
Ur-Mutter weiter oben kann aber sehr wohl im Bestand stehen.

#### Drei Einschränkungen

**Untere Schranke, kein vollständiges Bild.** GLEIF-Meldung ist teils
freiwillig. Die Tabelle behauptet nur positiv belegte Kanten; für 21 Institute
ist eine Mutter bekannt-unbekannt. Die wahre Verflechtung ist also mindestens
so groß wie hier ausgewiesen, nicht genau so groß.

**Rechtliches Eigentum, nicht der aufsichtliche Konsolidierungskreis.** GLEIF
bildet Eigentumsverhältnisse ab. Der Kreis nach CRR ist etwas anderes und weicht
ab — eine Abweichung zwischen Mutter-CON und Tochter-IND ist deshalb nicht
automatisch ein Meldefehler.

**GLEIF ist ein Heute-Stand, die Meldedaten sind ein Stichtagsstand.** Ein nach
dem Stichtag verkauftes Institut trägt hier bereits die neue Mutter. Beispiel aus
dem Bestand: *Santander Bank Polska* steht unter *Erste Group Bank AG*, weil
Erste die Bank 2025 übernommen hat — die Meldedaten stammen aber teils aus der
Zeit davor. Wer Kanten mit Stichtagen kombiniert, muss das mitdenken.

### `disclosure_lag.csv` — Rechtzeitigkeit, mit drei Vorbehalten

Je (Institut, Stichtag, Modul) der Abstand zwischen Stichtag und **erster**
Einreichung, dazu das Perzentil innerhalb der Proportionalitätsklasse.

**Die erste Einreichung zählt, nicht die letzte.** 66 % aller Kombinationen
(1.141 von 1.739) haben mehr als eine. Die letzte zu messen hieße,
Korrekturverhalten zu messen — und Institute zu bestrafen, die nachbessern.
`lag_days_last` steht daneben, trägt aber die Kennzahl nicht.

**Verglichen wird nur innerhalb der Klasse.** CRR Art. 433a–c geben großen,
anderen sowie kleinen und nicht komplexen Instituten verschiedene Fristen.
Gemessen am belastbaren Stichtag:

| Klasse | n | Median |
|---|---:|---:|
| Large highest EEA | 155 | 58 Tage |
| Large subsidiaries | 62 | 69 Tage |
| Other highest EEA | 1 | — |

11 Tage Klassenunterschied bei einem Median von 58 — ein roher Vergleich über
alle Institute hätte die Proportionalitätsklasse gemessen und als Sorgfalt
gelesen. Unter fünf Instituten je Klasse wird kein Perzentil ausgewiesen.

**Nur ein Stichtag ist belastbar.** P3DH ging am 26.01.2026 live; alles davor
wurde nachgereicht. Die Spalte `belastbar` hält das fest:

| Stichtag | n | Median-Lag | |
|---|---:|---:|---|
| 2025-06-30 | 404 | 246 | nachgereicht |
| 2025-09-30 | 237 | 160 | nachgereicht |
| 2025-10-31 | 5 | 180 | nachgereicht |
| 2025-12-31 | 875 | 131 | nachgereicht |
| **2026-03-31** | **218** | **58** | eingeschwungen |

Und dort melden fast nur große Institute — quartalsweise Offenlegung ist eine
Pflicht nach Art. 433a. **Für rund die Hälfte des Bestands ist Rechtzeitigkeit
am eingeschwungenen Stichtag nicht messbar.** Das ist keine Lücke im Skript,
sondern eine Eigenschaft der Pflicht; wer die Kennzahl für flächendeckend hält,
liest sie falsch.

### `rwa_density.csv` — die Zerlegung, die die EBA-Übung nicht liefert

Je (Institut, Konsolidierungskreis, Stichtag) die RWA-Dichte plus die Zerlegung
nach Risikoarten und Ansatz.

**Der Nenner ist nicht die Bilanzsumme.** Gerechnet wird TREA (`61.00` r0040)
geteilt durch die Gesamtrisikopositionsmessgröße der Verschuldungsquote
(`61.00` r0210, jeweils Spalte `c0010`). Die enthält außerbilanzielle Positionen
und folgt aufsichtlichen Anrechnungsregeln — wer die Zahl gegen Literatur hält,
die TREA/Total Assets rechnet, vergleicht Verschiedenes.

Der Befund, den die EBA-Benchmarking-Übung strukturell nicht liefern kann, weil
sie nur IRB-Institute abdeckt:

| Ansatz | n | Median RWA-Dichte |
|---|---:|---:|
| Standardansatz | 379 | 0,425 |
| gemischt | 316 | 0,339 |
| IRB (rein) | 11 | 0,205 |

Der Ansatz wird aus den OV1-„davon"-Zeilen gelesen (`0020` SA, `0030`/`0060`
IRB), nicht aus den gemeldeten Templates geschlossen. Nur 11 Institute melden
rein IRB — die großen IRB-Nutzer haben fast alle auch SA-Portfolios und stehen
deshalb unter „gemischt".

#### Zwei Gegenproben, die der Datensatz sich selbst gibt

**OV1 gegen KM1.** `60.00.A` r0380 trägt dieselbe Gesamtsumme wie KM1 r0040.
Über 694 Paare: Median-Abweichung **0,0000 %**, 15 über 1 %. Zwei unabhängig
gemeldete Templates, dieselbe Zahl.

**Die OV1-Teile gegen ihre eigene Summenzeile.** 632 von 694 Reports summieren
sich exakt. `r0340` ist dabei eine Nachrichtenzeile und kein Summand — nimmt man
sie hinzu, stimmen nur noch 196. Die Spalte `ov1_teile_stimmt` hält es fest;
Československá obchodná banka meldet etwa Teile, die das Ganze übersteigen.

#### Unplausibel ist nicht dasselbe wie falsch

| | Dichte | |
|---|---:|---|
| Kommuninvest (4 Stichtage) | 0,031–0,059 | **echt** — Kommunalfinanzierer, Risikogewicht 0 % |
| National Bank of Greece | 475.095 | Nenner um 10⁶ zu klein |

Beide sehen nach Ausreißer aus. Ein pauschaler Filter hätte Kommuninvest
genauso gelöscht wie Athen — und damit die interessanteste Beobachtung des
Datensatzes. `skalenverdacht` belegt den Defekt deshalb **am Nenner**: gegen das
Maximum der eigenen Zeitreihe, plus eine Schranke für Dichten über 10, die keine
Portfolioeigenschaft mehr sein können. Institute mit nur einem Stichtag und
unauffälliger Dichte bekommen `unbekannt`, nicht `false`.

Korrigiert wird nichts. Die Werte stehen unverändert; markiert ist markiert.

### `coverage_gap.csv` — die Umkehrung der Frage

Nicht „was steht in den Daten", sondern: **welche beaufsichtigte Einheit taucht
gar nicht auf?** Das ist „Fehlt ≠ Null" auf Populationsebene.

Die rohe Differenz zwischen der EZB-Liste (2.863 Einheiten) und unserem Bestand
(508) sind 2.479 — und die Zahl ist wertlos. Sie misst Proportionalität und
Schreibweisen, keine Lücke:

| Schritt | Rest |
|---|---:|
| rohe Differenz | 2.479 |
| nur signifikante Institute, Gruppenabdeckung über die EZB-Hierarchie | 126 |
| Abgleich über den 18-stelligen LEI-Kern | 19 |
| teilweise meldende Gruppen anerkannt | **12** |

Jeder Schritt entfernt Scheinbefunde, keinen echten.

| Einordnung | SI | LSI |
|---|---:|---:|
| `meldet_selbst` | 185 | 201 |
| `ueber_gruppe` | 593 | — |
| `gruppe_meldet_teilweise` | 7 | — |
| `keine_gruppe_bekannt` | — | 1.865 |
| `nicht_abgedeckt` | **12** | — |

Von den verbleibenden 12 sind 11 erklärbar: neun österreichische Volksbanken
hängen an Volksbank Wien, die bei uns unter einem nationalen Code statt einem
LEI steht, und zwei griechische an Piraeus, das bei uns als *Piraeus Financial
Holdings* meldet.

**Drei Fallen, die gemessen zugeschlagen haben.** Die Proportionalität nach CRR
Art. 433b/c (1.093 deutsche und 363 österreichische Kleininstitute legen gar
nicht einzeln quartalsweise offen). Die Konzernstruktur (593 Töchter, deren Kopf
meldet — ohne die Hierarchie zählte jede als fehlend). Und die Schreibweise des
Kennzeichens: drei Einträge unseres Bestands sind keine LEIs, sondern
Länderpräfix plus abgeschnittener LEI —

```
EZB             9695005MSX1OYEMGDF46   BPCE S.A.
unser Bestand   FR9695005MSX1OYEMGDF   Groupe BPCE
```

— und diese drei Zeilen allein erklärten 104 der 126.

**Die EZB-Hierarchie ist flach.** Kopf, darunter alle Einheiten, ohne
Zwischenstufen. Bei Novo Banco ist der Kopf ein Private-Equity-Halter, der nicht
meldet, während die Bank in der Mitte sehr wohl meldet — `gruppe_meldet_teilweise`
sagt genau das und nicht mehr.

**Die Grundgesamtheiten decken sich nicht.** Die SSM-Liste umfasst den Euroraum,
unser Bestand 31 Länder. Die 122 Institute, die nur bei uns stehen, sind
Dänemark (28), Polen (22), Schweden (19), Norwegen (13) und weitere — kein
Fehler der EZB-Liste, sondern außerhalb ihres Geltungsbereichs. Eine EU-weite
Vollständigkeit wird nirgends behauptet.

**Ein fehlendes Institut ist kein Vorwurf.** Die Spalte heißt `einordnung` und
nicht `verstoss`.

## Bekannte Einschränkungen

Ein Datensatz ohne dokumentierte Fallen wird falsch verwendet. Die folgenden sind
gemessen, nicht vermutet.

### 1. `eba_GA:x1` ist die Summenzeile, kein Land

Wer die Zeilen mit `open_axis_country IS NULL` mitsummiert, **zählt das
Gesamtexposure doppelt**. Empirisch: bei 89 von 96 Instituten gilt exakt
`x1 = Summe(benannte Länder) + x28` (Median-Verhältnis 1,000).

```sql
-- richtig
WHERE open_axis_country IS NOT NULL
```

`eba_GA:x28` ist dagegen ein echter Residual-Bucket („übrige Länder"), dessen
Belegung je Melder stark schwankt — bei manchen Instituten liegt dort fast das
gesamte Exposure. Beide Codes stehen nicht in ISO 3166-1 und bleiben in
`open_axis_country` bewusst `NULL`.

Diese Falle hat in unserer *eigenen* Beispielabfrage zugeschlagen.

### 2. `unit_ambiguous`: zwei Templates mit uneinheitlicher Einheit

`41.00` und `45.00.A` werden von verschiedenen Instituten in unterschiedlichen
Einheiten gemeldet, ohne dass die Meldung sagt, welche gemeint ist. Wir
korrigieren das **nicht** — eine Skalierung zu raten hieße, eine Zahl zu erfinden.
Stattdessen sind die Zeilen markiert. Für institutsübergreifende Aggregate
ausschließen oder gesondert behandeln.

### 3. „Fehlt" ist nicht „Null"

Institute dürfen nach CRR Art. 432 rechtmäßig auslassen. `template_reported` sagt,
ob das Institut ein Template als gemeldet **deklariert** hat. Eine fehlende Zeile
kann dreierlei heißen: bewusst nicht offengelegt, nicht anwendbar, oder eine Lücke
in *unserer* Verarbeitung. Ein Aggregat, das fehlende Werte als 0 behandelt,
verwandelt Schweigen in einen Befund.

### 4. 35 Fakten ohne Zeilenkoordinate

0,0015 % des Bestands tragen keinerlei Achsenwert. Dort bleibt `cell_row` leer,
statt eine Zeile zu erfinden. `WHERE cell_row <> ''` filtert sie.

Historisch waren es 409.057 (18 %) — Ursache war ein Parser-Defekt bei offenen
Zeilenachsen, behoben in `#56`/`#3`. Unbekannte dp-Codes gibt es heute **null**.

### 5. Zwölf mehrdeutige Datenpunkt-Platzierungen

Zwölf `(datapoint_code, template)`-Paare tragen im Codebook mehr als eine
Koordinate: dort zeigt eine DPM-VariableVersion auf zwei Zellen **derselben**
Tabelle (OV1 A-SA gegen A-IMA), und die Tabelle trägt keine Dimension, die sie
unterscheidet. Betrifft 948 Fakten (0,04 %); fünf der zwölf liegen in Templates,
die der Korpus nie meldet. Details: `#54`.

### 6. 123 Zellen ohne belastbare Brücke über den Meldewerkswechsel

Die Brücke RF 4.1 ↔ 4.2 ist beobachtungsbasiert: 5.277 Zellen, davon 5.091 stabil,
63 auf neue dp-Codes umgebunden, **123 mehrdeutig**. Die 123 liegen sämtlich in
LIQ2 (`74.00.a`–`f`). Für diese Zellen lässt sich eine Zeitreihe über den Bruch
hinweg nicht belegen; der Viewer markiert sie und behauptet nichts. Details: `#70`.

Zellen, die nur in *einer* Version vorkommen, stehen bewusst **nicht** in der
Brücke: Abwesenheit ist bei Offenlegungsdaten kein Beleg für eine
Taxonomie-Änderung.

### 7. Vergleichbarkeit über Institute hinweg

Rechnungslegung, Konsolidierungskreis (`scope`), nationale Optionen und
Meldewährung unterscheiden sich. Zwei Fälle verdienen besondere Vorsicht:

- **Freitext-Zeilen.** Bei CC2 (`66.02`) und LI2/LI3 (`64.01`, `64.02`) ist die
  offene Zeilenachse der **Bilanzposten des Instituts** — Freitext in
  Landessprache, allein in `64.02` 5.324 verschiedene Zeilen. Innerhalb eines
  Reports auswertbar, ohne Zuordnung **nicht** für Peer-Vergleiche.
- **Gemischte Währungen.** Ein Report kann Templates in verschiedenen Währungen
  enthalten. `currency` gilt je Fakt — nie je Report annehmen.

### 8. Auffällige Werte sind markiert, nicht korrigiert

Der Bestand enthält Meldungen, die offensichtlich falsch skaliert sind (fixe
Vorstandsvergütung im Billionenbereich, Prozentwerte als Bruchteile). Wir ändern
sie nicht — sie stehen so in der offiziellen Offenlegung. `quality_profile.csv`
und `plausibility_findings.csv` sagen, welche und warum.

## Reproduktion

```bash
bash scripts/fetch_state.sh          # Bestand vom data-Branch
python3 scripts/build_zweig_b.py     # Parquet neu bauen
python3 scripts/build_dataset_manifest.py
```

Die Pipeline ist byte-deterministisch: gleiche Eingaben ergeben gleiche Ausgaben
(`docs/reproduzierbarkeit.md`). Einzige Ausnahme ist `generated_at_utc` im
Manifest — bewusst, weil der `data`-Branch keine Historie führt.

## Zitation und Rechte

**Die Offenlegungsdaten stammen von der Europäischen Bankenaufsichtsbehörde und
sind gesondert zu zitieren.** Die MIT-Lizenz dieses Repositories deckt den Code,
**nicht** den Datensatz.

| | |
|---|---|
| Primärquelle | EBA Pillar 3 Data Hub, © European Banking Authority |
| Institutsnamen | GLEIF, CC0 |
| Aufbereitung | diese Pipeline — `CITATION.cff` |

Vollständige Abgrenzung: `DISCLAIMER.md`. Das Projekt ist weder mit der EBA noch
mit GLEIF verbunden. Zahlen vor jeder Verwendung gegen die offizielle Quelle
prüfen.
