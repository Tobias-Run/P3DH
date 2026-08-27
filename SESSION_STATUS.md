# Session Status — 2026-08-21

> Diese Datei ist die laufend aktualisierte Wahrheit zum Projektstatus.
> Am Ende jeder Session auf den tatsächlichen Stand bringen — nicht verwaisen lassen.

## Phasen-Übersicht

| Phase | Status | Stand |
|---|---|---|
| 0 — Scoping & Zugang | ✅ | Decision Memo, Format-Analyse, EDAP-Zugang, Git/GitHub |
| 1 — Ingestion | ✅ | Voll-Katalog-Harvester `harvest_catalog_query.py` (Power-BI-`query`, alter Scroll deprecated) → **4.278 Submissions / 489 Institute**. **20%-Stichprobe geladen** (346 ZIPs). **Delta-Pipeline**: Harvest-Diff (`harvest_log.csv`/`manifest_delta.csv`) + inkrementeller Parser (`source_file`, `--full`) |
| 2 — Parsing & DPM-Join | ✅ | `long_form_raw.csv` **209.231 Records / 218 Reports** (Multi-Modul); 9146/9146 Datapoints aufgelöst, gelabeltes `dpm_codebook.csv` (+ `data_type` aus DPM); Template-Titel via EBA-Layout |
| 2.5 — Refinement | ✅ | offene Achse als `open_axis_dims` erfasst (Re-Parse über alle Reports durch) |
| 3 — Multi-Modul | ✅ | CODIS + ESGDIS/FINDIS/GSIIDIS/IRRBBDIS/MRELTLACDIS (KM2)/REMDIS geparst; nur `*DISDOCS` (PDF) ausgenommen |
| 3b — RF 4.1↔4.2-Mapping | 🟡 | **Zell-Brücke steht** (`codebook/framework_bridge.csv`, beobachtungsbasiert): 916 Zellen stabil, **19 auf neue dp-Codes umgebunden** (KM1-Leverage-Puffer!, OV1-AIM, CVA, LR2). Details `docs/phase3_framework_bridge.md`. Wächst mit jeder 4.2-Welle (Re-Run); Konsumenten-Integration geprüft: **nicht nötig** — Zweig A/B joinen bereits zell-basiert. Stattdessen Placement-Guard gegen stillen Fact-Verlust (`check_fact_placement.py`) |
| 4A — Zweig A | ✅ | **JSON-Viewer = Standard** (`viewer_json.html`): **Slim-`index.json`** (nur Report-Meta, ~0,01 MB gzip) + `codebook.json` vorab; **`benchmark.json`** (KM1/OV1-Head, ~0,14 MB) **lazy** für Benchmark/Zeitreihe; jeder Report lazy als `data/reports/<key>.json` (~3 KB). Featuregleich (typisierte Skalen, EUR, Filter, Benchmark-Profile, Zeitreihen, Vergleich, Dark, Deep-Links). **Voll-Load-tauglich**: Index-Projektion ~0,2 MB gzip @ 4.278 Reports; Shards inkrementell geschrieben. **CSV-Viewer** (`viewer.html`) = Legacy; Gabelseite `index.html` |
| 4B — Zweig B | ✅ | `build_zweig_b.py` → `processed/long/p3dh_long.parquet` (self-contained, DuckDB; +`fact_value_raw`/`fx_rate`), Beispiele in `docs/zweig_b_queries.md`. **Speist auch Zweig A**: `build_zweig_a_shards.py` leitet die JSON-Shards allein aus dem Parquet ab → eine Transformationsstelle, kein Drift (Werte byte-identisch verifiziert) |
| 4 — Explorationen | 🟡 | Analyse-Ideen datengeerdet → `docs/phase4_analysis_ideas.md`. **Benchmark vertieft** (Issue #4): 6 Profile (KM1, Headroom, Risiko, Liquidität, **NPL/CQ3**, **ESG/41.00**) + **Perzentil-Bänder je Peer-Gruppe** (Größenklasse × Konsolidierung × Stichtag, ab n≥5 — 97 % der Reports abgedeckt) |

## Datenabdeckung (Snapshot)

**Echter Gesamtbestand im Hub (harvested 2026-06-22):** 4.278 Submissions · 489 Institute ·
2 Module (010000 *und* 020000 — geladen nur 020000) · Stichtage 2025-12-31 (2.690),
2025-06-30 (1.010), 2025-09-30 (314), 2026-03-31 (248), 2025-10-31 (16) · EU/EEA-weit
(DE 518, IT 440, FR 375, ES 277, SE 244, AT 233, PL 202, NL, DK, BE, LU, IE …).
Katalog liegt in `interim/edap_recon/manifest_full.csv`.

**Aktuell geladen (Stand 2026-07-10):** **553 Reports · 1.259.328 platzierbare Facts** ·
445 Institute · 30 Länder · 7 Module (CODIS/FINDIS/REMDIS/IRRBBDIS/MRELTLAC/ESGDIS/GSIIDIS).
Erste **volle Stichtags-Welle 31.12.2025** (434 Reports, `manifest_wave.csv`, latest-wins,
ohne DISDOCS) + der frühere 20 %-Sample-Rest (2025-06-30: 64, 2025-09-30: 34, 2026-03-31: 21).
Nächste Wellen: weitere Stichtage aus `manifest_full.csv` (download → parse → Zweig B → Shards
→ `publish_data_branch.sh`, alles inkrementell).

**Deployment (wichtig):** Die JSON-Daten liegen **nicht** auf `main`, sondern auf dem Orphan-
`data`-Branch und werden via **jsDelivr** ausgeliefert (Fallback raw.githubusercontent). Dort
liegt unter `state/` auch der **Pipeline-Zustand** (`long_form_raw.csv.gz`,
`filing_indicators.csv.gz`, `p3dh_long.parquet`) — zurückholbar mit `scripts/fetch_state.sh`.
`main` trägt nur Code + kleine Referenz-CSVs. Lokal sind das nur noch 358 MB (im Wesentlichen
`raw/`); Legacy-CSV-Viewer braucht ein vorheriges `fetch_state.sh`.

## Pipeline-Artefakte (Reihenfolge)

```
fetch_state.sh                <- data-Branch state/ (long_form + coverage + parquet zurückholen)
harvest_catalog_query.py      -> interim/edap_recon/manifest_full.csv  (VOLLER Katalog, query-API)
harvest_catalog.py            -> interim/edap_recon/manifest_urls.csv  (alt: Scroll, nur ~20 — überholt)
resolve_latest_submissions.py -> interim/edap_recon/manifest_latest.csv (latest-wins)
build_parse_manifest.py       -> interim/edap_recon/manifest_parse.csv (Union, ohne DISDOCS)
plan_delta.py                 -> interim/edap_recon/manifest_todo.csv  (nur noch nicht Verarbeitetes)
download_raw_reports.py       -> raw/*.zip
build_sample_codebook.py      -> codebook/mini_codebook_from_reports.csv (dp-Codes)
extract_template_titles.py    -> codebook/template_titles.csv  (EBA Annotated Table Layout)
build_codebook.py             -> codebook/dpm_codebook.csv     (dp -> Template/Row/Col + Labels + Titel)
fetch_lei_names.py            -> processed/lei_names.csv        (GLEIF)
xbrl_csv_parser.py            -> processed/long_form_raw.csv    (Fakten)
                              -> processed/filing_indicators.csv (Coverage-Matrix, „Fehlt ≠ Null")
build_entity_meta.py          -> processed/entity_meta.csv      (Name/Land/Größe/G-SII aus EDAP)
fetch_fx_rates.py             -> processed/fx_rates.csv          (EZB-Referenzkurse)
check_fact_placement.py       -> interim/placement_report.csv    (GUARD: stiller Fact-Verlust,
                                 Baseline interim/placement_baseline.json, Exit 1 bei Verschlechterung)
fetch_dpm_sources.py          -> codebook/DPM2_v4.2.accdb + dpm_table_layout.zip (opt-in, ~1 GB)
check_reference_data.py       (GUARD: decken FX-Kurse + entity_meta die Fakten ab? harter Exit 1)
geo_names.csv                 -> codebook/geo_names.csv          (ISO-Ländercodes -> Namen, statisch)
check_unit_consistency.py     -> interim/unit_consistency_report.csv (Größenordnungs-Scan + Sperrliste
                                 UNIT_AMBIGUOUS_TEMPLATES, importiert von build_zweig_b.py)
build_zweig_b.py              -> processed/long/p3dh_long.parquet (EINE gejointe Wahrheit, DuckDB;
                                 + open_axis_country aus geo_names.csv, eba_GA:-Codes -> Ländername;
                                 + unit_ambiguous-Flag für Templates mit gemischten Einheiten)
build_framework_bridge.py     -> codebook/framework_bridge.csv   (RF 4.1<->4.2 Zell-Brücke)
build_zweig_a_shards.py       -> processed/zweig_a/data/index.json + codebook.json + reports/<key>.json
                                 (JSON-Shards, allein aus dem Parquet abgeleitet)
publish_data_branch.sh        -> data-Branch: Shards + state/ (long_form.gz, coverage.gz, parquet)
processed/zweig_a/viewer_json.html  (Standard: lädt index/codebook vorab, Reports lazy als Shards)
processed/zweig_a/viewer.html       (Legacy: liest long_form + codebook + lei_names live im Browser)
```

Die ganze Kette läuft auch als GitHub-Action (`.github/workflows/pipeline.yml`):
`workflow_dispatch` mit den Schaltern `harvest` / `full_reparse` / `refresh_codebook`.
Der wöchentliche Cron ist auskommentiert — erst soll ein manueller Lauf sauber durchlaufen.

**Referenzdaten laufen jetzt mit** (Issue #2): `fetch_fx_rates.py` vor jedem Zweig-B-Bau,
`build_entity_meta.py` direkt nach dem Harvest (nur dort liegen die Roh-Antworten), der
Codebook-Rebuild als opt-in **vor** dem Parse — der Parser leitet `cell_row`/`cell_col`
aus dem Codebook ab, ein Rebuild danach käme zu spät; `refresh_codebook` erzwingt deshalb
`--full`. Zwei Guards schützen die Kette: `check_fact_placement.py` (stiller Fact-Verlust,
Baseline-basiert) und `check_reference_data.py` (FX-/entity_meta-Abdeckung, harter Abbruch).

## DPM-Auflösung (Referenz)

```
dp<n> == Variable.VariableID -> VariableVersion -> TableVersionCell (TableVID + CellCode "{K_61.00, rNNNN, cNNNN[, s*]}")
   TableVID + Ordinate -> HeaderVersion.Label   (Zeilen-/Spalten-Label, 100 %)
   Template-Titel       -> EBA Annotated Table Layout TOC (access-parser liest nur 22/148)
```
DB `codebook/DPM2_v4.2.accdb` (755 MB, kumulativ) + Layout-Zip — beide gitignored, URLs in
den jeweiligen Scripts. 4.2-DB packt Textfelder inkonsistent → `dpm_decode` scort Kandidaten.

## Zweig A — Data-driven Viewer

Zwei featuregleiche Vanilla-JS-Seiten, Gabelseite `processed/zweig_a/index.html`:

- **`viewer_json.html` (Standard):** lädt `data/index.json` (Report-Meta + Head-Templates
  KM1/OV1 + meta/names/fx) + `data/codebook.json` vorab (~0,25 MB gzip), holt jeden Report
  lazy als `data/reports/<entityID>__<refPeriod>.json` (~3 KB median). Nativ `JSON.parse`,
  kein CSV-Parser. Skaliert Richtung Voll-Load (Browser lädt nur das Sichtbare).
- **`viewer.html` (Legacy):** lädt die Roh-CSVs komplett und joint/typisiert im Browser —
  unabhängige Gegenprobe.

Die Shards kommen **allein aus dem Zweig-B-Parquet** (`build_zweig_a_shards.py`, deterministisch,
Werte byte-identisch verifiziert) → Viewer und Analytics teilen eine Transformationsstelle.
Bank-Namen jetzt aus EDAP (`entity_meta`, lesbarer als GLEIF-Legalnamen).

Starten (vom **Repo-Root**): `python3 -m http.server 8766` (Config `p3dh-web` mit
`--directory /Users/tobibi/P3dh`) → `/processed/zweig_a/`.

Politur offen: Open-Axis-Member (mehrere Werte je Zelle kollabieren im Gitter, wie im CSV-Viewer).

## Session 2026-08-21 — Benchmark-Standortbestimmung & Roadmap

Keine Code-Änderung, sondern strategische Bestandsaufnahme: **Wo stehen wir bei Benchmarking
und Mehrwert ggü. EDAP?** EDAP ist ein Archiv (ein Bank-ZIP nach dem anderen, kein Quervergleich).
Unser Mehrwert ist, die Population in *eine abfragbare Fläche* zu verwandeln.

**Live & solide:** Peer-Benchmark mit 4 Profilen (KM1-Kennzahlen, Kapital-Headroom, Risikoprofil
OV1, Liquidität), sortier-/filterbar, EUR-normiert (EZB-Kurs), Trend-Sparklines, Vergleichbarkeits-
Caveat. Dazu Zeitreihe je Institut, Vergleich (bis 4 Pins), Zweig B als freie SQL-Fläche.

**Befund — der Benchmark zieht erst aus ~5 % der Templates Werte** (nur 2 Head-Templates):
- KM1 (61.00) in **483/553**, OV1 (60.00.A) in **476/553** Reports — Gerüst greift breit.
- Ungenutzt, obwohl schon in Parquet/Shards: **NPL** CR1 (21.01.D, **413 rep**) + CQ3 (82.00.A,
  401 rep); **ESG** 41.00 (135 rep); **Kreditrisiko** CR5 (25.00, 240 rep) + CR6-IRB (26.00.A,
  93 rep); LIQ1/LIQ2/NSFR (73/74.00); **CCyB-Geo** 67.01.A (279 rep, liegt als `open_axis_dims`).
- Text/Enum-Facts (1,8 %, 27.390) bleiben via `fact_value_raw` erhalten.
- Nur **1 voller Stichtag** (31.12.2025) → Trend/Zeitreihe greift real nur für Institute mit
  ≥2 Stichtagen; Peer-Ranking ist Momentaufnahme.

### Benchmark-Roadmap (Mehrwert/Aufwand, höchster Hebel zuerst)

1. **Benchmark-Profile ausdehnen** — NPL (CR1/CQ3), ESG (41.00), Kreditrisiko-Mix. Daten liegen
   schon vor; nötig sind nur Profil-Definitionen im Viewer + Aufnahme weiterer Templates in
   `benchmark.json` (`HEAD_TEMPLATES` in `build_zweig_a_shards.py`). **Größter Hebel, kleinster
   Aufwand — nächster Schritt, wenn's weitergeht.**
2. **Perzentil-/Quartil-Bänder** im Benchmark → aus Rangliste wird echte Peer-Einordnung
   („Bank X im 78. Perzentil der Peer-Gruppe").
3. **Disclosure-Transparenz-Matrix** (`filing_indicators.csv`, „Fehlt ≠ Null") als eigener Tab —
   *wer meldet was vs. was deklariert wird*, struktureller Alleinstellungspunkt ggü. EDAP.
   ⚗️ **Vom Nutzer als Experiment eingestuft** (explorativ, kein Kern-Deliverable) — niedrige Prio.
4. **Open-Axis-Auflösung** (`eba_GA:NL` → „Niederlande") → Länder-Exposure-Benchmark (CCyB 67.01.A).

**Entscheidung:** Richtung = Benchmark-Substanz vertiefen (1 → 2), Transparenz-Matrix (3) nur als
Experiment, keine Priorität. Heute nichts gebaut — nur dokumentiert.

## Session 2026-08-21 (Teil 2) — Weg von lokaler Datenhaltung

Der Laptop war Zustandsspeicher der Pipeline (1,9 GB). Jetzt ist er nur noch Arbeitskopie:
**lokal 358 MB**, der Zustand liegt in der Cloud, und die Kette läuft auch ohne ihn.

**Zustand auf dem `data`-Branch.** `publish_data_branch.sh` legt zusätzlich `state/` ab
(`long_form_raw.csv.gz` 14 MB, `filing_indicators.csv.gz`, `p3dh_long.parquet` 19 MB);
`fetch_state.sh` holt ihn zurück. Round-Trip byte-identisch verifiziert. Damit ist das
Parquet auch ein öffentlicher Download der Analytik-Schicht.

**Lokal gelöscht (alles wiederbeschaffbar):** DPM-Datenbanken 1,3 GB (nur Build-Zeit —
`dpm_codebook.csv` ist committet; URLs stehen in `build_codebook.py`), `long_form_raw.csv`
275 MB und das Parquet (beide im State). `filing_indicators.csv` ist von `main` genommen
(war ein 5,4-MB-Duplikat, das mit jeder Welle veraltet wäre) → jetzt gitignored.

**Zwei echte Parser-Defekte gefunden und behoben** — beide hätten den CI-Betrieb zerstört:
1. **Datenverlust bei zustandslosem Lauf.** Die Menge der gültigen Quellen kam aus den ZIPs
   *auf der Platte*. Auf einem frischen Runner (nur die neuen ZIPs) hätte der Merge den
   gesamten Altbestand als „überholt" verworfen — 1,26 Mio. Facts. Jetzt kommt sie aus dem
   **Manifest**; nur wirklich überholte Resubmissions fallen raus.
2. **Nicht idempotent.** 35 Einreichungen ohne platzierbare Fakten stehen nur in der
   Coverage-Matrix, nie in der Long-Form → wurden bei *jedem* Lauf neu geparst. Die Coverage
   ist jetzt das maßgebliche Ledger. Inkrementeller Lauf: 6 s statt ~1 min, echter No-Op.

**Neu:** `plan_delta.py` (Download-Liste = Manifest minus Verarbeitetes; aktuell 17 statt
2.073 — die 17 sind tote EDAP-Links). `.github/workflows/pipeline.yml`: restore → plan →
download → parse → Zweig B → Shards → publish, mit **Sanity-Gate** (Publish bricht ab, wenn
der Bestand schrumpft) und `concurrency`-Guard gegen parallele Force-Pushes. Vorerst nur
manuell auslösbar; der Cron liegt auskommentiert bereit.

**Tests wiederbelebt:** `pytest` + `requests` fehlten in `requirements.txt` (Downloader
importiert `requests` — lief nur zufällig). Suite 8 → **11 Tests**, alle grün; die drei neuen
decken die beiden Defekte ab und wurden **gegen die alte Logik gegengeprüft** (schlagen dort fehl).

**Noch offen:** Der Harvest (Playwright/Power-BI) ist im Workflow bewusst opt-in — der
fragilste Teil der Kette; ohne ihn verarbeitet der Cron nur das committete Manifest.
`raw/` (253 MB, 2.073 ZIPs) bleibt lokal: EDAP-Links sterben (17 belegt), der Actions-Cache
taugt nicht als Archiv. Für echte Auslagerung wäre Object Storage (R2/B2) nötig.

## Session 2026-08-26 (Teil 2) — Placement-Guard

Konsumenten-Integration der Brücke geprüft — **und dabei die Prämisse widerlegt:**
Zweig A nutzt `datapoint_code` kein einziges Mal (Shards + Viewer joinen über
`(template_id, cell_row, cell_col)`), auch die Zweig-B-Beispiel-Queries sind
zell-basiert. Die Zeitreihen laufen über den 4.1→4.2-Wechsel bereits sauber durch
(an DekaBank / OV1 `60.00.A r0290 c0030` über 4 Stichtage verifiziert). Es gab
also keinen kaputten Join zu reparieren.

**Das echte Risiko sitzt eine Stufe früher** und war bis jetzt unsichtbar:
`cell_row`/`cell_col` entstehen erst durch einen dp-Lookup gegen
`dpm_codebook.csv`; unbekannter dp → keine Koordinate → der Fakt wird in den
Shards (`WHERE cell_row <> ''`) stillschweigend weggefiltert.

- **Neu `scripts/check_fact_placement.py`** — klassifiziert jeden Fakt in
  `placed` / `open_axis` (erwartet, kein Alarm) / `unplaceable`, prüft unbekannte
  dp-Codes und die rebound-Zellen der Brücke. Baseline-Logik wie das Sanity-Gate:
  Abbruch nur bei **Verschlechterung** (`interim/placement_baseline.json`,
  `--update-baseline` hebt bewusst an).
- **Befund: 5.344 Fakten gehen heute schon still verloren** (636 dem Codebook
  unbekannte dp-Codes), konzentriert auf ESG-Templates (`47.00.A` 4.700). Der
  Guard macht es sichtbar, behebt es nicht → 🔴 Backlog-Eintrag (Codebook/ESG-
  Taxonomie). Vor jeder ESG-Auswertung zu klären.
- **Workflow:** `Placement guard` zwischen Sanity-Gate und Zweig B; `Rebuild
  framework bridge` nach Zweig B (die Brücke stand bisher gar nicht im Workflow
  und wäre still veraltet); Commit-Schritt nimmt die Brücke mit und hängt nicht
  mehr am `harvest`-Schalter.
- Tests 17 → **31**, alle grün; Regressions-Probe gegen echte Daten (injizierter
  unbekannter dp) rötet den Guard wie erwartet.

## Session 2026-08-26 (Teil 1) — Framework-Brücke + Idee-A-Herabstufung

- **Phase 3b erste Ausbaustufe:** `scripts/build_framework_bridge.py` →
  `codebook/framework_bridge.csv` (937 Zellen in beiden RF-Versionen beobachtet:
  916 stable / 19 rebound / 2 ambiguous=Codebook-Duplikat). Frequenz-kontrolliert
  ist die Template-Ebene stabil — die scheinbaren 131 „nur-4.1"-Templates waren
  Jahres- vs. Quartalsumfang. Tests: `tests/test_framework_bridge.py` (Suite 11 → 17).
- **Idee A („Transparenz-Score") herabgestuft** nach Nutzer-Einwand: Template-
  Fußabdruck misst Regulierungskategorie (CRR Art. 433a–c) + Anwendbarkeit, nicht
  Offenherzigkeit. Rest-Wert: Kategorie-Karte fürs Schichten, Art.-432-Anomalien
  als Experiment, echte Offenheit nur via PDF-NLP (G). `phase4_analysis_ideas.md`
  komplett auf Stand 26.08. neu geschrieben (N=445-Realität, neue Reihenfolge).
- Remote-Session kann den Pipeline-State jetzt ohne HTTP ziehen: `git show
  origin/data:state/…` (fetch_state.sh geht über raw.githubusercontent → Egress-Block).

## Heute erledigt (2026-06-22)

- Handy-Branch `claude/status-check-9vherq` gemergt (Doku + `resolve_latest_submissions.py`).
- Resubmission-Filter in den Parser eingebunden → 16 statt 20 Reports.
- **BOM-Bug gefixt** (`utf-8-sig` für FilingIndicators **und** k-Dateien) → die 2 vormals
  leeren ZIPs liefern jetzt Daten; gleiche Wurzel wie der Filing-Indicator-Bug.
- **Coverage-Matrix** `processed/filing_indicators.csv` (266 reported / 612 declared
  not-reported) als „Fehlt ≠ Null"-Grundlage, sauber getrennt von den Fakten.
- **Bank-Namen** via GLEIF in den Viewer.
- **Template-Titel** 82/82 via EBA Annotated Table Layout.
- **Voll-Katalog-Harvester** gebaut (`harvest_catalog_query.py`): EDAP ist Azure Blob (kein
  public list) + kein offizielles Bulk/API → Katalog via Power-BI-`query`-Endpoint (Window
  hochgesetzt, ein Request) → 4.278 Submissions / 489 Institute. Damit echte Abdeckung = ~0,4 %.
- **Loop-Konzept** („loop engineering") besprochen, vorerst **geparkt**: passt später als
  Cron-Delta-Loop (Hub wächst bis Mitte 2026), aber erst wenn die Skalen-Pipeline (Zweig B) steht.

## Offene Punkte → GitHub-Issues

Seit 2026-08-26 werden offene Punkte als **Issues** geführt, nicht mehr als Liste hier:
https://github.com/Tobias-Run/P3DH/issues — `BACKLOG.md` behält nur noch die
abgeschlossenen Befunde als Entscheidungs-Historie.

| # | Thema | wo ausführbar |
|---|---|---|
| [#2](https://github.com/Tobias-Run/P3DH/issues/2) | 🔴 Referenzdaten veralten still (fx_rates/entity_meta/codebook nicht im Workflow) | CI / lokal mit Netz |
| [#3](https://github.com/Tobias-Run/P3DH/issues/3) | 🔴 GAR/BTAR unplatzierbar — 636 dp-Codes fehlen im Codebook | CI / lokal mit Netz |
| [#4](https://github.com/Tobias-Run/P3DH/issues/4) | Benchmark vertiefen: weitere Templates + Perzentil-Bänder (Roadmap 1+2) | überall |
| [#5](https://github.com/Tobias-Run/P3DH/issues/5) | Open-Axis-Member auflösen → Länder-Exposure-Benchmark (CCyB1) | überall |
| [#6](https://github.com/Tobias-Run/P3DH/issues/6) | Harvest-Diff scharf schalten | CI / lokal mit Netz |
| [#7](https://github.com/Tobias-Run/P3DH/issues/7) | Nächste Stichtags-Welle laden (hängt an #2) | CI / lokal mit Netz |
| [#8](https://github.com/Tobias-Run/P3DH/issues/8) | Wöchentlichen Cron scharf schalten | überall |

**„Laptop-only" gilt nicht mehr.** Der Workflow läuft auf `ubuntu-latest` mit vollem
Netzzugang (120 min, Playwright wird im Harvest-Schritt installiert) — auch der
755-MB-DPM-Download ist CI-fähig. Die tatsächliche Grenze ist **„Remote-Chat-Session
ohne Egress"**, nicht der Rechner.

**Weiterhin offen, aber ohne eigenes Issue:**
- **Unit-Handling:** %-Zellen als Dezimal (0.47 = 47 %); Long-Form trägt keine
  Pro-Zelle-Einheit — `data_type` aus dem DPM ist inzwischen im Codebook, Nutzung im
  Viewer geklärt. Bei Bedarf als Issue nachziehen.
- **Voll-Load-Strategie:** 4.278 Submissions ⇒ Millionen Zeilen. Zweig B (Parquet/DuckDB)
  steht inzwischen, Zweig A lädt Report-Shards lazy — die ursprüngliche Skalen-Sorge ist
  damit weitgehend adressiert; offen bleibt nur, in welchen Wellen geladen wird (#7).

## Hardware

M1/8 GB: `access-parser` liest die 755-MB-DB tabellenweise; Playwright headless sequentiell;
HTTP-Download max. 4 Worker.

## Repository

- GitHub: https://github.com/Tobias-Run/P3DH (Solo → Pushes direkt in `main`)
- `.gitignore`: `.accdb`, `.xlsx`, `.zip`, Roh-ZIPs, große Processed-CSVs
- SSH-Key `~/.ssh/github_key`; Push: `GIT_SSH_COMMAND="ssh -i ~/.ssh/github_key" git push origin main`
