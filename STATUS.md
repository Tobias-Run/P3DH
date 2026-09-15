# Projektstatus

**Stand: 2026-09-15** · Bestand aus Pipeline-Lauf #12 (2026-09-14, sha `5333e3c`)

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
Instituten reichen 476 XBRL-CSV ein — **474 davon sind im Bestand**. Die übrigen 13
veröffentlichen ausschließlich qualitative PDF-Pakete (`*DISDOCS`), die bewusst
außerhalb des Scopes liegen ([#38](https://github.com/Tobias-Run/P3DH/issues/38)).

Die Differenz von 2 zwischen Katalog (476) und Bestand (474) ist seit
[#7](https://github.com/Tobias-Run/P3DH/issues/7) **belegt statt vermutet** — und
sie besteht aus zwei verschiedenen Dingen:

- ein Institut ist [#28](https://github.com/Tobias-Run/P3DH/issues/28): die
  Einreichung wurde geladen, geparst und deklariert Templates in der
  Coverage-Matrix, trägt aber keine einzige platzierbare Zelle;
- beim anderen sind **alle** Katalogzeilen tote EDAP-Links (per HEAD geprüft:
  404 — eine Katalogzeile ohne publizierte Datei).

`processed/catalogue_coverage.csv` führt das je Report mit. Auf Report-Ebene sind
**882 von 925** geladen (95,4 %); die 43 Fehlstellen sind 40 PDF-Institute, 1
#28-Fall und 2 tote Links — **kein einziger offener, ladbarer Report**.

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

| Prüfung | Wogegen | Stand Lauf #12 |
|---|---|---|
| `check_branch_parity.py` | Viewer-Zahlen ≠ Long-Form, auch in der **Einheit** | 2.295.189 Zellen · 41.902 Währungspaare · grün |
| `check_fact_placement.py` | stiller Fact-Verlust durch unbekannte dp-Codes | unbekannte dp-Codes: **0** |
| `check_reference_data.py` | FX/Metadaten decken die Fakten nicht ab | 42/42 Kurse · 474/474 Institute · 0 monetäre Fakten ohne EUR-Wert |
| Sanity-Gate | schrumpfender Bestand durch Merge-Fehler | meldet in jedem Modus, bricht inkrementell ab |
| `determinism.py` | nicht-reproduzierbare Ausgaben | im Ausführungspfad, nicht nur im Test |
| Codebook-Fingerabdruck | Codebook-Wechsel wirkt nur auf neue Fakten | entscheidet vor dem Download ([#57](https://github.com/Tobias-Run/P3DH/issues/57)) |

Testsuite: **941** Tests. 24 davon überspringen sich in CI, weil sie die
Zweig-A-Artefakte brauchen — bekannt und erfasst als
[#69](https://github.com/Tobias-Run/P3DH/issues/69).

## Auswertungen als Produkt

Diese Schritte brechen bewusst **nicht** ab: ihre Befunde betreffen die
Einreichungen, nicht unsere Pipeline.

- **Plausibilität** ([#17](https://github.com/Tobias-Run/P3DH/issues/17), [#36](https://github.com/Tobias-Run/P3DH/issues/36)): 10.942 Befunde in 474 von 882 Reports (3.867 hoch · 6.235 mittel · 840 niedrig) aus vier Regelfamilien — 5.816 Zellausreißer, 214 Vergütungskorridor, 4.870 Zeitsprünge, 42 Strukturbrüche. Der Zeitvergleich misst das Institut an sich selbst und braucht dafür weder Peers noch Währungsannahme; 8 der 21 Report-Paare mit Strukturbruch treffen unabhängig einen `skaliert`-Befund aus [#83](https://github.com/Tobias-Run/P3DH/issues/83).
- **Footprint** ([#12](https://github.com/Tobias-Run/P3DH/issues/12)): 377 Reports, 271 Institute; Median-Domestizität 82,3 %, 149 Institute über 90 % heimatzentriert
- **Risikoträger-Anteil** ([#40](https://github.com/Tobias-Run/P3DH/issues/40)): REM1 gegen die Wikidata-Belegschaft, 83 Reports. Roh misst die Quote die **Grösse** (r² = 0,755 gegen log10(Belegschaft)); ausgewiesen wird deshalb der Rest gegen die Grössenerwartung — p10 0,48 · Median 1,03 · p90 1,87. Dass die Korrektur greift, zeigt der Perimetertest: CON/IND laufen roh um Faktor 3,7 auseinander, nach Abzug der Grösse um 1,04.
- **Negativmenge** ([#42](https://github.com/Tobias-Run/P3DH/issues/42)): von 2.863 beaufsichtigten Einheiten bleibt **ein** signifikantes Institut ohne jede Spur. Elf weitere melden unter anderer Kennung als der EZB-LEI (`namensgleicher_melder`) — Verdacht ausgewiesen, Abdeckung nicht behauptet. SI-Abdeckung 100 % in allen grossen Ländern ausser Österreich (88 %).
- **Katalogabdeckung** ([#7](https://github.com/Tobias-Run/P3DH/issues/7)): 882 von 925 Katalog-Reports geladen; die 43 Fehlstellen sind nach Ursache getrennt, davon **null** offen und ladbar.

## Betrieb

- **Pipeline:** `.github/workflows/pipeline.yml`, manuell (`workflow_dispatch`), zustandslos — `raw/` startet leer, der Bestand kommt vom `data`-Branch. Die Reihenfolge der 34 Schritte ist seit [#8](https://github.com/Tobias-Run/P3DH/issues/8) als Graph geprüft (`check_pipeline_order.py`, in `tests.yml`). Der wöchentliche Cron liegt weiter auskommentiert bereit: seit Lauf #12 sind acht Schritte dazugekommen, die noch nie in CI gelaufen sind — ein Zeitplan auf ungetesteter Kette erzeugt rote Läufe statt Daten.
- **Tests:** `.github/workflows/tests.yml`, automatisch bei jedem Push, ~15 s.
- **Auslieferung:** Orphan-Branch `data` → jsDelivr. **Der Branch wird force-gepusht und trägt genau einen Commit** — er hat keine Historie, jeder Lauf ersetzt den vorigen Stand vollständig.
- **Entwicklung:** Feature-Branch → PR → Merge nach `main`.

## Hardware (lokale Entwicklung)

M1 / 8 GB: `access-parser` liest die 755-MB-DPM-DB tabellenweise; Playwright
headless sequentiell; HTTP-Download mit maximal 4 Workern.
