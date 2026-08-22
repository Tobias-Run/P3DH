# EBA Pillar 3 Data Hub (P3DH) — Datenanalyse-Pipeline

Reproduzierbare Pipeline: öffentlich publizierte Pillar-3-Daten aus dem EBA Pillar 3
Data Hub (P3DH) auf dem European Data Access Portal (EDAP) beziehen, aus XBRL-CSV in
analysefertige Form überführen und Data-Science darauf ermöglichen.

> **Aktueller Projektstatus:** siehe `SESSION_STATUS.md` — wird laufend aktuell gehalten.
> `P3DH agent instructions.txt` war nur das initiale Briefing zu Projektstart und wird
> seitdem nicht mehr fortgeschrieben; für den heutigen Stand nicht verlässlich.

## 🔗 Live-Viewer (im Browser, ohne Installation)

**Öffentlich live:** **https://tobias-run.github.io/P3DH/** — kein Klonen/Server nötig.

Der **Zweig-A-Viewer** rekonstruiert die Bank-Templates (KM1, OV1, CCR1 …) mit vollen
Zeilen-/Spalten-Labels direkt im Browser und bietet **Peer-Benchmark, Zeitreihen und
Vergleich** über die Institute. Aktuell geladen: **553 Reports · 1,26 Mio. Fakten · 445
Institute · 30 Länder** (u. a. der volle Stichtag 31.12.2025); Voll-Katalog = 489 Institute /
4.278 Einreichungen, wellenweise nachladbar.

- **Landing:** `index.html` · **Viewer (Standard):** `processed/zweig_a/viewer_json.html`
- **Wie es lädt:** Der JSON-Viewer holt einen schlanken `index.json` vorab und jeden Report
  **erst beim Öffnen** als per-Report-JSON-Shard (nativ `JSON.parse`, kein CSV-Parser im
  Browser). So skaliert er Richtung Voll-Load. Die Shards werden **aus dem Zweig-B-Parquet
  abgeleitet** (eine Transformationsstelle) und über den Orphan-`data`-Branch via **jsDelivr**
  ausgeliefert (Fallback: `raw.githubusercontent.com`).
- **Gabelseite** `processed/zweig_a/index.html`: JSON-Viewer (Standard) vs. CSV-Viewer (Legacy,
  nur lokal — braucht die 275-MB-`long_form_raw.csv`).
- **Lokal:** `python3 -m http.server 8766` im Repo-Root → `http://localhost:8766/`

## ⚠ Disclaimer / Datenquellen

Unabhängiges, **nicht-kommerzielles Forschungs-/Bildungsprojekt**, **nicht** mit EBA oder
GLEIF verbunden. Alle externen Daten sind **öffentlich** und werden ausschließlich zu
**wissenschaftlichen/Bildungszwecken** genutzt (Fair Use / Forschung). Quellen: EBA Pillar 3
Data Hub (© EBA), EBA DPM 2.0, GLEIF (LEI-Namen). Bereitstellung „as is", ohne Gewähr —
Zahlen stets gegen die offizielle EBA-Quelle prüfen; keine Anlage-/Rechtsberatung.
Volltext: **`DISCLAIMER.md`**.

## Zwei Ausgabe-Zweige, ein gemeinsamer Kern

Der teure, fehleranfällige Teil (DPM-Join, Einheiten-Semantik, `filing-indicators`,
„fehlt ≠ Null") existiert **nur einmal**. Er erzeugt eine Long-Form-Wahrheit, die zu
**Zweig B (Parquet)** verdichtet wird — und aus diesem Parquet leiten sich **beide** Ausgaben
ab. Viewer und Analytik teilen so **eine Transformationsstelle** und können nicht auseinanderlaufen:

```
/raw  ─►  Parser + DPM-Join (Codebook)  ─►  long_form_raw.csv  ─►  ZWEIG B: /processed/long/p3dh_long.parquet
                                                                    (self-contained, DuckDB; EUR-normalisiert +
                                                                     Original, LEI/Entity-Keys, Flags, FX)
                                                                          │  build_zweig_a_shards.py
                                                                          ▼
                                                          ZWEIG A: JSON-Shards (data-Branch → jsDelivr)
                                                          - index.json (Report-Meta) + codebook.json
                                                          - benchmark.json (KM1/OV1-Head, lazy)
                                                          - reports/<key>.json (per Report, lazy)
                                                          → viewer_json.html rekonstruiert die Templates,
                                                            Benchmark / Zeitreihen / Vergleich im Browser
```

Zweig A wird **immer aus** Zweig B abgeleitet, nie parallel geparst (Werte byte-identisch
verifiziert). Der Legacy-CSV-Viewer (`viewer.html`) liest die Long-Form-CSV direkt und dient
nur noch als lokale, unabhängige Gegenprobe.

## Lokal arbeiten

Der Zustand der Pipeline (Long-Form, Coverage-Matrix, Zweig-B-Parquet) liegt **nicht** im
Repo, sondern auf dem `data`-Branch unter `state/`. Ein frischer Clone holt ihn sich:

```bash
bash scripts/fetch_state.sh     # ~300 MB, danach ist alles lokal auswertbar
```

Danach genügt `python3 scripts/build_zweig_b.py` bzw. DuckDB direkt auf dem Parquet.
Die DPM-Access-DB (720 MB) wird nur zum *Neubauen* des Codebooks gebraucht — das
fertige `codebook/dpm_codebook.csv` liegt im Repo.

## Projektstruktur

| Ordner | Inhalt |
|---|---|
| `raw/` | Roh-XBRL-CSV-Pakete, **immutable**, nie überschreiben (gitignored) |
| `interim/edap_recon/` | Kataloge/Manifeste (Voll-Harvest, Wellen, latest-wins) |
| `processed/long/` | **Zweig B**: `p3dh_long.parquet` — die gejointe Wahrheit, speist die Shards (gitignored, regenerierbar) |
| `processed/zweig_a/` | **Zweig A**: `viewer_json.html` (Standard) + `viewer.html` (Legacy) + Gabelseite `index.html`; die JSON-Shards liegen auf dem `data`-Branch |
| `codebook/` | DPM-Mapping Code → Label/Einheit/Titel |
| `scripts/` | Harvester, Downloader, Parser, Zweig-B/A-Builder, Publish-Skript |
| `notebooks/` | Data-Science-Explorationen (Phase 4) |
| `docs/` | Decision-Memos, Format-Notizen, Query-Beispiele |

## Phasen

- **Phase 0** — Scoping & Zugangsklärung ✅ → `docs/phase0_decision_memo.md`
- **Phase 1** — Ingestion: Voll-Katalog-Harvester (`harvest_catalog_query.py`) + wellenweiser Download ✅
- **Phase 2** — Parsing & DPM-Join → Codebook + Long-Form ✅
- **Phase 3** — Zweig B (Parquet/DuckDB) + Zweig A (JSON-Viewer, aus Zweig B gespeist) ✅ · RF-4.1↔4.2-Brücke offen
- **Phase 4** — Explorationen: Peer-Benchmark live; NPL/ESG-Profile, Perzentile, Transparenz-Matrix offen

## Automatisierte Pipeline (GitHub Actions)

`.github/workflows/pipeline.yml` fährt die ganze Kette ohne den Laptop. Ausgelöst wird
manuell (`workflow_dispatch`); ein wöchentlicher Cron liegt auskommentiert bereit und
wird scharf geschaltet, sobald ein manueller Lauf sauber durch ist:

```
fetch_state.sh → plan_delta.py → download (nur Neues) → parse (inkrementell)
   → build_zweig_b.py → build_zweig_a_shards.py → publish_data_branch.sh
```

Der Lauf ist **zustandslos**: `raw/` startet leer, der Bestand kommt aus `state/` auf dem
`data`-Branch, und die Coverage-Matrix sagt, was schon verarbeitet ist — geladen wird nur
die Differenz. Zwei Schalter: `harvest` (Katalog neu ernten, opt-in, weil der
Playwright-/Power-BI-Teil der fragilste ist) und `full_reparse`. Ein **Sanity-Gate** bricht
vor dem Publish ab, falls der Bestand schrumpft.

## Arbeitsprinzipien

1. Reproduzierbarkeit: Roh-Layer immutable, jede Transformation skriptiert.
2. Annahmen offenlegen (im Code/README), nicht bei Kleinigkeiten nachfragen.
3. „Fehlt" ≠ „Null" durchgängig erhalten (`filing-indicators`).
4. Vergleichbarkeitsfallen (Rechnungslegung, Konsolidierung, nationale Optionen) als
   Caveat in jeder Analyse benennen.
5. Resubmissions: pro (Institut, Modul, Stichtag) zählt nur die neueste Einreichung
   („latest wins"). Der **vollständige Katalog** inkl. älterer Fassungen bleibt als
   Audit-Trail in `interim/edap_recon/manifest_full.csv` (4.278 Einreichungen, Voll-Harvest
   via `harvest_catalog_query.py`).
