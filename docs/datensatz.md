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
| `processed/irb_risk_weights.csv` | Institut × Forderungsklasse × PD-Band → Risikogewicht, PD, LGD | CR6 `26.00.A` |
| `processed/footprint.csv` | Institut → Länderstreuung des Exposures, Domestizitätsquote, HHI | CCyB1 `67.01.A` |

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
