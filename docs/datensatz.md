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
liegen. Der Katalog zählt 4.278 Einreichungen, weil **472** davon
Korrekturfassungen derselben Meldung sind — es zählt jeweils nur die neueste
(„latest wins"). Übrig bleiben 3.806 eigenständige Meldungen, davon 2.825
XBRL-Pakete und 981 reine PDF-Pakete.

> ⚠️ Diese Zahl hängt daran, was „dieselbe Meldung" heißt, und die naheliegende
> Antwort ist falsch: die Spalte `module` im Katalog trägt nur den numerischen
> PILLAR3-Code, nicht den Modultyp. Wer danach gruppiert, zählt CODIS, ESGDIS und
> FINDIS desselben Instituts als Korrekturen voneinander und kommt auf 2.539.
> Die Regel steht seit #88 an einer Stelle: `scripts/submissions.py`.

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
| `processed/eba_reconciliation.csv` | unsere Länderaggregate gegen die EBA-eigenen | EBA Risk Dashboard, Datenanhang |
| `processed/scale_flags.csv` | Report bzw. Template → Skalenurteil, Signale, geschätzter Faktor | abgeleitet aus dem Bestand |
| `processed/omission_profile.csv` | Report → was wird weggelassen, gemessen an den direkten Peers | `filing_indicators.csv` |
| `processed/omission_templates.csv` | Klasse × Stichtag × Template → Offenlegungsquote der Peer-Gruppe | ebenda |
| `processed/omission_persistence.csv` | Institut × Template → ist die Auslassung dauerhaft oder wechselt sie? | ebenda + `disclosure_frequency.csv` |
| `processed/irrbb_sensitivity.csv` | Report × Zinsschock → ΔEVE, ΔNII, Supervisory Outlier Test | IRRBB1 `68.00`, KM1 `61.00` |
| `processed/peer_similarity.csv` | Report → die fünf ähnlichsten Institute nach Länderprofil | CCyB1 `67.01.A` |
| `processed/country_effect.csv` | Bankattribut × Länderkennzahl → Varianzzerlegung und Korrelation | `footprint.csv`, `country_gdp.csv` |
| `processed/country_exposure.csv` | Report × Land → Exposure, Anteil am Report, **Exposure je Host-BIP** | CCyB1 `67.01.A` + `country_gdp.csv` |
| `processed/country_concentration.csv` | Land → aggregiertes Exposure der Melder, am BIP relativiert | ebenda, entdoppelt über `lei_relations.csv` |
| `processed/peer_clusters.csv` | Gruppe → Institute mit gemeinsamem Länder-Fussabdruck, Kohäsion, Trägerschaft | CCyB1 `67.01.A` + `lei_relations.csv` |
| `processed/equity_link.csv` | Institut → Aktien-ISIN, Primärnotierung, Tickersymbol | Wikidata (`P946`, `P414`/`P249`) |
| `processed/event_study_feasibility.csv` | Ereignisfenster → verwertbare Ereignisse, Urteil zur Machbarkeit | `manifest_full.csv` + `wikidata_entities.csv` |
| `processed/catalogue_coverage.csv` | Katalog-Report → geladen, oder warum nicht | `manifest_full.csv` gegen Parquet + Coverage-Matrix |
| `processed/risk_taker_share.csv` | Report → Anteil der „identified staff" an der Belegschaft, grössenbereinigt | REM1 `30.01` + `wikidata_entities.csv` |
| `codebook/wikidata_entities.csv` | LEI → Wikidata-Item, Belegschaft mit Stichtag, Gründung, Rechtsform, Börsennotierung | Wikidata (`P1278`) |
| `processed/irb_risk_weights.csv` | Institut × Forderungsklasse × PD-Band → Risikogewicht, PD, LGD | CR6 `26.00.A` |
| `processed/footprint.csv` | Institut → Länderstreuung des Exposures, Domestizitätsquote, HHI | CCyB1 `67.01.A` |
| `processed/disclosure_frequency.csv` | Klasse × Template → gemessene Offenlegungsfrequenz | `filing_indicators.csv` |
| `processed/group_graph_check.csv` | GLEIF-Konzernmutter gegen EZB-Gruppenkopf | beide Graphen |

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

**Benutzt wird sie in `country_exposure.csv`** (#14). Bis dahin lag die Tabelle
im Repo, ohne dass irgendetwas sie las — der Zweck aus dem Titel des Issues,
„Kontextspalte", war damit nicht eingelöst.

Dort steht je Report und Land der Quotient `exposure_je_bip`. Drei Dinge sind
beim Lesen nötig:

- **Die Umrechnung steht in der Zeile.** Das BIP kommt in Dollar, das Exposure
  in Euro; ohne Umrechnung wäre der Quotient rund 17 % daneben. Welcher Kurs
  benutzt wurde, sagt `bip_fx_refdate` — für 2025-06-30 liegt keiner vor, dort
  wird der nächstgelegene genommen.
- **Fehlt ≠ Null.** Für Jersey, Guernsey, die Britischen Jungferninseln und
  Taiwan bleiben `bip_eur` und `exposure_je_bip` **leer**. Eine Null behauptete
  eine Wirtschaft der Größe null, und der Quotient wäre unendlich.
- **Oben kippt die Kennzahl.** Die Marshallinseln erreichen 5.265 % des BIP,
  Luxemburg 780 %, die Kaimaninseln 640 %. Dahinter steht kein überschuldetes
  Land, sondern ein Register — Schiffsfinanzierung beziehungsweise
  Fondsdomizilierung. Eine Quote weit über 100 % heißt „Finanzplatz", nicht
  „Klumpenrisiko". Für die Fälle, um die es geht (5 Mrd in Malta gegen 5 Mrd in
  Deutschland), trägt sie.

### `country_concentration.csv` — wie viel Exposure trägt Land X? (#19)

Dieselben Daten je Land aggregiert. Die Summe ist **entdoppelt**: der CON-Report
einer Gruppe enthält ihre Töchter bereits, und die IND-Reports derselben Töchter
dazuzuzählen meldete eine Konzentration, die es nicht gibt — bei Österreich
macht das 7,8 % aus. Reports mit Skalenvorbehalt (#83) bleiben ebenfalls
draußen. Sie misst das Exposure **der Melder im Bestand** (222 zum 31.12.2025),
nicht das eines Bankensystems.

Vier Spalten tragen die Vorbehalte, die #19 als Vorbedingung nennt:

| Spalte | wogegen |
|---|---|
| `melder_gesamt` · `breite` | Ohne Nenner ist `melder` nicht lesbar — 55 Melder sind viel oder wenig, je nachdem, ob 60 oder 600 in Frage kamen |
| `melder_unvollstaendig` | Häuser mit über 25 % im Residualbucket `x28`. Deren Geografie ist unvollständig, die Summe also nach **unten** verzerrt — 45 von 250 Ländersummen betroffen |
| `groesster_inlaendisch` | trennt die domestizierte Konzentration von der echten (siehe unten) |

**Der Befund: Breite und Konzentration sind entkoppelt.** Brasilien hat 82
Melder — und trotzdem liegen 80,1 % des Exposures (125,1 Mrd) bei Banco
Santander. Viele Melder heißen nicht gestreut.

Die Spalte `groesster_inlaendisch` ist nötig, damit das deutbar bleibt: Islands
84,9 % liegen bei Íslandsbanki, einer isländischen Bank im eigenen Land — das
ist der Normalfall, kein Befund. Von 101 Ländern mit über 0,5 Mrd Exposure
tragen 85 ihre größte Position bei einem **ausländischen** Institut, und nur
die sind Drittstaatenrisiken im Sinne des Issues:

| Land | Anteil | bei | Melder |
|---|---:|---|---:|
| Algerien | 89,7 % | Natixis | 43 |
| Neuseeland | 84,9 % | Rabobank | 60 |
| Mosambik | 82,1 % | Banco Comercial Português | 22 |
| Brasilien | 80,1 % | Banco Santander | 82 |

Nicht länderzuordenbar bleiben zum 31.12.2025 **736,5 Mrd EUR** im
Residualbucket — 3,4 % der zuordenbaren Masse.

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
| teilweise meldende Gruppen anerkannt | 12 |
| Melder unter abweichender LEI erkannt | **1** |

Jeder Schritt entfernt Scheinbefunde, keinen echten.

| Einordnung | SI | LSI |
|---|---:|---:|
| `meldet_selbst` | 185 | 201 |
| `ueber_gruppe` | 593 | — |
| `gruppe_meldet_teilweise` | 7 | — |
| `namensgleicher_melder` | 11 | — |
| `keine_gruppe_bekannt` | — | 1.865 |
| `nicht_abgedeckt` | **1** | — |

#### Die LEI der Aufsicht ist nicht die LEI der Offenlegung

Rein über die LEI gerechnet fehlten **12** signifikante Institute. Elf davon
melden nachweislich, nur unter einer anderen Kennung als der, die die EZB-Liste
führt: neun österreichische Volksbanken hängen an **Volksbank Wien**, die bei
uns unter einem nationalen Code statt einem LEI steht, und zwei griechische an
**Piraeus**, das als *Piraeus Financial Holdings* meldet.

Sie als fehlend zu zählen wäre eine Unterstellung; sie stillschweigend als
abgedeckt zu zählen eine Behauptung. `namensgleicher_melder` sagt beides nicht
und führt den gefundenen Melder in `namenstreffer` mit, damit der Verdacht
nachprüfbar bleibt — die Zuordnung selbst läuft weiter ausschliesslich über die
LEI.

Der Namensvergleich verlangt **zwei** gemeinsame bedeutungstragende Wörter im
**selben Land**; ein Wort genügt nur, wenn ein Name nach Abzug der Rechtsformen
aus einem einzigen besteht. Beide Schranken sind gemessen nötig: mit einem Wort
träfe *Nederlandse Waterschapsbank* auf *Nederlandse Financierings-Maatschappij*
(zwei verschiedene Banken), und ohne die Mindestwortlänge zerfällt `S.A.` in
„s" und „a" — dann gelten *Piraeus Bank S.A.* und *Alpha Bank S.A.* als
dasselbe Haus.

#### Übrig bleibt ein einziges Institut

**Nederlandse Waterschapsbank N.V.** — weder selbst im Bestand, noch über die
Gruppe, noch namensgleich. Das ist die Zahl, die #42 sucht, und auch sie ist
kein Vorwurf: Art. 433a lässt für nicht börsennotierte Institute jährliche
statt quartalsweiser Offenlegung zu, und eine Offenlegung ausserhalb des Hubs
ist damit nicht ausgeschlossen.

#### Abdeckung je Land — getrennt nach SI und LSI

| Land | SI | LSI |
|---|---:|---:|
| Italien | 212/212 (100 %) | 30/138 (22 %) |
| Frankreich | 207/207 (100 %) | 12/83 (14 %) |
| Österreich | 66/75 (88 %) | 16/315 (5 %) |
| Deutschland | 64/64 (100 %) | 41/1.109 (4 %) |
| Finnland | 55/55 (100 %) | 5/46 (11 %) |
| Spanien | 39/39 (100 %) | 16/72 (22 %) |

Die Trennung ist keine Formalie. **Die LSI-Quote ist niedrig, weil sie niedrig
sein soll:** nach CRR Art. 433a–c legen kleine, nicht börsennotierte Institute
seltener und weniger offen, und Deutschlands 1.109 LSIs sind überwiegend
Sparkassen und Genossenschaftsbanken. Eine gemeinsame Quote läse sich als
Abdeckungslücke und wäre eine Unterstellung.

> ⚠️ Das LSI-Blatt der EZB-Liste hat **weder eine Land- noch eine Namensspalte**
> — es ist nach Ländern gegliedert, Name und Zwischenüberschrift stehen in
> derselben Spalte. Wer nur Spaltenköpfe sucht, bekommt für alle 2.066 LSIs
> leere Felder, und zwar lautlos. Genau deshalb wird das Land wie die
> Gruppennummer als laufende Überschrift mitgeführt.

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

### `eba_reconciliation.csv` — die externe Bestätigung

Bisher validiert das Projekt nur gegen sich selbst (Zeilenzahl-Parität, Guards,
OV1 gegen KM1). Hier wird zum ersten Mal gegen eine **fremde Quelle** geprüft:
die EBA veröffentlicht aggregierte Kennzahlen je Land, wir haben die
Einzelmeldungen, aus denen solche Aggregate entstehen.

Verglichen werden die vier Kapitalkennzahlen, die sich vollständig aus KM1
rechnen lassen — CET1-, Tier-1-, Gesamtkapital- und Verschuldungsquote — über
29 Länder und vier Stichtage.

| Kennzahl | n | Median \|Differenz\| | p90 |
|---|---:|---:|---:|
| SVC_3 CET1 | 102 | 1,02 pp | 4,96 pp |
| SVC_1 Tier 1 | 102 | 0,76 pp | 5,31 pp |
| SVC_2 Gesamtkapital | 102 | 0,75 pp | 4,68 pp |
| SVC_13 Verschuldung | 101 | 0,45 pp | 1,89 pp |

60 % aller 407 Vergleichspunkte liegen innerhalb eines Prozentpunkts.

**Die Abweichung fällt monoton mit der Zahl der Institute je Land:**

| Institute je Land | Median \|Differenz\| | innerhalb 1 pp |
|---|---:|---:|
| 1 | 2,07 pp | 27 % |
| 2–4 | 0,62 pp | 66 % |
| 5–9 | 0,53 pp | 70 % |
| **≥ 10** | **0,23 pp** | **82 %** |

Das ist die Signatur eines **Abdeckungsunterschieds**, nicht eines
systematischen Fehlers: ein Rechenfehler in unserer Kette wäre von der Zahl der
Institute unabhängig, ein Stichprobenunterschied verschwindet mit wachsender
Zahl. Damit ist die Kette vom Parser über die Zellplatzierung bis zur
EUR-Normierung extern bestätigt.

**Drei Dinge, ohne die der Vergleich Unsinn misst.** Gewichtet statt gemittelt
(die EBA weist Summe-durch-Summe aus). Keine Doppelzählung — 90 Institutszeilen
sind ausgeschlossen, weil ihre Mutter selbst meldet. Keine kaputten Nenner —
5 Zeilen mit Skalenverdacht sind ausgeschlossen, denn in einem Summenaggregat
verschwindet ein 10⁶-Fehler nicht, er verzerrt es.

**Die Grundgesamtheiten sind verschieden, und das ist kein Fehler.** Das EBA
Risk Dashboard beruht auf aufsichtlichem Meldewesen über eine definierte
Stichprobe, P3DH auf Offenlegung nach CRR Teil 8. Eine Abweichung ist erwartbar;
deshalb steht `n_institute` in jeder Zeile, und bei `n = 1` misst die Differenz
die Grundgesamtheit, nicht unsere Rechnung.

### `scale_flags.csv` — Meldungen, deren absolute Beträge um einen Faktor danebenliegen

Je (Institut, Konsolidierungskreis, Stichtag) ein Urteil: `skaliert`,
`verdacht` oder `unauffaellig`. 54 von 882 Reports sind als skaliert
eingestuft, 17 als Verdacht; dazu 48 einzelne Templates in sonst sauberen
Reports.

#### Warum das eine eigene Ebene braucht

Die Plausibilitätsprüfung (`check_plausibility.py`) misst den Abstand **über**
dem Median der Zellpopulation. Das ist eine bewusste Entscheidung: die untere
Flanke einer Exposure-Verteilung ist natürlich — sehr viele Institute haben nahe
null Exposure zu einer gegebenen Kategorie, und ein Betrag von 100 EUR in einer
Zelle mit Median 10⁸ ist eine kleine Position, kein Meldefehler.

Ein Skalenfehler macht Werte aber **immer zu klein**. Er landet damit genau
dort, wo nicht hingesehen wird. Für die Deutsche Pfandbriefbank am 2025-06-30
liegen 1.524 der 1.966 prüfbaren Fakten mindestens drei Größenordnungen unter
ihrem Zellmedian — und die Prüfung meldet **null** Befunde, bei 67 von 69
danebenliegenden Templates.

Die Zellprüfung kann diesen Fehler also nicht finden, ohne die Regel aufzugeben,
die sie überhaupt brauchbar macht. Deshalb eine eigene Ebene.

#### Drei Klassen

| | Ebene | Beispiel | |
|---|---|---|---|
| A | Report | Deutsche Pfandbriefbank, Bank of Valletta | fast alle Templates |
| B | Template | ING Bank Śląski, `67.01.A` | der übrige Report ist sauber |
| C | Einzelzelle | National Bank of Greece | Sache der Zellprüfung |

Klasse B fällt ohne die Spalte `ebene` durch beide Netze: reportweit ist ING
Bank Śląski unauffällig (Versatz −0,15), und in den betroffenen Zellen schweigt
die Zellprüfung.

#### Vier Signale, und warum kein einzelnes reicht

Die TREA-Verteilung ist ein **Tal, keine leere Lücke**: 50 Reports unter 10⁶ EUR
(fachlich unmöglich), 25 dazwischen, 723 über 10⁸. In der Grauzone kann ein sehr
kleines Institut echt liegen — dort verlangt das Urteil zwei unabhängige
Signale.

| Signal | was es misst | n |
|---|---|---:|
| `untergrenze` | TREA unter jeder fachlich möglichen Grenze | 50 |
| `versatz` | Median des Abstands zum Populationsmedian derselben Zelle | 72 |
| `zeitreihe` | Sprung ≥ 100 gegen den **größten** eigenen Stichtag | 5 |
| `decimals` | erklärte Meldegenauigkeit, die fast kein Wert erreicht | 10 |

Zwei Signale entscheiden für sich allein: die Untergrenze, und ein Versatz unter
−4 Größenordnungen. Das zweite ist nötig, weil **84 der 882 Reports gar keinen
TREA melden** — dort greift die Untergrenze nicht, es bliebe bei einem Signal,
und die Prüfung erklärte sich für zufrieden, *weil* die Kennzahl fehlt, an der
sie hängt. Zwei Reports hängen daran: DLR Kredit A/S (598 Werte, Median 23 EUR,
Maximum 29.712 EUR — bei einer dänischen Realkreditbank) und Banco Santander
Totta zum 2025-06-30.

Ein widerlegtes Signal wird als widerlegt geführt, nicht gelöscht. Axa banque
meldet nur KM1 in Millionen und die übrigen 317 monetären Werte in Einheiten;
die Reportzeile trägt deshalb `untergrenze_widerlegt` und `unauffaellig`,
während der Befund selbst als Templatezeile auf `61.00` steht.

`zeitreihe` feuert selten, und das hat einen Grund: wer wie Zagrebačka banka an
allen vier Stichtagen skaliert meldet, hat keinen sauberen eigenen Bezug mehr.
Solche Fälle fängt die Untergrenze.

Der **Negativfall** ist so wichtig wie die Treffer: Kommuninvest — 3,4 Mrd SEK
TREA, 355 % CET1, nachprüfbar korrekt für einen Kommunalfinanzierer mit fast nur
nullgewichteten Aktiva — ist an allen Stichtagen `unauffaellig`. Eine Regel, die
kleine Häuser systematisch markiert, wäre wertlos.

#### Was mit einem markierten Report NICHT passiert

**Er wird nicht korrigiert.** `decimals_monetary` sagt formal etwas anderes als
„in Millionen gemeldet"; wer das geraderückt, entscheidet eine Auslegungsfrage
still und erfindet Daten, falls die Vermutung falsch ist.

**Er wird nicht verworfen.** Ein Verhältnis überlebt einen gleichmäßigen
Skalenfehler: die RWA-Dichte der Deutschen Pfandbriefbank ist mit 0,43
**richtig**, obwohl Zähler und Nenner beide zu klein sind. Das Urteil betrifft
die absoluten Beträge, nicht den Report.

**Und es gilt nicht durchgängig.** Bei der pbb sind 67 von 69 Templates
skaliert, `64.03.B` und `68.00` aber nicht.

#### Wo die Marke hinwirkt

Zwei Stellen, und beide sind Teil des Befunds:

1. **Aus dem Nenner der Zellstatistik.** Ein um 10⁶ danebenliegender Report
   weitet die Zellen, in denen er steht, über die Unbrauchbarkeitsschwelle —
   der Schaden trifft die *anderen* Institute derselben Zellen, deren Ausreißer
   mitgedeckelt werden. Der Ausschluss senkt die unbrauchbaren Zellen von 592
   auf 246 und die Median-Rumpfbreite von 3,85 auf 3,15 Größenordnungen.
   Ausgeschlossen wird nur aus dem Nenner; geprüft werden die Reports weiter.
2. **In den Viewer.** 50 der 100 markierten Reports haben null
   Plausibilitätsbefunde — ohne die Marke wären sie dort von einem sauberen
   Report nicht zu unterscheiden.

`faktor_geschaetzt` ist ein Hinweis, keine Feststellung, und wird nirgends zum
Rechnen benutzt: gemessen 10³ (62×) und 10⁶ (56×) — plus ein 10⁹ bei Société
générale `27.02.B`, wo der Sprung real ist, die Zahl als Meldeskala aber
unplausibel.

### `omission_profile.csv` — was Institute nach Art. 432 weglassen

Art. 432 CRR erlaubt, nicht wesentliche sowie proprietäre oder vertrauliche
Angaben wegzulassen. Zu diesem Ermessensspielraum gibt es Leitlinien, aber keine
auffindbare empirische Arbeit — weil man je Institut wissen müsste, was es
*weglässt*, und das aus einem PDF nicht rekonstruierbar ist.

`processed/filing_indicators.csv` ist genau diese Aussage, vom Melder selbst,
Template für Template: 64.898 Zeilen, 23.525 „offengelegt", 41.373 „nicht
offengelegt".

#### Die naheliegende Kennzahl misst den Meldekalender

| Stichtag | offengelegt |
|---|---:|
| 2025-06-30 | 35,4 % |
| 2025-09-30 | 11,9 % |
| 2025-12-31 | 45,1 % |
| 2026-03-31 | 12,9 % |

Das ist die Frequenz nach Art. 433a–c, kein Verhalten. `19.03` (OR3) steht an
drei Stichtagen bei rund 2 % und am 2025-12-31 bei 53,9 % — jährlich. `74.00`
(LIQ2) bei 62,8 / 2,5 / 62,9 / 2,8 — halbjährlich. `61.00` (KM1) bei rund 95 %
an jedem Stichtag — vierteljährlich. Und ungeschichtet misst dieselbe Zahl
zusätzlich die Institutsgröße: ein kleines Haus lässt mehr weg, weil es weniger
hat.

#### Gemessen wird gegen die Population derselben Koordinate

Dieselbe Konstruktion wie bei der Zellprüfung (#17). Die Koordinate ist
(Größenklasse, Stichtag, Template) — sie absorbiert Kalender **und** Größe. Je
Koordinate wird die Offenlegungsquote der Peer-Gruppe gemessen (n ≥ 20) und in
drei Bänder gelegt:

| Band | Quote der Peers | n Koordinaten |
|---|---|---:|
| `erwartbar` | ≥ 80 % | 124 |
| `uneinheitlich` | 20–80 % | 254 |
| `untypisch` | < 20 % | 367 |

Gezählt wird nur im Band `erwartbar`: **ein Institut lässt etwas weg, das seine
direkten Peers am selben Stichtag offenlegen.** Der breite Mittelbau bekommt ein
eigenes Band, statt an einer 50-%-Schwelle in eines der anderen gezwungen zu
werden — eine Erwartung, die die Daten nicht hergeben, wäre erfunden.

Das Ergebnis ist konservativ: von 850 prüfbaren Reports weichen **596 gar nicht
ab**, der Median liegt bei 0, p90 bei 0,167.

#### Drei Vorbehalte, und alle drei stehen in Spalten

**1. Die Hälfte der Abweichungen ist eine gemeinsame Regel, kein Ermessen.**
Sechs Institute in vier Ländern lassen *exakt* dieselben elf Templates weg
(`02.00|24.00|25.00|60.00|66.01|70.00|71.00|72.00|73.00|74.00|90.01`) —
darunter J.P. Morgan SE, BofA Securities Europe, Citigroup Global Markets Europe
und BNY Mellon. Unabhängige Einzelentscheidungen sehen anders aus; das ist eine
feinere Proportionalitätsstufe, die `institution_type` nicht abbildet. 48 % der
abweichenden Reports teilen ihre Auslassungsmenge mit mindestens zwei anderen.
`n_signatur_geteilt` hält das je Zeile fest.

**2. Acht Deklarationen widersprechen ihrer eigenen Lieferung.** PPF Financial
Holdings deklariert am 2025-12-31 *jedes* Template als nicht offengelegt und
liefert Daten für 46; OTP Luxembourg für 25. Das ist ein Deklarationsfehler, und
mit einer Quote von 1,0 stünden sie an der Spitze jeder Rangliste.
`deklaration = unbrauchbar` nimmt sie aus allen Kennzahlen.

**3. Nichtanwendbarkeit ist nicht sauber abgetrennt.** Der Filing-Indicator sagt
„nicht offengelegt", nicht warum. Die Peer-Gruppe drückt den Anteil, den
Geschäftsmodelle erklären, sie eliminiert ihn nicht. `n_gegen_erwartung` ist
deshalb eine **Obergrenze** für Ermessensausübung, keine Messung davon — die
Spalte heißt nicht `n_ermessen`.

#### Die Gegenprobe gegen die Lieferung, in zwei getrennten Spalten

| | Zeilen | zuschreibbar? |
|---|---:|---|
| `n_false_mit_daten` — „nicht offengelegt", aber Fakten vorhanden | 175 | **ja** — liegen Fakten vor, wurden sie gemeldet |
| `n_true_ohne_daten` — „offengelegt", aber kein Fakt im Bestand | 2.001 | **nein** — kann auch eine Lücke unserer Platzierung sein |

In einer Spalte addiert wären 175 belastbare Zeilen unter 2.001 unzuschreibbaren
verschwunden.

#### Art. 432(2) kennt eine Ausnahme von der Ausnahme

Die Angaben nach Art. 437 (Eigenmittel: CC1 `66.01`, CC2 `66.02`) und Art. 450
(Vergütung: REM1–REM5) sind von der Proprietäts-Ausnahme **ausgenommen** — eine
Auslassung dort kann sich nicht auf Vertraulichkeit stützen. Gemessen: 95 solche
Auslassungen, `n_art432_2` führt sie getrennt.

⚠️ **Auslassung ist kein Fehlverhalten.** Art. 432 ist eine ausdrückliche
Erlaubnis. Die Zahl sagt „hier weicht ein Institut von seinen Peers ab", nicht
„hier wird etwas verschwiegen".

### `omission_persistence.csv` — dauerhaft oder wechselnd?

Die Zeitdimension derselben Frage, und sie trennt die beiden Ursachen, die der
Filing-Indicator nicht unterscheidet:

> **Nichtanwendbarkeit ist dauerhaft. Ermessen kann wechseln.**
> Wer kein Handelsbuch hat, hat auch im nächsten Quartal keines. Wer ein
> Template einmal offenlegt, dem *ist* es anwendbar — eine spätere Auslassung
> kann dann keine Nichtanwendbarkeit mehr sein.

Eine Zeile je (Institut, Konsolidierungskreis, Template). Gemessen wird
ausschließlich an Stichtagen, die **beides** sind: vom Institut gemeldet und von
seiner Frequenzklasse (`disclosure_frequency.csv`) erwartet. Ein halbjährliches
Template „fehlt" zwischen den Quartalen aus reiner Meldelogik; wer das mitzählt,
misst wieder den Meldekalender.

| | Paare | |
|---|---:|---|
| ohne Kalendermodell | 28.727 | das Frequenzmodell deckt 184 Koordinaten ab |
| < 2 erwartete Stichtage | 6.841 | kein Zeitvergleich möglich |
| `kalendertreu` | 2.381 | an allen erwarteten Stichtagen offengelegt |
| `dauerhaft` | 435 | an keinem — Nichtanwendbarkeit **nicht** ausschließbar |
| `wechselnd` | 523 | an manchen — Nichtanwendbarkeit **ausgeschlossen** |

#### Warum 523 die falsche Zahl zum Zitieren ist

Die häufigste „wechselnde" Lage ist `0-1-` — am 30.06. ausgelassen, am 31.12.
offengelegt, dazwischen gar nicht gemeldet. Sie tritt bei **36 Instituten
gleichzeitig** auf (Template `91.00`), bei `66.02` und `67.01` je 23-mal. Eine
Entscheidung, die 36 Häuser gleichzeitig treffen, ist kein Ermessen.

Die Ursache ist eine echte Grenze des Frequenzmodells: **es schätzt an
Instituten mit allen vier Stichtagen und wird hier auf Institute mit zweien
angewandt.** Wer nur 30.06. und 31.12. meldet, war an der Schätzung nie
beteiligt. Bei `91.00` kommt hinzu, dass sie auf 9 Instituten ruht, während das
Template über die Population eher jährlich aussieht — 21 % Offenlegung am
30.06. gegen 72 % am 31.12.

Deshalb trägt jede Zeile `n_signatur_geteilt` (wie viele andere Institute
dieselbe Lage im selben Template zeigen) und `frequenz_n_institute` (worauf die
Erwartung beruht). `einzelfall = ja` verlangt beides: Signatur bei weniger als
drei Instituten **und** eine Frequenz aus mindestens 20. Es bleiben **94
individuell zuschreibbare Fälle** — das ist die Zahl, die etwas über einzelne
Institute sagt.

Auch sie ist eine **Obergrenze**, aus demselben Grund wie `n_gegen_erwartung`.

### `irrbb_sensitivity.csv` — Zinssensitivität, gemessen statt geschätzt

Das IRRBB-Modul (`68.00`, EU IRRBB1) trägt die sechs aufsichtlichen
Zinsschock-Szenarien mit der Barwertänderung des Eigenkapitals (ΔEVE) und der
Zinsergebnisänderung (ΔNII). **235 Institute** melden es; bis September 2026 war
es im ganzen Projekt ungenutzt.

Der Massstab ist das Tier-1-Kapital aus KM1, und er ist nicht frei gewählt — die
**Supervisory Outlier Tests** definieren genau diesen Quotienten: 15 % für ΔEVE
(CRD Art. 98(5)), 5 % für ΔNII (EBA/GL/2022/14). Gezählt wird nur der *Verlust*.

#### Die EVE-Kategorie ist leer, und genau das ist der Befund

| | |
|---|---:|
| auswertbare Zeilen | 1.763 |
| Median ΔEVE / Tier 1 | −0,000 |
| p1 | −0,115 |
| **grösster Verlust** | **−14,84 %** |
| über der 15-%-Schwelle | **0** |

Null Überschreitungen — bei einem Maximum von 14,84 %. Die fünf schwersten Fälle
liegen bei −14,84 · −14,64 · −14,51 · −14,45 · −14,33 %, alle im letzten
Prozentpunkt vor der Grenze. **Die Verteilung bricht unmittelbar vor der
aufsichtlichen Schwelle ab**: das ist keine Eigenschaft der Zinsrisiken, sondern
die Grenze als bindende Nebenbedingung. Ohne die Randverteilung wäre „0
Überschreitungen" nicht von „nicht gemessen" zu unterscheiden.

#### Bei ΔNII ist die Kategorie nicht leer, und die Treffer haben ein Muster

22 Überschreitungen, fast alle unter *fallenden* Zinsen: flatexDEGIRO (−25,5 %),
Nordnet (−25,0 %), Clearstream (−21,5 %), Avanza (−19,1 %), Revolut (−15,3 %).
Broker, Neobanken und Verwahrstellen — Häuser, deren Ertrag am Zinsspread auf
gehaltene Kundengelder hängt. Kein Meldefehler, sondern ein Geschäftsmodell, das
der Test sichtbar macht.

⚠️ Zwei Vorbehalte stehen in der Spalte `vorbehalt`: `skala` für Reports mit
Skalenbefund aus #83 (die Deutsche Pfandbriefbank meldet 2.998 EUR Kernkapital —
ungefiltert 126 Zeilen scheinbarer Überschreitungen aus *einem* Fehler) und
`unplausibel`, wo der Verlust das gesamte Kernkapital übersteigt.

### `peer_similarity.csv` — ähnliche Institute nach Länderprofil

Die formale Peer-Gruppe (Grössenklasse × Konsolidierung × Stichtag) ist für
Perzentile richtig, beantwortet aber nicht „mit wem ist dieses Institut
vergleichbar". Gemessen wird die **Überlappung der Länderverteilung** des
Exposures aus `67.01.A`:

> überlappung(p, q) = Σ min(p_land, q_land)

Direkt lesbar: 0,68 heisst, dass 68 % des Exposures beider Häuser in denselben
Ländern liegt. Bewusst kein Kosinus — der wäre gegen unterschiedliche Breite
blind und für einen Leser nicht interpretierbar.

**Die Gegenprobe:** die stärksten Treffer sind Mutter/Tochter-Paare — ING Groep
↔ ING Bank bei 0,9999, Argenta Holding ↔ Argenta Bank bei 1,0000. Das Verfahren
findet Konzernzugehörigkeit aus der Exposure-Geografie wieder, *ohne je einen
Konzerngraphen gesehen zu haben*; unter den 100 besten Treffern sind 22
konzernintern, unter den 129 Treffern unterhalb von 0,80 noch genau einer. Die
Spalte `beziehung` benennt das aus #32/#42, damit ein Leser den Beleg nicht für
eine Entdeckung hält.

⚠️ **Das ist keine Peer-Gruppe.** Die Perzentile im Viewer bleiben auf der
formalen Schichtung; die Liste ist explorativ und im Viewer so beschriftet.

⚠️ **Die Grenze der Kennzahl betrifft ein Drittel der Fälle.** Zwei rein national
tätige Banken desselben Landes überlappen sich zwangsläufig fast vollständig: bei
über 90 % Domestizität liegt die beste Überlappung im Median bei 0,975, bei
breiter aufgestellten nur bei 0,760. Deshalb stehen `n_laender` und
`groesste_gemeinsamkeit` in jeder Zeile.

⚠️ **Die Zahlen oben sind seit dem Fix an `lade()` andere.** Bis dahin ging jede
Zeile aus `67.01.A` als Land in den Anteilsvektor ein — auch `x1`, die
**Gesamtzeile**, die die Summe der übrigen noch einmal trägt. Bei den 127
betroffenen Profilen lag ihr Anteil im Median bei exakt 0,500: zwei beliebige
Institute teilten sich schon darüber die halbe Masse.

Der Median über alle Paare verschob sich dadurch kaum (0,034 statt 0,030) — wer
nur den geprüft hätte, hätte nichts bemerkt. Die **Spitze** kippte vollständig:
0,970 → 0,345, 0,924 → 0,262. Und die Spitze ist genau das, was in dieser Datei
steht; eine ausgewiesene Überlappung von 0,92, gelesen als „92 % des Exposures
liegt in denselben Ländern", war schlicht falsch. Gefiltert wird jetzt auf
`open_axis_country IS NOT NULL` — keine Liste von Sonderfällen, sondern das
Merkmal, das eine Landzeile ausmacht.

### `peer_clusters.csv` — Gruppen mit gemeinsamem Fussabdruck

`peer_similarity.csv` liefert je Report die fünf nächsten Nachbarn. Das
beantwortet „wem ähnelt dieses Haus", nicht „welche Gruppen teilen einen
Fussabdruck" — die Frage aus dem Titel von #11 und #13. Dafür wird die
Ähnlichkeit **vollständig** gerechnet (56.825 Paare) und ab 0,90 zu
Zusammenhangskomponenten verbunden.

Drei Spalten tragen die Vorbehalte, ohne die die Ausgabe irreführend wäre:

| Spalte | wogegen |
|---|---|
| `kohaesion` | die kleinste paarweise Überlappung IN der Gruppe. A~B und B~C machen A, B, C zu einer Komponente, auch wenn A und C sich fremd sind — eine **Kette**, die wie ein Block aussähe |
| `institute` | die Einheit ist (LEI, scope, refPeriod). Beim ersten Lauf waren 37 von 69 „Gruppen" ein einziges Haus über mehrere Quartale; solche Selbstähnlichkeiten stehen nicht mehr drin |
| `traegerschaft` | `konzern` heißt: das Verfahren hat eine bekannte Struktur wiedergefunden (OTP Luxembourg ↔ OTP banka d.d.). Das ist eine Gültigkeitsprobe, kein Befund |
| `vektor_unvollstaendig` | CCyB1 erlaubt, unwesentliche Länder in `x28` zusammenzufassen. DekaBank trägt dort 53 % — die Zuordnung stützt sich auf 47 % des Buches. #13 verlangt die Markierung ausdrücklich |

⚠️ **„Keine Mutter gemeldet" heißt nicht „eigenständig".** GLEIF trennt
`NO_KNOWN_PERSON` / `NON_CONSOLIDATING` / `NATURAL_PERSONS` („es gibt keine")
von `NO_LEI` / `NON_PUBLIC` („wir kennen sie nicht"). Nur das erste ist eine
Auskunft; beim zweiten steht `ungeklaert`, nicht `unabhaengig`.

**Der Befund — und er widerspricht der Erwartung.** #13 erwartet „Cluster, die
nicht mit dem Heimatland zusammenfallen müssen … eine österreichische und eine
italienische Bank können denselben CEE-Footprint haben". Gemessen: von **26
Gruppen ist genau eine grenzüberschreitend**, und das ist OTP Luxembourg mit OTP
banka d.d. — derselbe Konzern. **Null** Gruppen mit belegt verschiedenen Trägern
über Ländergrenzen. Die Gruppen fallen mit dem Heimatland zusammen.

Ein Zwischenstand sagte das Gegenteil: sechs Häuser aus Malta, Griechenland,
Finnland und Italien schienen einen Fussabdruck zu teilen. Das war der
`x1`-Fehler oben — ihre „gemeinsamen Länder" waren DE, FR, IE (die neun von zehn
Profilen tragen) und `x28`, der Residualbucket. Mit der Korrektur löste die
Gruppe sich auf.

### `country_effect.csv` — hängt die Bank am Heimatland? Nein.

Die These aus #11 — Bankattribute aus BIP- und Zinszeitreihen des Heimatlands
erklären — ist geprüft und trägt nicht. Der Zins-Teil scheitert schon an der
Konstruktion (EURIBOR hat zu einem Stichtag für alle Banken denselben Wert). Für
den Rest gilt:

Eine Kennzahl des Heimatlands ist für alle Institute desselben Landes identisch
und kann nur erklären, was **zwischen** Ländern streut. Diese Zerlegung ist eine
Identität, keine Schätzung:

| | Anteil |
|---|---:|
| Varianz zwischen Ländern | 31,8 % |
| Varianz **innerhalb** | **68,2 %** |

Damit gilt **R² ≤ 0,318 für jede denkbare Länderkennzahl**, auch für noch nicht
erhobene. Gemessen erreicht das BIP r² = 0,0013 — **0,4 % des Erreichbaren**.
Auch der naheliegende Rettungsversuch („dann eben die Finanzplatzintensität")
scheitert: Irland liegt bei Exposure/BIP am unteren Ende und bei der
Domestizität trotzdem ganz unten.

Der Ländereffekt ist trotzdem gross — die Mediane reichen von 0,061 (Irland) bis
0,993 (Norwegen). Er ist nur kein *Makro*effekt. Wer die Domestizität erklären
will, braucht Instituts- und keine Ländermerkmale; das ist die Richtung von #13
und #35.

### `disdocs_language.csv` — in welcher Sprache berichten die Institute?

Die Vorbedingung aus #38, und sie war der Grund, warum dort nichts gebaut wurde:

> ⚠️ **31 Länder, entsprechend viele Sprachen.** Eine Schlagwortsuche auf
> Deutsch oder Englisch erfasst einen verzerrten Ausschnitt.

`probe_disdocs.py` hatte den Extraktionstest erledigt (97 % der PDFs tragen eine
Textebene), die Sprache aber blieb offen: **kein einziges PDF gibt ein `/Lang`
an.** Erkannt wird sie deshalb über Funktionswörter — Artikel, Präpositionen,
Konjunktionen, die in jedem Sachtext vorkommen und nicht am Fachgebiet hängen.

#### Die Antwort

| | n=58 |
|---|---:|
| Englisch | 30 (52 %) |
| Deutsch | 11 |
| Italienisch | 6 |
| übrige (cs, da, hr, pl, sk, sv, es, fr) | 11 |

**Eine Schlagwortsuche nur auf Englisch erreichte 52 % des Korpus.** Die
Verzerrung, vor der das Issue warnt, ist damit beziffert statt vermutet — und
sie ist gross genug, dass jede einsprachige Auswertung die Hälfte der
Institute systematisch auslässt.

#### Warum man dem Erkenner glauben darf

Ein Spracherkenner ohne Gütemaß ist eine Behauptung. Zwei Gegenproben, beide
unabhängig von ihm:

1. **Gegen das Sitzland.** Jede erkannte Sprache ist entweder die Amtssprache
   des Sitzlands (32) oder Englisch (26). **Null** implausible Treffer — bei
   einem verrauschten Erkenner stünden hier zufällige Sprachen.
2. **Gegen sich selbst.** In einer gezielten Stichprobe von 15 Instituten mit
   mehreren Berichten tragen **14 von 14** durchgehend dieselbe Sprache. Ein
   Sprachwechsel zwischen Stichtagen wäre entweder ein Erkennungsfehler oder
   eine echte Umstellung — beides käme in den Bericht.

Die zufällige Stichprobe enthielt genau *ein* Institut mit zwei Berichten; für
die zweite Gegenprobe wird deshalb **gezielt** gezogen (`--paare`). Zufällig zu
ziehen und dann über das Ergebnis zu reden wäre eine Aussage über das Glück der
Ziehung.

#### Was der Erkenner nicht kann

Bei eng verwandten Sprachen (Tschechisch/Slowakisch, Dänisch/Norwegisch/
Schwedisch) trennen Funktionswörter nur knapp. Liegt der Abstand zum
Zweitplatzierten unter der Schranke, lautet das Urteil `unsicher` statt der
wahrscheinlicheren Sprache — in der Paarstichprobe traf das 1 von 30.

**Korpusgrösse:** 1.073 Pakete, hochgerechnet rund 2 GB (Median 0,99 MB je
Paket, max 11,3 MB). Der gesamte XBRL-Bestand liegt bei 13 MB.

### `equity_link.csv` — vom Institut zum handelbaren Papier

Die zweite Hälfte von #39, soweit sie **ohne fremde Daten** zu erledigen ist.
69 belegt börsennotierte Institute, davon **56 mit Aktien-ISIN** und **42 mit
dem Ticker ihrer Primärnotierung**.

#### Warum nicht GLEIF

Das Issue nennt GLEIF `/isins`, und der Weg funktioniert — an 12 Instituten
geprüft, alle mit Treffern. Er liefert aber den **falschen Instrumententyp**:
Intesa Sanpaolo trägt dort 1.676 ISINs, ganz überwiegend Anleihen. Eine
Ereignisstudie auf Aktienkursen braucht *die eine* Aktien-ISIN, und GLEIF
unterscheidet den Typ nicht. Wikidata führt sie als `P946`.

#### Die Falle: Wikidata ordnet die Börsen nicht

`P414` listet alle Notierungen ohne Rangfolge. Die erstbeste zu nehmen geht
sichtbar schief:

```
UniCredit                 -> Frankfurt Stock Exchange, Ticker CRI
Banca Monte dei Paschi    -> OTC Markets Group,        Ticker BMDPY
```

`BMDPY` ist ein **ADR**. Ein Ereignisfenster auf einem dünn gehandelten
Zweitpapier misst Rauschen — und es sähe aus wie ein Ergebnis, weil am Ende
Zahlen mit Nachkommastellen stehen.

Entschieden wird über das **Länderpräfix der ISIN**: `IT0005218752` heisst
Italien, also ist die Mailänder Notierung die primäre. Passt keine, bleibt das
Feld leer und `sicherheit` sagt warum — geraten wird nicht.

| `sicherheit` | n |
|---|---:|
| `eindeutig` | 39 |
| `keine isin` | 13 |
| `ohne ticker` | 9 |
| `keine Notierung im ISIN-Land` | 5 |
| `mehrere im ISIN-Land` | 3 |

> ⚠️ **Kursdaten bleiben die offene Hälfte.** Dieses Blatt schliesst die Lücke
> auf unserer Seite: 42 Institute sind an eine Kursreihe anschliessbar, sobald
> es eine gibt.

### `event_study_feasibility.csv` — trägt der Bestand eine Ereignisstudie?

Die Vorfrage aus #39, beantwortet statt geschätzt. Wir besitzen den
**Einreichungszeitpunkt auf die Sekunde** (4.278 Zeilen mit `submission_ts`) —
das ist ein Ereignisdatum, und Ereignisdaten sind die Währung der
Kapitalmarktforschung. Ob daraus eine Studie werden kann, hängt an zwei Zahlen.

#### Ein Ereignis ist nicht eine Einreichung

Ein Institut reicht mehrere Module am selben Tag ein. **4.278 Einreichungen
verdichten sich auf 1.964 (Institut, Tag).** Wer Einreichungen zählt, hält die
Stichprobe für doppelt so gross.

#### Isolation und Notierung halbieren sie zweimal

| Fenster | isoliert | Anteil | davon börsennotiert | mit `hoch`-Befund | Urteil |
|---|---:|---:|---:|---:|---|
| ±3 d | 1.024 | 52 % | **243** | 154 | tragfähig |
| ±5 d | 825 | 42 % | 192 | 127 | tragfähig |
| ±10 d | 546 | 28 % | 122 | 89 | tragfähig |
| ±21 d | 363 | 18 % | 75 | 52 | grenzwertig |

Die Spalte **börsennotiert** ist die Stichprobe, die eine Aktien-Ereignisstudie
wirklich hätte — nicht `isoliert`. Vier von fünf Instituten dieses Bestands
haben keine handelbare Aktie (Sparkassen, Genossenschafts- und Förderbanken).
Von 489 Instituten sind **69 belegt notiert**; 257 tragen keinen
Wikidata-Eintrag, ihr Status ist damit **unbekannt und nicht „nicht notiert"**.

Die letzte Spalte ist die Behandlungsgruppe der schärferen Frage aus #39:
reagiert der Markt *stärker*, wenn die Offenlegung etwas Unangenehmes enthält?
154 isolierte Ereignisse börsennotierter Institute tragen einen `hoch`-Befund
aus #17.

> ⚠️ **Obere Schranke, keine Schätzung.** Die zweite Konfundierung aus #39 ist
> nicht aufgelöst: Pillar-3-Offenlegung fällt oft mit dem Geschäftsbericht
> zusammen, und dessen Datum liegt uns nicht vor. Jedes solche Ereignis fällt
> zusätzlich heraus.

> ⚠️ **Kursdaten sind keine offene Quelle.** Dieses Blatt sagt, ob sich die
> Beschaffung lohnen würde — es ersetzt sie nicht.

### `catalogue_coverage.csv` — ist die Stichtagswelle geladen?

Die Frage aus #7, und sie war ohne dieses Blatt nur von Hand zu beantworten.
925 Katalog-Reports, **882 geladen (95,4 %)**. Die naheliegende Rechnung
„Katalog minus Bestand = 43 Rückstand" ist dabei falsch, weil die 43 vier
verschiedene Dinge sind:

| Einstufung | n | was es ist |
|---|---:|---|
| `nur_pdf` | 40 | veröffentlicht nur DISDOCS — PDF, kein XBRL-CSV |
| `ohne_platzierbare_fakten` | 1 | geparst, in der Coverage-Matrix, kein platzierbarer Fakt (#28) |
| `toter_link` | 2 | Katalogzeile ohne publizierte Datei (EDAP 404) |
| **`offen`** | **0** | ladbar und noch nicht geladen |

**Nur die letzte Zeile beschreibt eine Aufgabe.** Die 40 PDF-Institute als
Rückstand zu führen hiesse, eine Eigenschaft der Quelle als eigenes Versäumnis
zu buchen; die zwei toten Links stehen dauerhaft in `manifest_todo.csv` und
verschwinden nie.

Der `ohne_platzierbare_fakten`-Fall ist der heikelste: die Einreichung wurde
geladen, geparst und deklariert Templates, trägt aber keinen einzigen
platzierbaren Fakt. Sichtbar wird sie nur, wenn man die Coverage-Matrix gegen
die Long-Form hält — sonst sieht sie aus wie eine geladene.

Alle fünf Stichtage liegen vor (2025-06-30, 2025-09-30, 2025-10-31, 2025-12-31,
2026-03-31); 209 Institute tragen mindestens zwei, womit Zeitreihen und die
Zeitprüfung aus #36 real greifen.

### `risk_taker_share.csv` — wie breit zieht ein Haus den Kreis der Risikoträger?

Die Kennzahl aus #40, und sie entsteht **erst durch die Kombination**: REM1
(`30.01` r0010) liefert die Zahl der „identified staff" nach CRD Art. 92,
Wikidata über die LEI (`P1278` → `P1128`) die Gesamtbelegschaft. Der Quotient
sagt, wie weit ein Institut den Kreis der Mitarbeiter zieht, deren Tätigkeit sich
wesentlich auf das Risikoprofil auswirkt — ein Ermessensspielraum, für den es
bisher keine vergleichenden Zahlen gibt. 83 Reports, 68 im Modell.

#### Die Rohquote misst die Grösse, nicht das Ermessen

Roh reicht der Anteil von 0,30 % bis 54,67 % — Faktor 180. Das sieht nach einem
gewaltigen Ermessensunterschied aus und ist zum grössten Teil keiner:

| Belegschaft | n | Median-Anteil |
|---|---:|---:|
| < 500 | 18 | 14,37 % |
| 500–5.000 | 28 | 5,80 % |
| 5.000–50.000 | 18 | 1,81 % |
| > 50.000 | 4 | 1,14 % |

`log10(Belegschaft)` gegen `log10(Anteil)`: **r = −0,869, r² = 0,755**. Drei
Viertel der Streuung erklärt die Belegschaftsgrösse allein — und das ist
Sachlogik, kein Artefakt: eine Grossbank mit 194.000 Beschäftigten hat
Zehntausende im Filialvertrieb, deren Tätigkeit das Risikoprofil nicht
wesentlich beeinflusst. Ein Spezialfinanzierer mit 101 Mitarbeitern hat sie
nicht.

> ⚠️ **Wer die Rohquote als Governance-Aussage veröffentlicht, veröffentlicht
> eine Grössenmessung mit einem Governance-Etikett** — dieselbe Falle wie die
> rohe Auslassungsquote in #43, die RWA-Dichte in #45 und die Ländermittel
> in #11.

#### Gemessen wird deshalb der Rest

`faktor_gegen_erwartung` = tatsächlicher Anteil / dem Anteil, den die
Belegschaftsgrösse vorhersagt (Modell: `Anteil ≈ 10^(−0,500·log10(Belegschaft)
+0,333)`, geschätzt je Institut und nur auf Zeilen ohne Vorbehalt). Ein Wert
von 2,0 heisst: **doppelt so viele Risikoträger wie Häuser dieser Grösse** — und
das ist eine Aussage über die Auslegung.

Die Korrektur zieht die Spanne von Faktor 180 auf p10 0,48 / Median 1,03 /
p90 1,87 zusammen. Am weitesten gezogen: Raiffeisen Bank International 3,31×,
Sparebank 1 Østlandet 3,11×, Helaba 2,71×. Am engsten: VÚB 0,23×, MONETA Money
Bank 0,34×, Bausparkasse Schwäbisch Hall 0,38×.

Dass die Korrektur wirkt und nicht nur glättet, zeigt der **Perimetertest**:
Wikidata führt eine Gruppenzahl, ein IND-Report aber die Risikoträger des
Einzelinstituts. Roh liegen die IND-Quoten deshalb um Faktor 3,7 über den
CON-Quoten (9,7 % gegen 2,6 %); nach Abzug der Grösse bleibt davon Faktor 1,04
(1,042 gegen 1,006). Wo beide Perimeter vorliegen, gewinnt CON.

#### Drei Vorbehalte, alle gemessen

1. **Die Stichprobe ist nicht der Bestand.** Von 474 LEIs finden sich 232 in
   Wikidata (49 %), aber nur **112 tragen eine Mitarbeiterzahl (24 %)** — und
   diese sind nach TREA im Median **2,4-mal grösser** als die übrigen
   (10,5 gegen 4,4 Mrd EUR). Die Verteilung hier ist grosslastig.
2. **Wikidata ist crowdsourced.** Die Zahlen sind unterschiedlich aktuell und
   verschieden abgegrenzt (Kopfzahl gegen Vollzeitäquivalente). `P1128` trägt
   oft mehrere Aussagen mit verschiedenen Stichtagen — behalten wird die mit dem
   **jüngsten** (`mitarbeiter_stand`, bei 100 von 112 vorhanden); undatierte
   verlieren gegen datierte. `wikidata_id` macht jeden Wert nachprüfbar.
3. **Beide Seiten der Division brauchen einen Filter.** REM1 ist genau das
   Template, in dem #17 die stärksten Ausreisser findet. 15 Reports mit
   `rem_per_head`-Befund tragen `vorbehalt=rem_befund`, gehen nicht ins Modell
   und sind keine Governance-Aussage.

### `irb_risk_weights.csv` — Risikogewichte je PD-Band

Was die EBA-Benchmarking-Übung misst, aber nicht institutsgenau veröffentlicht:
CR6 (`26.00.A`) trägt je Institut, Forderungsklasse und PD-Band das Exposure,
die ausfallgewichtete PD, die LGD und den Risikogewichtsbetrag. **90 Institute**
melden es, 16.464 Zeilen.

#### Der Befund

Bei gleicher Ausfallwahrscheinlichkeit und gleicher Forderungsklasse streuen die
Risikogewichte über die Institute um einen Faktor von **4,5 bis 6,6** (p90/p10,
nur wesentliche Zellen). Der sauberste Fall ist das **Defaultband**: dort ist
die PD auf 100 % fixiert und kann die Streuung nicht erklären —

| Forderungsklasse | n | p10 | Median | p90 | Faktor |
|---|---:|---:|---:|---:|---:|
| `qx2081` | 88 | 0,348 | 0,809 | 1,916 | 5,5 |
| `qx2013` | 79 | 0,351 | 0,711 | 1,861 | 5,3 |
| `qx2009` | 44 | 0,541 | 0,891 | 2,428 | 4,5 |

Was übrig bleibt, sind LGD-Schätzung und Wertberichtigungen. Deskriptiv, nicht
kausal: eine niedrige Dichte kann ein besichertes Portfolio *oder* eine
großzügige Modellierung bedeuten — und genau deshalb gibt es den Output-Floor.

#### Vier Fallen, und jede einzelne zerstört die Auswertung

**1. Die PD-Spalte heißt „(%)" und ist meistens keine.** 15.638 von 15.997
Werten liegen bei ≤ 1. Geraten werden muss das nicht: die Zeilenbeschriftung
nennt das Band (`0.25 to <0.50`, in Prozent), und daran lässt sich die Einheit
**messen**. Über 11.177 Werte: 82,1 % passen nur als Bruch, 3,2 % nur als
Prozent, 12,0 % als beides. Die Einheit gehört dem **Report**, nicht der Zelle —
135 von 142 melden als Bruch, 4 in Prozent, 3 bleiben `unklar` und werden nicht
normiert.

**2. Die Bänder überlappen sich.** `r0010` (0,00–0,15) enthält `r0020` und
`r0030`; ebenso `r0070`, `r0100`, `r0130`. Wer alle 18 Zeilen summiert, zählt
das Exposure doppelt. Die Hierarchie ist nachgemessen exakt (Medianabweichung
0,00000); die Spalte `ebene` trennt `grob` (8 Bänder) von `fein` (13) und
`summe`. **Nie über Ebenen hinweg aggregieren.**

**3. Das Gitter ist dünn besetzt.** 2.736 Zellen führen PD = 0 *und*
Exposure = 0 — sie sind keine Meldung, sondern eine Leerstelle. Eine erste
Fassung wertete jede davon als „PD unterhalb ihres Bandes" und meldete 3.016
Verstöße statt 230.

**4. Kleinstbeträge messen Rundung, nicht Modellierung.** Ein Risikogewicht von
0,008 bei 20 % PD ist intern konsistent — es steht auf 87.671 EUR Exposure und
699 EUR RWEA. Zellen unter 10 Mio EUR sind 19 % der besetzten Zellen und tragen
**0,017 %** des Exposures; die Spalte `wesentlich` nimmt sie aus der Statistik
und lässt sie in der Datei.

#### Zwei Gegenproben

**Die gemeldete Dichte gegen die gerechnete.** `c0100` ist unabhängig gemeldet
und muss `c0090 / c0040` sein: über 12.671 Paare Medianabweichung **0,0000** —
und zwar als Bruch, die Spalte ist trotz ihres Namens keine Prozentangabe. 846
Zellen weichen ab: 140 melden die Dichte in Prozent, 212 umgekehrt, 282 sind
echte Widersprüche zwischen zwei Spalten desselben Reports.

**Die PD gegen ihr eigenes Band.** `c0050` ist die exposure-gewichtete PD
*innerhalb* des Bandes und muss dort liegen. Von 11.546 besetzten Zellen tun das
11.316; die 230 Abweichungen sind überwiegend Randwerte (PD = 0,15 im Band
„0.10 to <0.15").

⚠️ **Die Forderungsklasse ist nicht auflösbar.** CR6 führt sie als offene Achse
(`qEEA=eba_qAE:qx2012`), und für `26.00` liegt im Codebook keine
Achsenauflösung. Der Code steht roh in `klasse_code`. Für den Vergleich reicht
das — er läuft innerhalb einer Klasse —, aber ohne Klartextnamen ist die Zeile
fachlich nicht einzuordnen (Lücke im Codebook, #3).

### `footprint.csv` — Länderstreuung, und was `reliable` seit #83 bedeutet

Je (Institut, Konsolidierungskreis, Stichtag) die geografische Verteilung des
Exposures aus CCyB1 (`67.01.A`, Spalte `c0060`): Domestizitätsquote, Herfindahl
über die Länderanteile, Zahl der benannten Länder.

#### Zwei Spalten für zwei verschiedene Fragen

| Spalte | sagt |
|---|---|
| `reliable` | ist die Zeile **im Ganzen** zu gebrauchen? |
| `vorbehalt` | **welcher** Einwand greift — `kein_heimatland`, `residual`, `skala` (mehrere mit `\|` verbunden) |

Der Unterschied ist nicht kosmetisch. Bis #83 stand `reliable` bei **28 Zeilen**
auf `true`, deren Exposure um Größenordnungen zu klein ist. Der Beleg:

| ING Bank Śląski | Gesamtexposure | `domestic_share` |
|---|---:|---:|
| 2025-06-30 | 39.863 EUR | 0,9820 |
| 2025-12-31 | 41.827.858.555 EUR | 0,9858 |

Faktor 10⁶ im Betrag, die Quote praktisch unverändert. Ein gleichmäßiger
Skalenfehler **kürzt sich in jedem Verhältnis heraus**.

⚠️ **Daraus folgt eine Leseregel.** Wer `total_exposure_eur` summiert, nimmt nur
`reliable = true`. Wer Domestizität oder Konzentration auswertet, holt sich die
Zeilen mit `vorbehalt = skala` ausdrücklich **zurück** — dort sind die Quoten
gültig, und sie wegzulassen verkleinerte die Grundgesamtheit ohne Grund.

#### Warum die Templateebene mitgelesen wird

`scale_flags.csv` kennt Report- und Templateebene. Hier zählen beide — und die
zweite ist kein Sonderfall: ING Bank Śląski ist **reportweit unauffällig**
(Versatz −0,15), skaliert ist genau `67.01.*`, also die Quelle dieser Datei. Ein
Filter nur auf die Reportebene hätte ihn durchgelassen.

Ein `verdacht` genügt hier als Vorbehalt, anders als in `check_plausibility.py`:
dort geht es um eine Grundgesamtheit, hier um einen einzelnen Betrag, der in
keine Summe eingehen darf.

Gemessen: 377 Zeilen, davon 335 ohne Vorbehalt, 31 mit `skala`, 14 mit
`residual`.

### `disclosure_frequency.csv` — die Frequenz, gemessen statt abgeschrieben

Je (Größenklasse, Template) die Offenlegungsfrequenz, abgeleitet aus dem
Verhalten der Melder. Sie steht in Art. 433a–c CRR; sie zu kodieren wäre
möglich, aber schwächer — gemessen wird, was Institute **tun**, und Abweichungen
davon sind selbst ein Befund.

Ohne dieses Modell stolpert jede Auswertung über Stichtage hinweg: ein
halbjährlich offengelegtes Template „verschwindet" zwischen den Quartalen und
sieht dabei aus wie eine Auslassung (#43) oder wie ein Sprung (#36).

#### Muster je Institut, nicht Quote je Population

Die naheliegende Messung — der Anteil der Melder je (Template, Stichtag) — ist
unbrauchbar: **ein Drittel der Quoten liegt zwischen 20 und 80 %**. Eine
Schwelle darauf erfände eine Trennung, die die Zahlen nicht hergeben.

Gemessen wird deshalb das **Muster eines einzelnen Instituts** über die vier
Stichtage, als Vierer-Kette `06-30 · 09-30 · 12-31 · 03-31`. Das ist scharf:
über 4.407 vollständige Paare fallen **96,5 % in genau vier Muster**.

| Muster | Anteil | Bedeutung |
|---|---:|---|
| `1010` | 36,2 % | halbjährlich |
| `0000` | 33,6 % | nie (Template trifft dieses Institut nicht) |
| `0010` | 15,6 % | jährlich |
| `1111` | 11,1 % | vierteljährlich |
| Rest | 3,5 % | uneinheitlich |

Eine Koordinate trägt nur dann eine Frequenz, wenn mindestens 5 Institute
beitragen **und** das Modalmuster ≥ 60 % erreicht — sonst steht dort
`uneinheitlich`. Von 184 Koordinaten sind 88 eindeutig.

#### Die Gegenprobe

Drei Frequenzen sind bei #43 unabhängig aus den Populationsquoten abgelesen
worden und kommen hier wieder heraus:

| Template | | gemessen | Modalanteil |
|---|---|---|---:|
| `61.00` | KM1 | vierteljährlich | 98 % von 58 |
| `74.00` | LIQ2 | halbjährlich | 93 % von 58 |
| `19.03` | OR3 | jährlich | 93 % von 58 |

#### Der inhaltliche Befund: Proportionalität, sichtbar gemacht

Dieselbe Angabe hat je nach Größenklasse eine andere Frequenz. `19.03` (OR3) ist
für große EEA-Institute **jährlich**, für Tochtergesellschaften **nie** — Art.
433a gegen 433b/c, an den Daten abgelesen.

#### Drei Vorbehalte

**1. Nur 82 der 476 Institute tragen ein Muster bei.** Ein Muster braucht alle
vier Stichtage — und wer nur zum Jahresende meldet, hat keines. Das ist keine
Stichprobe, sondern eine Auswahl nach genau der Eigenschaft, die gemessen wird.
Für `Other highest EEA` bleiben **8 Paare**; für diese Klasse sagt die Datei
nichts.

**2. Vier Stichtage unterscheiden „jährlich" nicht von „einmalig".** Das
entscheidet erst die nächste Welle.

**3. `nie` heißt nicht „müsste nicht".** Die Trennung von Nichtanwendbarkeit und
Ermessen bleibt offen (#43).

⚠️ **Geprüft, nicht angenommen:** 2026-03-31 ist zugleich der einzige
RF-4.2-Stichtag, und ein geänderter Meldebogen sähe aus wie eine geänderte
Frequenz. Nachgemessen trägt der Filing-Indicator-Bogen an **allen** Stichtagen
dieselben 114 Templates — keines fällt weg, keines kommt dazu.

### `group_graph_check.csv` — die zwei Konzerngraphen gegeneinander

Im Repo liegen **zwei** Konzerngraphen: GLEIF Level-2 (`lei_relations.csv`, 189
oberste Mütter) und die EZB-Hierarchie (`coverage_gap.csv`, 797 Gruppenköpfe).
`build_eba_reconciliation.py` schließt über den ersten 90 Institutszeilen aus,
damit ein Länderaggregat Mutter und Tochter nicht doppelt zählt — wäre er
falsch, wären es die Aggregate auch.

97 Institute haben in beiden Quellen einen Kopf:

| Urteil | n |
|---|---:|
| `identisch` | 67 |
| `ssm_schnitt` | 30 |
| `konflikt` | **0** |

#### Die 30 Abweichungen sind kein Fehler, sondern die Perimetergrenze

Die beiden Graphen beantworten verschiedene Fragen: die EZB nennt den Kopf der
**beaufsichtigten Gruppe im SSM**, GLEIF den **Konzern**. In allen 30
Abweichungen liegt der GLEIF-Kopf außerhalb der EZB-Liste, und bei 27 davon ist
der EZB-Kopf das Institut selbst — es *ist* die Spitze seiner beaufsichtigten
Gruppe.

| Institut | EZB-Kopf | GLEIF-Kopf |
|---|---|---|
| BofA Securities Europe SA | sie selbst | Bank of America (US) |
| HSBC Continental Europe | sie selbst | HSBC Holdings (UK) |
| AB SEB bankas (LT) | sie selbst | SEB AB (SE, außerhalb SSM) |

Die Gegenprobe stützt das: bei **allen 67** Übereinstimmungen liegt der Kopf
innerhalb der EZB-Liste.

⚠️ **Keiner der beiden ersetzt den anderen.** Für Aggregate ohne Doppelzählung
ist der EZB-Kopf richtig — eine US-Mutter meldet nicht nach CRR Teil 8 und kann
in einem EU-Aggregat gar nicht doppelt zählen. Für die Frage, wem ein Institut
gehört, ist es GLEIF.

#### Warum „0 Konflikte" hier eine Aussage ist

`konflikt` heißt: der GLEIF-Kopf steht in der EZB-Liste, ist dort aber ein
anderer. Diese Kategorie ist leer — und eine Prüfung, deren interessante
Kategorie leer ist, sieht aus wie eine, die nichts tut.

Der Unterschied ist die Gegenprobe: 97 Vergleichspaare, davon 30 mit
abweichendem Kopf. Der Vergleich **greift**, er findet nur keinen Widerspruch.
Ein Test hält genau das fest — fände er nirgends eine Abweichung, wäre „kein
Konflikt" kein Ergebnis, sondern ein Symptom.

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

**Zwei Marken, zwei verschiedene Aussagen — sie sind nicht austauschbar.**
`plausibility_findings.csv` sagt „*dieser* Wert passt nicht zur Verteilung
seiner Zellpopulation"; `scale_flags.csv` sagt „die absoluten Beträge *dieses
Reports* liegen um einen Faktor daneben". Die erste Prüfung kann die zweite Sorte
gar nicht finden — sie sieht nur nach oben, ein Skalenfehler zeigt nach unten
(Abschnitt `scale_flags.csv`). Wer allein aus einem leeren Befundprofil auf einen
sauberen Report schließt, liegt bei 50 von 100 markierten Reports falsch.

#### Der Zeitvergleich als dritte Aussage (#36)

`plausibility_findings.csv` führt seit #36 zwei weitere Regeln, erkennbar an
der Spalte `rule`:

| `rule` | Maßstab | Referenz in `reference` |
|---|---|---|
| `cell_outlier` | die Zellpopulation aller Institute | Median der Zelle |
| `rem_per_head` | ein fachlicher Korridor | Mitte des Korridors |
| `time_jump` | **das Institut selbst, ein Stichtag vorher** | der eigene Wert am Nachbarstichtag |
| `time_break` | dasselbe, aber über den ganzen Report | Median aller Sprünge |

Der Zeitvergleich braucht keine Peer-Gruppe, keine Größenklasse und keine
Währungsannahme — das Institut ist sein eigener Maßstab. Er ist deshalb auch
der einzige, der einen Skalenfehler **von unten** sehen kann.

Drei Eigenschaften, ohne die die Spalten falsch gelesen werden:

- **Ein Zeitbefund steht an BEIDEN Reports des Paares.** Welcher der zwei
  falsch liegt, sagt die Prüfung nicht — und die naheliegende Wahl wäre die
  falsche: bei der Deutschen Pfandbriefbank ist der *frühere* Report der
  skalierte, der spätere sauber. `vergleich_refPeriod` nennt jeweils den
  anderen Stichtag.
- **`time_break` ist eine Aussage über den Report, nicht über eine Zelle** und
  trägt deshalb kein Template. Er greift ab 5 % springender Zellen (p95 der
  beobachteten Verteilung); 21 Report-Paare erreichen ihn und tragen zusammen
  77 % aller Zellsprünge. `hinweis` führt Anteil und Median mit: liegt der
  Median bei ~3 oder ~6 Größenordnungen, war es ein Faktorwechsel, sonst eher
  ein echter Strukturbruch (Verkauf, Entkonsolidierung, Fusion).
- **Ein Sprung ist nicht per se ein Meldefehler.** Der Befund lautet
  „unerklärter Sprung".

Die Gegenprobe: 8 der 21 Report-Paare mit Strukturbruch enthalten einen Report,
den `scale_flags.csv` unabhängig als `skaliert` führt — darunter fünf der sechs
am höchsten konzentrierten. Zwei Verfahren ohne gemeinsame Evidenz zeigen auf
dieselben Reports.

`findings_per_1000` rechnet seit #36 gegen **beide** Arten von Gelegenheit:
prüfbare Fakten (`n_facts_checked`) plus vergleichbare Zeitpaare
(`n_zeitpaare`). Ein Institut mit vier Stichtagen wurde häufiger geprüft als
eines mit einem.

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
