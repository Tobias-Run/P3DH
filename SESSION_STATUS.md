# Session Status — 2026-06-22

> Diese Datei ist die laufend aktualisierte Wahrheit zum Projektstatus.
> Am Ende jeder Session auf den tatsächlichen Stand bringen — nicht verwaisen lassen.

## Phasen-Übersicht

| Phase | Status | Stand |
|---|---|---|
| 0 — Scoping & Zugang | ✅ | Decision Memo, Format-Analyse, EDAP-Zugang, Git/GitHub |
| 1 — Ingestion | ✅ | 20 ZIPs in `raw/`; Resubmission-Policy „latest-wins" eingebunden (Download **und** Parser konsumieren `manifest_latest.csv`) → 16 aktuelle Submissions |
| 2 — Parsing & DPM-Join | ✅ | `long_form_raw.csv` (**17.883 Records**); DPM-Blocker gelöst (access-parser + DPM v4.2); 3206/3206 Datapoints aufgelöst, 84 % mit Zellkoordinate; voll gelabeltes `dpm_codebook.csv` (Row/Col-Labels 100 %, **Template-Titel 82/82**) |
| 2.5 — Refinement | ✅ | Ursache der ~16 % ohne Zellkoordinate geklärt: **offene Achse** (67/66/64/29 u. a. tragen typisierte Dimensionsspalte). Parser erfasst sie jetzt als `open_axis_dims` statt sie zu verwerfen; Regressionstests in `tests/`. **TODO Laptop:** `long_form_raw.csv` über alle 16 Reports neu erzeugen |
| 3 — RF 4.1↔4.2-Mapping | ⬜ | Brücke für Zeitreihen (beide Versionen im Datensatz) |
| 4A — Zweig A | ✅ | **Data-driven Viewer** `processed/zweig_a/viewer.html` (Bank-Namen + volle Titel) |
| 4B — Zweig B | ⬜ | maschinenlesbare Analytics (Parquet/DuckDB) |
| 4 — Explorationen | 🟡 geplant | Analyse-Ideen datengeerdet → `docs/phase4_analysis_ideas.md` |

## Datenabdeckung (Snapshot)

8 Institute · 16 aktuelle Submissions (nach Resubmission-Dedup; 20 ZIPs roh) ·
4 Stichtage (2025-06-30 … 2026-03-31) · DE/SE/AT/MT/EE/DK/LV · 11 CON / 5 IND ·
EUR/SEK/DKK · Framework 4.1 (94 %) **und** 4.2 (6 %) gemischt · 88 Templates ·
4 Institute mit ≥2 Stichtagen (1 mit allen 4) → kurze Zeitreihen möglich.

Institute (LEI → Name via GLEIF, `processed/lei_names.csv`): DEKABANK DEUTSCHE
GIROZENTRALE, HYPO TIROL BANK AG, Aktiebolaget Svensk Exportkredit, SPARKASSE
(HOLDINGS) MALTA, NOBA BANK GROUP, AS INBANK, RØNDE SPAREKASSE, RIETUMU BANKA.

## Pipeline-Artefakte (Reihenfolge)

```
harvest_catalog.py            -> interim/edap_recon/manifest_urls.csv  (Roh-Katalog, Audit)
resolve_latest_submissions.py -> interim/edap_recon/manifest_latest.csv (latest-wins)
download_raw_reports.py       -> raw/*.zip
build_sample_codebook.py      -> codebook/mini_codebook_from_reports.csv (dp-Codes)
extract_template_titles.py    -> codebook/template_titles.csv  (EBA Annotated Table Layout)
build_codebook.py             -> codebook/dpm_codebook.csv     (dp -> Template/Row/Col + Labels + Titel)
fetch_lei_names.py            -> processed/lei_names.csv        (GLEIF)
xbrl_csv_parser.py            -> processed/long_form_raw.csv    (Fakten)
                              -> processed/filing_indicators.csv (Coverage-Matrix, „Fehlt ≠ Null")
processed/zweig_a/viewer.html  (liest long_form + codebook + lei_names live im Browser)
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

`processed/zweig_a/viewer.html`: statische Vanilla-JS-Seite, lädt die Roh-CSVs zur Laufzeit
(`cache:'no-store'`) und rendert die Template-Gitter clientseitig. **Bank-Name** prominent
(LEI klein), Report-Sidebar + Template-Filter, **voller offizieller Template-Titel**
(z.B. „EU KM1 - Key metrics template"), Werte mit Zeilen-/Spalten-Labels platziert.
Starten (vom **Repo-Root**): `python3 -m http.server 8766` → `/processed/zweig_a/viewer.html`
(oder `.claude/launch.json`, Config `zweig-a`).

Politur offen: Unit-Handling (% -Zellen als Dezimal, keine Pro-Zelle-Einheit).

## Heute erledigt (2026-06-22)

- Handy-Branch `claude/status-check-9vherq` gemergt (Doku + `resolve_latest_submissions.py`).
- Resubmission-Filter in den Parser eingebunden → 16 statt 20 Reports.
- **BOM-Bug gefixt** (`utf-8-sig` für FilingIndicators **und** k-Dateien) → die 2 vormals
  leeren ZIPs liefern jetzt Daten; gleiche Wurzel wie der Filing-Indicator-Bug.
- **Coverage-Matrix** `processed/filing_indicators.csv` (266 reported / 612 declared
  not-reported) als „Fehlt ≠ Null"-Grundlage, sauber getrennt von den Fakten.
- **Bank-Namen** via GLEIF in den Viewer.
- **Template-Titel** 82/82 via EBA Annotated Table Layout.

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

## Hardware

M1/8 GB: `access-parser` liest die 755-MB-DB tabellenweise; Playwright headless sequentiell;
HTTP-Download max. 4 Worker.

## Repository

- GitHub: https://github.com/Tobias-Run/P3DH (Solo → Pushes direkt in `main`)
- `.gitignore`: `.accdb`, `.xlsx`, `.zip`, Roh-ZIPs, große Processed-CSVs
- SSH-Key `~/.ssh/github_key`; Push: `GIT_SSH_COMMAND="ssh -i ~/.ssh/github_key" git push origin main`
