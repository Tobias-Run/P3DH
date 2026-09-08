# Projektstatus

**Stand: 2026-09-08** · Bestand aus Pipeline-Lauf #6 (2026-09-07)

Diese Datei beschreibt, *wo das Projekt steht*. Offene Arbeit wird als
[GitHub-Issue](https://github.com/Tobias-Run/P3DH/issues) geführt, abgeschlossene
Befunde als Entscheidungshistorie in `BACKLOG.md`. Die Sitzungsprotokolle, die
früher hier standen, liegen in der Git-Historie dieser Datei.

## Bestand

| | |
|---|---|
| Reports | **882** (Institut × Konsolidierungskreis × Stichtag) |
| Fakten | **2.295.224** |
| Institute | **474** im Bestand · 476 im Katalog mit XBRL-CSV-Einreichung |
| Länder | 30 |
| Stichtage | 2025-06-30 · 2025-09-30 · 2025-10-31 · 2025-12-31 · 2026-03-31 |
| Meldewerk | RF 4.1: 2.231.690 Fakten · RF 4.2: 63.534 |
| Nicht platzierbar | **35** Fakten (0,0015 %) — ohne jeden Achsenwert |

**Die Abdeckung ist vollständig, nicht stichprobenhaft.** Der Katalog zählt 4.278
Einreichungen und 489 Institute, aber 2.539 davon sind Neueinreichungen und
Korrekturen derselben Meldung („latest wins", Arbeitsprinzip 5). Von den 489
Instituten reichen 476 XBRL-CSV ein — **alle 476 sind im Bestand**. Die übrigen 13
veröffentlichen ausschließlich qualitative PDF-Pakete (`*DISDOCS`), die bewusst
außerhalb des Scopes liegen ([#38](https://github.com/Tobias-Run/P3DH/issues/38)).

Die Differenz von 2 zwischen Katalog (476) und Bestand (474) deckt sich der
Größenordnung nach mit [#28](https://github.com/Tobias-Run/P3DH/issues/28) — Reports,
die keine einzige platzierbare Zelle enthalten und deshalb gar nicht erst
erscheinen; belegt ist der Zusammenhang nicht.

## Phasen

| Phase | Status | Stand |
|---|---|---|
| 0 — Scoping & Zugang | ✅ | `docs/phase0_decision_memo.md` |
| 1 — Ingestion | ✅ | Voll-Katalog-Harvester (Power-BI-`query`), wellenweiser Download, Harvest-Diff mit Klassifikation und Schrumpf-Gate |
| 2 — Parsing & DPM-Join | ✅ | 9.775/9.775 Datenpunkte aufgelöst, `codebook/dpm_codebook.csv` (14.221 Zeilen), Template-Titel via EBA-Layout |
| 2.5 — Offene Achsen | ✅ | Dimensionswert wird zur Zeile (CCyB1 → ISO-Land); ohne Achsenwert bleibt die Zeile leer statt geraten |
| 3 — Multi-Modul | ✅ | CODIS · ESGDIS · FINDIS · GSIIDIS · IRRBBDIS · MRELTLACDIS · REMDIS; nur `*DISDOCS` (PDF) ausgenommen |
| 3b — Brücke RF 4.1↔4.2 | ✅ | beobachtungsbasiert: 5.277 Zellen, davon 5.091 stabil, 63 umgebunden, 123 mehrdeutig ([#70](https://github.com/Tobias-Run/P3DH/issues/70), alle in LIQ2) |
| 4A — Zweig A (Viewer) | ✅ | JSON-Viewer als Standard, Shards lazy, Voll-Load-tauglich |
| 4B — Zweig B (Parquet) | ✅ | `p3dh_long.parquet`, self-contained, speist Zweig A |
| 4 — Explorationen | 🟡 | sieben Benchmark-Profile, Perzentilbänder, Plausibilitätsprofil, Footprint · Clustering und Transparenz-Matrix offen |

## Qualitätszusagen im Ausführungspfad

Keine davon ist eine Behauptung im README — jede bricht die Pipeline ab oder
erzeugt ein Produkt:

| Prüfung | Wogegen | Stand Lauf #6 |
|---|---|---|
| `check_branch_parity.py` | Viewer-Zahlen ≠ Long-Form, auch in der **Einheit** | 2.295.189 Zellen · 41.902 Währungspaare · grün |
| `check_fact_placement.py` | stiller Fact-Verlust durch unbekannte dp-Codes | unbekannte dp-Codes: **0** |
| `check_reference_data.py` | FX/Metadaten decken die Fakten nicht ab | 42/42 Kurse · 474/474 Institute · 0 monetäre Fakten ohne EUR-Wert |
| Sanity-Gate | schrumpfender Bestand durch Merge-Fehler | meldet in jedem Modus, bricht inkrementell ab |
| `determinism.py` | nicht-reproduzierbare Ausgaben | im Ausführungspfad, nicht nur im Test |
| Codebook-Fingerabdruck | Codebook-Wechsel wirkt nur auf neue Fakten | entscheidet vor dem Download ([#57](https://github.com/Tobias-Run/P3DH/issues/57)) |

Testsuite: **352** Tests. 24 davon überspringen sich in CI, weil sie die
Zweig-A-Artefakte brauchen — bekannt und erfasst als
[#69](https://github.com/Tobias-Run/P3DH/issues/69).

## Auswertungen als Produkt

Diese Schritte brechen bewusst **nicht** ab: ihre Befunde betreffen die
Einreichungen, nicht unsere Pipeline.

- **Plausibilität** ([#17](https://github.com/Tobias-Run/P3DH/issues/17)): 5.957 Befunde in 326 von 882 Reports (2.868 hoch · 2.204 mittel · 885 niedrig)
- **Footprint** ([#12](https://github.com/Tobias-Run/P3DH/issues/12)): 377 Reports, 271 Institute; Median-Domestizität 82,3 %, 149 Institute über 90 % heimatzentriert

## Betrieb

- **Pipeline:** `.github/workflows/pipeline.yml`, manuell (`workflow_dispatch`), zustandslos — `raw/` startet leer, der Bestand kommt vom `data`-Branch. Laufzeit #6: 10:45 inkl. vollem Reparse. Wöchentlicher Cron liegt auskommentiert bereit ([#8](https://github.com/Tobias-Run/P3DH/issues/8)).
- **Tests:** `.github/workflows/tests.yml`, automatisch bei jedem Push, ~15 s.
- **Auslieferung:** Orphan-Branch `data` → jsDelivr. **Der Branch wird force-gepusht und trägt genau einen Commit** — er hat keine Historie, jeder Lauf ersetzt den vorigen Stand vollständig.
- **Entwicklung:** Feature-Branch → PR → Merge nach `main`.

## Hardware (lokale Entwicklung)

M1 / 8 GB: `access-parser` liest die 755-MB-DPM-DB tabellenweise; Playwright
headless sequentiell; HTTP-Download mit maximal 4 Workern.
