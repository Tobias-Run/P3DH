# Backlog

> **Offene Punkte werden ab 2026-08-26 als GitHub-Issues geführt:**
> https://github.com/Tobias-Run/P3DH/issues
> Diese Datei behält die *abgeschlossenen* Befunde als Entscheidungs-Historie
> (warum etwas so gebaut ist) — sie ist kein Aufgaben-Tracker mehr.

## 🔴 OFFEN → Issue #3: GAR/BTAR-Fakten unplatzierbar (636 dp-Codes fehlen)

Vom Placement-Guard (`scripts/check_fact_placement.py`) sichtbar gemacht — der
Guard **verhindert nur die Verschlechterung, er behebt den Befund nicht.**

`cell_row`/`cell_col` entstehen erst durch einen dp-Lookup im Parser gegen
`codebook/dpm_codebook.csv`. **636 dp-Codes kennt das Codebook nicht**; die
betroffenen Fakten haben weder Koordinate noch offene-Achsen-Dimension und werden
in `build_zweig_a_shards.py` (`WHERE cell_row <> ''`) weggefiltert — ohne Fehler,
ohne Warnung. Betroffen sind 5.344 Fakten:

| Template | Inhalt | verlorene Fakten |
|---|---|---|
| `47.00.A` | GAR (I) | 4.700 von 6.197 (76 %) |
| `00.03` | Narrative ESGDIS | 197 |
| `49.01` | BTAR | 154 |
| `47.00.B` | GAR (II) | 136 |
| `96.00.B` | TLAC2b Creditor ranking | 127 von 132 (96 %) |

**Abgrenzung (Korrektur einer früheren, zu breiten Formulierung):** Betroffen ist
**nur die GAR/BTAR-Kennzahl**, nicht ESG insgesamt. Das ESG-Template der
Benchmark-Roadmap, **`41.00` (Klima-Transitionsrisiko), ist sauber** — 97.249
Fakten aus 135 Reports, null Verluste. Ebenso NPL (`21.01.D`, `82.00.A`),
Kreditrisiko (`25.00`, `26.00.A`), Liquidität (`73/74.00`), KM1, OV1.
Roadmap-Punkt 1 ist also **nicht** blockiert.

**Vermutete Ursache:** `build_codebook.py` zieht die Taxonomie aus der DPM-
Access-DB; die ESGDIS-Templates sind dort offenbar nicht oder nur teilweise
abgedeckt. Zu prüfen: fehlt eine Tabelle/ein Release in der 4.2-DB, oder braucht
ESG einen eigenen Layout-/Taxonomie-Pfad?

Nach einem Codebook-Fix: `python3 scripts/check_fact_placement.py --update-baseline`
(die Baseline sinkt dann — der Guard akzeptiert Verbesserungen ohnehin still).

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
