# Phase 3b — Framework-Brücke 4.1 ↔ 4.2

**Stand:** 2026-08-26. Erste Ausbaustufe: beobachtungsbasierte Zell-Brücke aus dem
Zweig-B-Parquet. Artefakt: `codebook/framework_bridge.csv`
(Builder: `scripts/build_framework_bridge.py`, Tests: `tests/test_framework_bridge.py`).

## Warum es die Brücke braucht

Ab Stichtag 2026-03-31 melden Institute unter Reporting Framework **4.2**
(Modul-Codes wechseln mit: `020000` → `020100`, `010000` → `010100`). Für
Zeitreihen über den Wechsel hinweg stellt sich die Frage, was vergleichbar bleibt.

## Befunde (Datenbasis: 553 Reports, davon 22 unter 4.2)

**1. Template-Ebene: praktisch stabil.** Der scheinbar große Unterschied
(131 Templates „nur 4.1") ist ein **Frequenz-Artefakt**: die 4.2-Seite besteht
bisher nur aus Q1-Quartalsmeldungen (kleinster Offenlegungsumfang), die 4.1-Seite
enthält die Jahresmeldungen 31.12. Frequenz-kontrolliert (gleiche Institute,
Quartal 2025-09-30 vs. Quartal 2026-03-31): 21 Templates gemeinsam, nur
66.01.A / 67.02 „nur 4.1" und 02.00 „nur 4.2" — bei N=5 Instituten schwach belegt.

**2. Zell-Ebene: 98 % stabil, aber die Ausnahmen treffen Kern-Kennzahlen.**
Von 937 Zellen, die unter beiden Versionen beobachtet wurden:

| Status | Zellen | Bedeutung |
|---|---|---|
| `stable` | 916 | gleicher dp-Code — direkter Join funktioniert |
| `rebound` | 19 | **dp-Code geändert** — naiver dp-Join verliert die Zeitreihe still |
| `ambiguous` | 2 | 2 dp je Zelle, aber identisch in beiden Versionen (Codebook-Duplikat, kein Versionsproblem) |

Die 19 Umbindungen clustern fachlich plausibel um CRR3-Baustellen:

- **KM1 (61.00)** r0260 „EU 14d Leverage ratio buffer requirement" — alle 5 Spalten;
  r0190 „EU 11a Overall capital requirements"
- **OV1 (60.00.A)** r0290 „Alternative Internal Models" (Marktrisiko/FRTB)
- **63.01.B–E** CVA-Zeile, „Other RWEA", Verbriefungs-Zeile, Total
- **71.00 (LR2)** SFT-Zeilen

Gerade **KM1 ist das Rückgrat des Benchmarks** — ohne Brücke bricht die
Leverage-Puffer-Zeitreihe beim Versionswechsel unbemerkt ab.

## Konsequenz für Konsumenten (Zweig B / Viewer / Analysen)

- Zeitreihen **nie** allein über `datapoint_code` joinen, sondern über
  `(template_id, cell_row, cell_col)` — oder dp-Codes vorher per
  `framework_bridge.csv` (Status `rebound`) auf eine Version normalisieren.
- Zell-Layout (row/col) ist der stabile Anker; die Labels bestätigen die
  fachliche Identität der Zelle.

## Grenzen / Pflege

- **Beobachtungsbasiert, nicht taxonomie-vollständig:** Die Brücke kennt nur
  Zellen, die real in beiden Versionen gemeldet wurden (bisher 22 4.2-Reports,
  nur Quartalsumfang). Mit jeder 4.2-Welle (v. a. Jahresmeldung 31.12.2026)
  wächst sie — Skript einfach neu laufen lassen.
- Zellen „nur 4.1"/„nur 4.2" stehen bewusst **nicht** drin: Abwesenheit ist bei
  Offenlegungsdaten kein Beleg für Taxonomie-Änderung (Frequenz/Anwendbarkeit).
- Taxonomie-seitige Vervollständigung (DPM 4.1- gegen 4.2-Release diffen) wäre
  der nächste Ausbau — braucht die Access-DBs (gitignored, per Download; läuft in
  CI oder lokal mit Netz, siehe `build_codebook.py`).

---

## Guard: `scripts/check_fact_placement.py`

Die Brücke hat bei der Konsumenten-Prüfung eine unerwartete Erkenntnis geliefert:
**es gibt keinen kaputten dp-Join zu reparieren.** Zweig A verwendet
`datapoint_code` kein einziges Mal (Shards und Viewer joinen über
`(template_id, cell_row, cell_col)`), und auch alle Beispiel-Queries in
`docs/zweig_b_queries.md` sind zell-basiert. Die Zeitreihen laufen über den
Versionswechsel bereits sauber durch — verifiziert an DekaBank / OV1
`60.00.A r0290 c0030` über alle vier Stichtage.

**Das echte Risiko liegt eine Stufe früher.** `cell_row`/`cell_col` entstehen erst
durch einen dp-Lookup im Parser (`xbrl_csv_parser.py`) gegen `dpm_codebook.csv`.
Kennt das Codebook einen dp-Code nicht, bleiben die Koordinaten leer — und der Fakt
wird in `build_zweig_a_shards.py` (`WHERE cell_row <> ''`) **stillschweigend
weggefiltert**. Die Zahl der Reports stimmt weiterhin, nur die Fakten fehlen.

### Was der Guard prüft

Jeder Fakt fällt in genau eine Klasse:

| Klasse | Bedeutung | Alarm? |
|---|---|---|
| `placed` | Koordinate vorhanden | nein |
| `open_axis` | keine Koordinate, aber `open_axis_dims` gesetzt — offene Tabellen haben im DPM keine statische (row, col) | **nein**, erwartet |
| `unplaceable` | weder Koordinate noch Dimension | **ja** — stiller Verlust |

Dazu: dp-Codes, die `dpm_codebook.csv` nicht kennt, und `rebound`-Zellen der
Brücke, deren dp-Code im Codebook fehlt (die verlören beim Versionswechsel ihre
Koordinaten).

### Ist-Stand (553 Reports)

| Kategorie | fw 4.1 | fw 4.2 |
|---|---|---|
| platziert | 1.251.461 | 7.867 |
| offene Achse (erwartet) | 281.184 | 0 |
| **unplatzierbar** | **5.344** | **0** |

636 dp-Codes sind dem Codebook unbekannt. Die Verluste konzentrieren sich auf
ESG-Templates: `47.00.A` (4.700), `00.03` (197), `49.01` (154), `47.00.B` (136),
`96.00.B` (127).

### Baseline statt Nullforderung

Diese 5.344 sind Realität — „muss null sein" wäre sofort rot und damit wertlos.
Stattdessen dieselbe Philosophie wie das Sanity-Gate (bricht bei schrumpfendem
Bestand ab): `interim/placement_baseline.json` hält den akzeptierten Ist-Stand,
der Guard bricht ab (Exit 1), sobald es **schlechter** wird — mehr unplatzierbare
Fakten, ein *neuer* unbekannter dp-Code, oder eine rebound-Zelle ohne Codebook-dp.

```bash
python3 scripts/check_fact_placement.py                    # prüfen (CI)
python3 scripts/check_fact_placement.py --update-baseline  # Zuwachs bewusst akzeptieren
```

Im Workflow läuft er zwischen Sanity-Gate und Zweig-B-Build; der Brücken-Rebuild
folgt direkt nach Zweig B, damit `framework_bridge.csv` nicht still veraltet.
