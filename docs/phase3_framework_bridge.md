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
  der nächste Ausbau — braucht die Access-DBs (laptop-lokal, gitignored).
