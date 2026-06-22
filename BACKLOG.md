# Backlog

## ✅ ERLEDIGT: Filing-Indicators immer `False` („Fehlt ≠ Null")

Behoben (utf-8-sig + Key-Normalisierung auf Basis-ID ohne `K_`-Präfix). Der
Parser schreibt jetzt zusätzlich `processed/filing_indicators.csv` (Coverage-
Matrix). Regressionstest dagegen: `tests/test_xbrl_csv_parser.py`
(`test_filing_indicators_not_all_false`, `..._key_normalized_and_values`).

## ✅ ERLEDIGT: Phase 2.5 — fehlende Zell-Koordinaten = offene Achse

~16 % der Records hatten kein `cell_row`/`cell_col`, zu 100 % in den Templates
mit **offener Achse** (67.01 CCyB1 geografisch, 66.02 CC2, 64.0x LI2/LI3,
29.0x CR9/CR10; auch open-axis-Zellen in 04.00/26.00). Diese k-Dateien tragen
eine dritte, typisierte Dimensionsspalte (`RIO`=Land, `qADP`/`qABI`/`qEEA`=
Freitext/Enumeration). Für offene Tabellen gibt es im DPM **keine statische
(row, col)** — die Zeile entsteht erst zur Einreichung über den Dimensionswert.

Es war also **kein Join-Bug**, sondern Datenverlust: der Parser las nur
`datapoint`/`factValue` und verwarf die Dimensionsspalte (→ bei CCyB1 ging das
Land jeder Position verloren). Fix: neues Feld `open_axis_dims` erfasst alle
Spalten jenseits von `datapoint`/`factValue` als `col=value;…`. Am Sample-Report
verifiziert: 370/370 koordinatenlose Records sind jetzt über `open_axis_dims`
identifiziert, 0 bleiben ohne Identität. Regressionstest:
`test_open_axis_dimension_captured`, `test_open_axis_rows_not_collapsed`.

**Offen / Folgeschritt:** `processed/long_form_raw.csv` muss mit allen 16 Reports
auf dem Laptop **neu erzeugt** werden, damit die neue Spalte `open_axis_dims`
und die geretteten Dimensionen einfließen (Remote-Session hat nur 1 Sample-ZIP,
deshalb hier bewusst nicht überschrieben). Optional Phase 3: `open_axis_dims`
gegen DPM-Open-Axis-Member auflösen (z. B. `eba_GA:NL` → „Niederlande").

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
