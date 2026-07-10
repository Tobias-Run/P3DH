# Session Status — 2026-07-10

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
| 3b — RF 4.1↔4.2-Mapping | ⬜ | Brücke für Zeitreihen (beide Versionen im Datensatz) |
| 4A — Zweig A | ✅ | **JSON-Viewer = Standard** (`viewer_json.html`): **Slim-`index.json`** (nur Report-Meta, ~0,01 MB gzip) + `codebook.json` vorab; **`benchmark.json`** (KM1/OV1-Head, ~0,14 MB) **lazy** für Benchmark/Zeitreihe; jeder Report lazy als `data/reports/<key>.json` (~3 KB). Featuregleich (typisierte Skalen, EUR, Filter, Benchmark-Profile, Zeitreihen, Vergleich, Dark, Deep-Links). **Voll-Load-tauglich**: Index-Projektion ~0,2 MB gzip @ 4.278 Reports; Shards inkrementell geschrieben. **CSV-Viewer** (`viewer.html`) = Legacy; Gabelseite `index.html` |
| 4B — Zweig B | ✅ | `build_zweig_b.py` → `processed/long/p3dh_long.parquet` (self-contained, DuckDB; +`fact_value_raw`/`fx_rate`), Beispiele in `docs/zweig_b_queries.md`. **Speist auch Zweig A**: `build_zweig_a_shards.py` leitet die JSON-Shards allein aus dem Parquet ab → eine Transformationsstelle, kein Drift (Werte byte-identisch verifiziert) |
| 4 — Explorationen | 🟡 geplant | Analyse-Ideen datengeerdet → `docs/phase4_analysis_ideas.md` |

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
`data`-Branch und werden via **jsDelivr** ausgeliefert (Fallback raw.githubusercontent). `main`
trägt nur Code + kleine CSVs; `long_form_raw.csv` (275 MB) und das Parquet sind gitignored
(regenerierbar). Legacy-CSV-Viewer nur noch lokal (braucht die große CSV).

## Pipeline-Artefakte (Reihenfolge)

```
harvest_catalog_query.py      -> interim/edap_recon/manifest_full.csv  (VOLLER Katalog, query-API)
harvest_catalog.py            -> interim/edap_recon/manifest_urls.csv  (alt: Scroll, nur ~20 — überholt)
resolve_latest_submissions.py -> interim/edap_recon/manifest_latest.csv (latest-wins)
download_raw_reports.py       -> raw/*.zip
build_sample_codebook.py      -> codebook/mini_codebook_from_reports.csv (dp-Codes)
extract_template_titles.py    -> codebook/template_titles.csv  (EBA Annotated Table Layout)
build_codebook.py             -> codebook/dpm_codebook.csv     (dp -> Template/Row/Col + Labels + Titel)
fetch_lei_names.py            -> processed/lei_names.csv        (GLEIF)
xbrl_csv_parser.py            -> processed/long_form_raw.csv    (Fakten)
                              -> processed/filing_indicators.csv (Coverage-Matrix, „Fehlt ≠ Null")
build_entity_meta.py          -> processed/entity_meta.csv      (Name/Land/Größe/G-SII aus EDAP)
fetch_fx_rates.py             -> processed/fx_rates.csv          (EZB-Referenzkurse)
build_zweig_b.py              -> processed/long/p3dh_long.parquet (EINE gejointe Wahrheit, DuckDB)
build_zweig_a_shards.py       -> processed/zweig_a/data/index.json + codebook.json + reports/<key>.json
                                 (JSON-Shards, allein aus dem Parquet abgeleitet)
processed/zweig_a/viewer_json.html  (Standard: lädt index/codebook vorab, Reports lazy als Shards)
processed/zweig_a/viewer.html       (Legacy: liest long_form + codebook + lei_names live im Browser)
```

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

## Offene Punkte / Backlog (siehe `BACKLOG.md`)

1. ✅ **Phase 2.5 geklärt:** Die ~16 % ohne Zellkoordinate sind **offene-Achsen-Templates**
   (typisierte Dimensionsspalte `RIO`/`qADP`/`qABI`/`qEEA`), kein Join-Bug. Parser erfasst
   die Dimension jetzt als `open_axis_dims`. **Folgeschritt:** `long_form_raw.csv` auf dem
   Laptop über alle 16 Reports neu erzeugen; optional Phase 3: Dimensionswerte gegen
   DPM-Open-Axis-Member auflösen.
2. **Unit-Handling:** % -Zellen als Dezimal (0.47 = 47 %); Long-Form trägt keine Pro-Zelle-Einheit.
3. **Delta-Pipeline:** Harvest schreibt Katalog komplett neu (kein Diff); Parser Full-Rerun
   statt Append. Unkritisch bei ~20 Reports.
4. **Erste Auswertung** auf der Coverage-Matrix (Transparenz-/Disclosure-Score je Institut,
   Tier 1 aus `docs/phase4_analysis_ideas.md`) — netz-unabhängig machbar.
5. **STRATEGISCHE ENTSCHEIDUNG (offen):** Voll-Load 4.278 Submissions ⇒ Millionen Long-Form-
   Zeilen ⇒ **Zweig B (DuckDB/Parquet) wird Pflicht**, Browser-Viewer skaliert nicht (muss pro
   Report lazy-laden). Alternative: erst repräsentative Stichprobe (z. B. 1 Stichtag × alle
   Länder) als Skalentest. Download via `manifest_full.csv` → `download_raw_reports.py`.

## Hardware

M1/8 GB: `access-parser` liest die 755-MB-DB tabellenweise; Playwright headless sequentiell;
HTTP-Download max. 4 Worker.

## Repository

- GitHub: https://github.com/Tobias-Run/P3DH (Solo → Pushes direkt in `main`)
- `.gitignore`: `.accdb`, `.xlsx`, `.zip`, Roh-ZIPs, große Processed-CSVs
- SSH-Key `~/.ssh/github_key`; Push: `GIT_SSH_COMMAND="ssh -i ~/.ssh/github_key" git push origin main`
