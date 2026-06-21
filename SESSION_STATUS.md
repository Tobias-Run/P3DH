# Session Status — 2026-06-22

> Diese Datei ist die laufend aktualisierte Wahrheit zum Projektstatus.
> Am Ende jeder Session auf den tatsächlichen Stand bringen — nicht verwaisen lassen.

## Phasen-Übersicht

| Phase | Status | Stand |
|---|---|---|
| 0 — Scoping & Zugang | ✅ | Decision Memo, Format-Analyse, EDAP-Zugang, Git/GitHub |
| 1 — Ingestion | ✅ Kern, 🟡 Politur | 20 ZIPs in `raw/`; Resubmission-Policy „latest-wins" (`resolve_latest_submissions.py`) **eingebunden** → Download/Parse konsumieren `manifest_latest.csv` |
| 2 — Parsing & DPM-Join | ✅ | `long_form_raw.csv` (19.048 Records); **DPM-Blocker gelöst** (access-parser + DPM v4.2), 3206/3206 Datapoints aufgelöst, 82 % mit Zellkoordinate, voll gelabeltes `dpm_codebook.csv` |
| 2.5 — Refinement | 🔧 | restliche 18 % (Sheet-/Z-Achse + Sub-Letter-Versatz bei 64/66/67/29) |
| 3 — RF 4.1↔4.2-Mapping | ⬜ | Brücke für Zeitreihen (beide Versionen im Datensatz) |
| 4A — Zweig A | ✅ | **Data-driven Viewer** `processed/zweig_a/viewer.html` |
| 4B — Zweig B | ⬜ | maschinenlesbare Analytics (Parquet/DuckDB) |
| 4 — Explorationen | 🟡 geplant | Analyse-Ideen datengeerdet → `docs/phase4_analysis_ideas.md` |

## Datenabdeckung (Snapshot)

8 Institute · 16 aktuelle Submissions (nach Resubmission-Dedup; 20 ZIPs roh) ·
4 Stichtage (2025-06-30 … 2026-03-31) · DE/SE/AT/MT/EE/DK/LV · 11 CON / 5 IND ·
EUR/SEK/DKK · Framework 4.1 (94 %) **und** 4.2 (6 %) gemischt · 88 Templates ·
4 Institute mit ≥2 Stichtagen (1 mit allen 4) → kurze Zeitreihen möglich.

## DPM-Auflösung (Referenz)

```
dp<n>  ==  Variable.VariableID
       ->  VariableVersion        (VariableID -> VariableVID)
       ->  TableVersionCell        (VariableVID -> TableVID + CellCode "{Template, rNNNN, cNNNN[, s*]}")
   TableVID -> TableVersion.Name           (Template-Titel)
   TableVID + Ordinate -> HeaderVersion.Label  (Zeilen-/Spalten-Label)
```
DB: `codebook/DPM2_v4.2.accdb` (755 MB, kumulativ, gitignored — URL in `build_codebook.py`).
4.2-DB packt Textfelder pro Record inkonsistent → `dpm_decode` scort Kandidaten nach
ASCII-Anteil; lange Memo-Felder (Template-`Name`) z.T. unlesbar (22 Titel sauber, Labels 100 %).

## Zweig A — Data-driven Viewer

`processed/zweig_a/viewer.html`: einzelne statische Vanilla-JS-Seite, **lädt die Roh-CSVs
zur Laufzeit** (`long_form_raw.csv` + `dpm_codebook.csv`) und rendert die Template-Gitter
clientseitig — Report-Sidebar + Template-Filter, keine hartcodierten Daten. KM1 (61.00)
verifiziert: volle Zeilen-Labels, Perioden-Spalten (a=T … e=T-4), Werte korrekt platziert.
Starten (vom **Repo-Root**, damit beide CSVs erreichbar): `python3 -m http.server 8766`
→ `/processed/zweig_a/viewer.html` (oder `.claude/launch.json`, Config `zweig-a`).

Politur offen: Template-Titel nur ~22/148 (Memo-Overflow; saubere Quelle = EBA „DPM table
layout"/Glossary-XLSX); Unit-Handling (% -Zellen als Dezimal, keine Pro-Zelle-Einheit).

## Offene Punkte / Backlog (siehe `BACKLOG.md`)

1. **Filing-Indicator / „Fehlt ≠ Null".** `_extract_filing_indicators` liest `utf-8` statt
   `utf-8-sig` → BOM-Bug. **Verifiziert latent:** betrifft nur die 2 ZIPs mit BOM-Format
   `﻿reported,templateID`, und genau die liefern 0 Datapoints; die 18 Daten-ZIPs haben
   `templateID,reported` (kein BOM) und lesen korrekt. Committetes `reported=True` ist
   damit korrekt (k-Dateien existieren nur für gemeldete Templates). **Echte Lücke:** der
   Parser emittiert die als `false` deklarierten Templates gar nicht → für „Fehlt ≠ Null"
   müssen die FilingIndicators selbst als Records raus.
2. **2 von 20 ZIPs = 0 Datapoints** (anderes internes Format) — noch unerklärt.
3. **Resubmission-Dedup** umgesetzt (`manifest_latest.csv`), aber `long_form` noch aus allen
   20 ZIPs gebaut → nach Repopulation auf die 16 aktuellen neu parsen.
4. **Delta-Pipeline:** Harvest schreibt Katalog komplett neu (kein Diff); Parser macht
   Full-Rerun statt Append. Unkritisch bei ~20 Reports, relevant beim Skalieren.

## Hardware

M1/8 GB: `access-parser` liest die 755-MB-DB tabellenweise (schwere Tabellen voll im RAM);
Playwright headless sequentiell; HTTP-Download max. 4 Worker.

## Repository

- GitHub: https://github.com/Tobias-Run/P3DH (Solo → Pushes direkt in `main`)
- `.gitignore` schließt große Dateien aus (`.accdb` 4.0+4.2, Roh-ZIPs, große Processed-CSVs)
- SSH-Key `~/.ssh/github_key`
