# EBA Pillar 3 Data Hub (P3DH) — Datenanalyse-Pipeline

Reproduzierbare Pipeline: öffentlich publizierte Pillar-3-Daten aus dem EBA Pillar 3
Data Hub (P3DH) auf dem European Data Access Portal (EDAP) beziehen, aus XBRL-CSV in
analysefertige Form überführen und Data-Science darauf ermöglichen.

## Zwei Ausgabe-Zweige, ein gemeinsamer Kern

Der teure, fehleranfällige Teil (DPM-Join, Einheiten-Semantik, `filing-indicators`,
„fehlt ≠ Null") existiert **nur einmal** und erzeugt eine Long-Form-Wahrheit. Daraus
werden zwei Zweige abgeleitet:

```
/raw  ──►  Parser + DPM-Join (Codebook)  ──►  Long-Form "Wahrheit" (/processed/long)
                                                   │
                          ┌────────────────────────┴────────────────────────┐
                          ▼                                                  ▼
              ZWEIG A: menschenlesbar                          ZWEIG B: maschinenlesbar
              /reports/readable                                /processed/long (Parquet)
              - Template-Layout rekonstruiert                  - Tidy/Long, partitioniert
              - Labels/Einheiten ausgeschrieben                - LEI/Entity-Keys, Flags
              - 1 File je Institut/Stichtag (XLSX/HTML)        - EUR-normalisiert (+ Orig.)
              - qualitative PDF-Narrative                      - DuckDB, Framework-Brücke
```

Zweig A wird **immer aus** Long-Form gerendert, nie parallel geparst.
**Pilot-Priorität: Zweig A zuerst** (visuelle Validierung von Parsing + DPM-Join an
einem Report, bevor skaliert wird).

## Projektstruktur

| Ordner | Inhalt |
|---|---|
| `raw/` | Roh-XBRL-CSV-Pakete + PDFs, **immutable**, nie überschreiben |
| `interim/` | Zwischenstände (geparst, noch nicht modelliert) |
| `processed/long/` | Long-Form Parquet (Zweig B, die Quelle) |
| `codebook/` | DPM-Mapping Code → Label/Einheit |
| `reports/readable/` | Zweig A: menschenlesbare Reports (abgeleitet) |
| `notebooks/` | Data-Science-Explorationen (Phase 4) |
| `scripts/` | Downloader, Parser, Renderer |
| `docs/` | Decision-Memos, User Guides, Referenzartefakte |

## Phasen

- **Phase 0** — Scoping & Zugangsklärung → `docs/phase0_decision_memo.md`
- **Phase 1** — Ingestion (Downloader + Manifest)
- **Phase 2** — Parsing & DPM-Join → Codebook + Long-Form
- **Phase 3** — Modellierung (Tidy/Long, Entity-Layer, QA)
- **Phase 4** — Explorationen (Benchmarking, Zeitreihen, ESG, NLP)

## Arbeitsprinzipien

1. Reproduzierbarkeit: Roh-Layer immutable, jede Transformation skriptiert.
2. Annahmen offenlegen (im Code/README), nicht bei Kleinigkeiten nachfragen.
3. „Fehlt" ≠ „Null" durchgängig erhalten (`filing-indicators`).
4. Vergleichbarkeitsfallen (Rechnungslegung, Konsolidierung, nationale Optionen) als
   Caveat in jeder Analyse benennen.
