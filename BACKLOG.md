# Backlog

> **Offene Punkte werden ab 2026-08-26 als GitHub-Issues geführt:**
> https://github.com/Tobias-Run/P3DH/issues
> Diese Datei behält die *abgeschlossenen* Befunde als Entscheidungs-Historie
> (warum etwas so gebaut ist) — sie ist kein Aufgaben-Tracker mehr.

## ✅ ERLEDIGT: GAR/BTAR-Fakten unplatzierbar (Issue #3, geschlossen)

Vom Placement-Guard (`scripts/check_fact_placement.py`) sichtbar gemacht: 636
dp-Codes kannte das Codebook nicht, 5.344 Fakten wurden dadurch in
`build_zweig_a_shards.py` (`WHERE cell_row <> ''`) weggefiltert — ohne Fehler,
ohne Warnung. Schwerpunkt `47.00.A` (GAR I, 4.700 von 6.197) und `96.00.B`
(TLAC2b Creditor ranking, 127 von 132).

**Die vermutete Ursache war falsch.** Der Verdacht lag auf einer Lücke der
ESGDIS-Templates in der DPM-Access-DB. Tatsächlich war das Codebook schlicht
**veraltet**: der Refresh-Schritt im Workflow ist opt-in und lief beim Voll-Load
nicht mit. Der Neubau im Zuge von #56 löste 9.775 von 9.775 dp-Codes auf (vorher
9.068) und deckte damit 14.283 zusätzliche Fakten in `47.00.A`/`49.01`/`96.00.A`
und `96.00.B` ab.

Stand nach Pipeline-Lauf #6: **dem Codebook unbekannte dp-Codes: 0.** Es
verbleiben 35 unplatzierbare Fakten (0,0015 %) — Fakten ohne jeden Achsenwert,
bei denen die Zeile bewusst leer bleibt, statt eine zu erfinden (Arbeitsprinzip 3).

Genau dieser Fehlermodus — ein Codebook-Wechsel, der still nur auf neue Fakten
wirkt — ist anschließend als #57 abgesichert worden: der Fingerabdruck des
Codebooks liegt neben dem Bestand und erzwingt den vollen Reparse.

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
- **Automatisierung** da: `.github/workflows/pipeline.yml` (`workflow_dispatch`,
  inklusive Sanity-Gate gegen schrumpfenden Bestand). Der wöchentliche Cron ist
  auskommentiert vorbereitet — scharf schalten, sobald ein manueller Lauf durch ist.

**Harvest-Diff** (Issue #6) ist seit 2026-09 geschlossen: `scripts/harvest_delta.py`
klassifiziert jede Änderung (neu · resubmission · überholt · zurückgezogen),
`harvest_log.csv` und `manifest_delta.csv` werden committet — vorher entstand die
append-only-Historie auf einem Wegwerf-Runner und begann bei jedem Lauf neu —,
und die Lauf-Zusammenfassung liest den Diff. Dazu ein Schrumpf-Gate **vor** dem
Überschreiben von `manifest_full.csv`: danach wäre die Vergleichsgrundlage weg.
Im Workflow bleibt der Harvest bewusst **opt-in** — er ist der fragilste Teil der
Kette (headless Power-BI-Embed).
