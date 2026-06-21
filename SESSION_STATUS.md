# Session Status — 2026-06-21

> Diese Datei ist die laufend aktualisierte Wahrheit zum Projektstatus.
> Wird am Ende jeder Session auf den tatsächlichen Stand gebracht — nicht
> verwaisen lassen wie die Vorgängerversion.

## Phasen-Übersicht

| Phase | Status | Stand |
|---|---|---|
| 0 — Scoping & Zugangsklärung | ✅ Abgeschlossen | Decision Memo, Format-Analyse, EDAP-Zugang geklärt |
| 1 — Ingestion | 🟡 Teilweise | Katalog geharvested (21 Submissions); Resubmission-Policy (latest-wins) umgesetzt → 17 aktuelle; nur 1 von 17 Roh-ZIPs tatsächlich in `raw/` persistiert |
| 2 — Parsing & DPM-Join | 🟡 Interim | Parser liefert 19.048 Long-Form-Records aus 20 Reports; **alle Datapoint-Labels sind `[TODO: DPM lookup]`** — echter DPM-Join fehlt noch; zudem 🔴 Filing-Indicator-Bug (s.u.) |
| 3 — Modellierung | ⬜ Nicht begonnen | — |
| 4 — Explorationen | 🟡 Geplant | Analyse-Ideen datengeerdet dokumentiert → `docs/phase4_analysis_ideas.md` (Tier 1 ohne DPM machbar, Tier 2 blockiert) |

## Datenabdeckung (Snapshot)

8 Institute · 16 aktuelle Submissions · 4 Stichtage (2025-06-30 … 2026-03-31) ·
Länder DE/SE/AT/MT/EE/DK/LV · 11 CON / 5 IND · Währungen EUR/SEK/DKK ·
Framework 4.1 (94 %) **und** 4.2 (6 %) gemischt · 88 Templates. **4 Institute mit
≥2 Stichtagen** (1 davon mit allen 4) → kurze Zeitreihen möglich.

## Zuletzt erledigt

- Phase-4-Analyse-Ideen brainstormed + datengeerdet dokumentiert →
  `docs/phase4_analysis_ideas.md` (Tier 1 = ohne DPM machbar: Transparenz-Profil,
  4.1→4.2-Struktur-Diff, Währungs-/Präzisions-QA; Tier 2 = DPM-abhängig).
- 🔴 **Filing-Indicator-Bug entdeckt** (s. Blocker 4 + BACKLOG): `template_reported`
  ist für alle 19.048 Records fälschlich `False` (BOM- + Key-Mismatch).
- DPM-Alternativquellen recherchiert (Websuche): XBRL-Taxonomie-Label-Linkbases
  (im `report.json` referenziert), „Annotated Templates" (Excel), RF-4.1-Technical-
  Package — keine als verifiziert kleinere Alternative bestätigt (EBA-Hosts geblockt).
- Resubmission-Policy "latest wins" (`scripts/resolve_latest_submissions.py`),
  `download_raw_reports.py` konsumiert jetzt `manifest_latest.csv`.

## 🔴 Umgebungs-Blocker: Netzwerk

`eba.europa.eu` / `errp.eba.europa.eu` / `xbrl.org` etc. sind in dieser Remote-
Session geblockt (`host_not_allowed`). **Betrifft auch den Roh-ZIP-Download** und
die DPM-/Taxonomie-Beschaffung. Aufhebbar nur durch Anpassung der Netzwerk-Policy
der Umgebung (durch den User, greift erst in neuer Session).

## Größte offene Blocker

1. **DPM Data Dictionary nicht extrahiert.** Access-DB (`codebook/`) muss noch
   per mdb-tools/pyodbc ausgelesen werden, um die 3.206 `dp<n>`-Codes auf echte
   Labels/Einheiten zu mappen. Long-Form bleibt sonst kryptisch.
2. **Roh-Layer unvollständig.** Nur 1 von 16 Submissions physisch in `raw/`.
   `download_raw_reports.py` muss erneut laufen — **braucht Netzwerk** (s.o.).
3. **Filing-Indicator-Bug.** `template_reported` immer `False` → „Fehlt ≠ Null"
   kaputt. Kleiner Fix, aber mit Roh-Layer-Repopulation bündeln (BACKLOG).
4. **Siehe `BACKLOG.md`:** Parser-Full-Rerun statt Append; kein Harvest-Diff.

## Nächste konkrete Aktion

- **Sobald Netzwerk frei:** `python3 scripts/download_raw_reports.py` (16 ZIPs),
  dann DPM-Dictionary-Extraktion (Blocker 1) + Filing-Indicator-Fix gebündelt.
- **Netz-unabhängig jetzt machbar:** Filing-Indicator-Fix im Parser-Code;
  Tier-1-Analysen vorbereiten (`docs/phase4_analysis_ideas.md`).

## Hardware Constraint

M1/8GB: Playwright läuft headless sequentiell, HTTP-Download max. 4 Worker.

## Repository

- GitHub: https://github.com/Tobias-Run/P3DH
- `.gitignore` schließt große Dateien aus (DPM-Datenbank, Roh-ZIPs, große Processed-CSVs)
