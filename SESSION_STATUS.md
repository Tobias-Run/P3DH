# Session Status — 2026-06-21

> Diese Datei ist die laufend aktualisierte Wahrheit zum Projektstatus.
> Wird am Ende jeder Session auf den tatsächlichen Stand gebracht — nicht
> verwaisen lassen wie die Vorgängerversion.

## Phasen-Übersicht

| Phase | Status | Stand |
|---|---|---|
| 0 — Scoping & Zugangsklärung | ✅ Abgeschlossen | Decision Memo, Format-Analyse, EDAP-Zugang geklärt |
| 1 — Ingestion | 🟡 Teilweise | Katalog geharvested (21 Submissions); Resubmission-Policy (latest-wins) umgesetzt → 17 aktuelle; nur 1 von 17 Roh-ZIPs tatsächlich in `raw/` persistiert |
| 2 — Parsing & DPM-Join | 🟡 Interim | Parser liefert 19.048 Long-Form-Records aus 20 Reports; **alle Datapoint-Labels sind `[TODO: DPM lookup]`** — echter DPM-Join fehlt noch |
| 3 — Modellierung | ⬜ Nicht begonnen | — |
| 4 — Explorationen | ⬜ Nicht begonnen | — |

## Zuletzt erledigt

- Resubmission-Policy "latest wins": `scripts/resolve_latest_submissions.py`
  filtert den Roh-Katalog (`manifest_urls.csv`, 21 Zeilen) auf eine Zeile je
  (Institut, Modul, Stichtag) → `manifest_latest.csv` (17 Zeilen). Roh-Katalog
  bleibt als Audit-Trail erhalten.
- `download_raw_reports.py` konsumiert jetzt `manifest_latest.csv` statt der
  ungefilterten Liste.
- `BACKLOG.md` angelegt für offene Architekturpunkte.

## Größte offene Blocker

1. **DPM Data Dictionary nicht extrahiert.** Access-DB (`codebook/`) muss noch
   per mdb-tools/pyodbc ausgelesen werden, um die 3.206 `dp<n>`-Codes im
   Mini-Codebook auf echte Labels/Einheiten zu mappen. Ohne das bleiben die
   Long-Form-Daten kryptisch (Phase 2 nicht wirklich abgeschlossen).
2. **Roh-Layer unvollständig.** Nur 1 von 17 aktuellen Submissions liegt
   physisch in `raw/` — der Rest wurde nie heruntergeladen oder ist
   gitignored verlorengegangen. `download_raw_reports.py` muss erneut laufen.
3. **Siehe `BACKLOG.md`:** Parser macht Full-Rerun statt inkrementellem
   Append; kein Diff zwischen Harvest-Läufen.

## Nächste konkrete Aktion

```bash
python3 scripts/download_raw_reports.py     # restliche 16 Roh-ZIPs laden
# danach: DPM-Dictionary-Extraktion angehen (Blocker 1)
```

## Hardware Constraint

M1/8GB: Playwright läuft headless sequentiell, HTTP-Download max. 4 Worker.

## Repository

- GitHub: https://github.com/Tobias-Run/P3DH
- `.gitignore` schließt große Dateien aus (DPM-Datenbank, Roh-ZIPs, große Processed-CSVs)
