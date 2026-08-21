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

**✅ Folgeschritt erledigt (2026-07-05):** Long-Form über alle 123 CODIS-Reports
der 20-%-Stichprobe neu erzeugt — 53.833 Records tragen `open_axis_dims`.
Optional weiter offen: `open_axis_dims` gegen DPM-Open-Axis-Member auflösen
(z. B. `eba_GA:NL` → „Niederlande") für lesbare offene Achsen im Viewer.

## ✅ ERLEDIGT: Delta-Pipeline + Automatisierung (2026-08-21)

- **Parser ist inkrementell** (`source_file`-Ledger, `--full` erzwingt Neuaufbau).
  Zwei dabei gefundene Defekte behoben: (a) die Menge der gültigen Quellen kam aus
  den ZIPs *auf der Platte* — auf einem zustandslosen Runner hätte der Merge den
  gesamten Altbestand verworfen; sie kommt jetzt aus dem Manifest. (b) Einreichungen
  ohne platzierbare Fakten stehen nur in der Coverage-Matrix und wurden deshalb bei
  jedem Lauf neu geparst; die Coverage ist jetzt das maßgebliche Ledger.
  Regressionstests: `IncrementalMergeTest` (gegen die alte Logik gegengeprüft).
- **Download-Delta** via `scripts/plan_delta.py` → `manifest_todo.csv` (Manifest minus
  bereits Verarbeitetes), statt sich auf den Dateibestand in `raw/` zu verlassen.
- **Automatischer Trigger** da: `.github/workflows/pipeline.yml` (Cron wöchentlich +
  `workflow_dispatch`), inklusive Sanity-Gate gegen schrumpfenden Bestand.

Offen bleibt nur: **Harvest-Diff.** `harvest_catalog_query.py` schreibt den Katalog
komplett neu, ohne Log, was seit dem letzten Harvest dazukam (`harvest_log.csv`/
`manifest_delta.csv` sind angelegt, aber der Vergleich ist nicht scharf geschaltet).
Im Workflow ist der Harvest deshalb bewusst **opt-in** — er ist der fragilste Teil
der Kette (headless Power-BI-Embed).
