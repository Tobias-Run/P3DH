# Backlog

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
