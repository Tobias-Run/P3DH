# Backlog

## 🔴 BUG: Filing-Indicators immer `False` (Korrektheit, „Fehlt ≠ Null" kaputt)

`xbrl_csv_parser.py` setzt `template_reported` für **alle** Records auf `False`.
Zwei unabhängige Ursachen, beide bestätigt am Sample-Report (real: 34×true/21×false):

1. **BOM:** `_extract_filing_indicators()` liest `FilingIndicators.csv` mit
   `.decode("utf-8")` statt `utf-8-sig`. Die erste Spalte heißt dadurch intern
   `﻿reported`, `row.get("reported")` liefert `None` → alles `False`.
   (`_extract_metadata()` macht es mit `utf-8-sig` bereits korrekt — Inkonsistenz.)
2. **Key-Mismatch:** Parser leitet aus `k_61.00.csv` die ID `61.00` ab, der
   Indicator-Dict-Key ist aber `K_61.00`. `.get("61.00")` trifft nie → `False`.

**Wirkung:** Die in den Instructions als *zwingend* markierte Unterscheidung
„nicht offengelegt" vs. „echter Nullwert" fehlt komplett. Blockiert die
Disclosure-/Transparenz-Analyse (Tier 1, höchster Wert — siehe
`docs/phase4_analysis_ideas.md`).

**Fix-Hinweis:** klein (utf-8-sig + Key-Normalisierung auf `K_<NN.NN>`), aber
erst zusammen mit dem Repopulieren des `raw/`-Layers anwenden, sonst entstehen
Code und committetes `long_form_raw.csv` inkonsistent (nur 1 ZIP lokal vorhanden).

## Delta-Pipeline: inkrementelle Verarbeitung (offen)

Aktuell nur teilweise umgesetzt (siehe `scripts/resolve_latest_submissions.py` für
die Resubmission-Policy). Der eigentliche Kern fehlt noch:

- **Kein Diff zwischen Harvest-Läufen.** `harvest_catalog.py` schreibt bei jedem
  Lauf den kompletten Katalog neu, ohne Vergleich/Log, was seit dem letzten
  Harvest neu hinzugekommen ist.
- **Parser macht Full-Rerun statt Append.** `xbrl_csv_parser.py::parse_all_reports()`
  parst bei jedem Lauf alle `.zip` in `raw/` neu und überschreibt
  `processed/long_form_raw.csv` komplett. Sollte stattdessen nur neue/geänderte
  Reports parsen und an die bestehende Long-Form-Tabelle anhängen.
- **Kein automatischer Trigger.** Harvest läuft nur manuell, kein Cron o.ä.
  (nice-to-have, kein Muss).

Bei der aktuellen Datenmenge (~16–20 Reports) unkritisch (Full-Rerun dauert
Sekunden), wird aber relevant, sobald die Anzahl Reports/Institute deutlich wächst.
