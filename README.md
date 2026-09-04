# EBA Pillar 3 Data Hub (P3DH) — Datenanalyse-Pipeline

**Europas Banken legen alles offen. Lesen kann es fast niemand.**

Die EBA veröffentlicht die aufsichtlichen Offenlegungen der großen EU- und
EEA-Institute an einer Stelle, maschinenlesbar als XBRL-CSV. Das war ein
echter Fortschritt — und es löste die falsche Hälfte des Problems. Das Portal
gibt ein Bankarchiv nach dem anderen heraus. Ob eine Kapitalquote hoch ist, ob
ein Länderexposure ungewöhnlich aussieht oder ob eine gemeldete Zahl überhaupt
plausibel ist, sagt es nicht.

Diese Fragen brauchen die Population als Maßstab. Also haben wir sie gebaut:
jede Einreichung geparst, jeden Datenpunkt gegen das DPM aufgelöst, jedes
Template mit echten Zeilen- und Spaltenlabels rekonstruiert — und dann über die
Institute hinweg verglichen.

Der Unterschied zeigt sich schnell. Eine Meldung im Bestand weist **11,7 Bio.
EUR fixe Vorstandsvergütung für neun Personen** aus, rund das Dreifache des
deutschen BIP. Für sich gelesen ist das eine Zahl. Gegen 330 vergleichbare
Meldungen gelesen, deren Median bei 1,6 Mio. EUR liegt, ist es ein Befund. Wir
korrigieren sie nicht — wir markieren sie und sagen, warum.

> **Aktueller Projektstatus:** siehe `SESSION_STATUS.md` — wird laufend aktuell gehalten.
> `P3DH agent instructions.txt` war nur das initiale Briefing zu Projektstart und wird
> seitdem nicht mehr fortgeschrieben; für den heutigen Stand nicht verlässlich.

## 🔗 Live-Viewer (im Browser, ohne Installation)

**Öffentlich live:** **https://tobias-run.github.io/P3DH/** — kein Klonen/Server nötig.

Der **Zweig-A-Viewer** rekonstruiert die Bank-Templates (KM1, OV1, CCR1 …) mit vollen
Zeilen-/Spalten-Labels und bietet **Peer-Benchmark, Zeitreihen und Vergleich** über die
Institute. Aktuell geladen: **882 Reports · 2,30 Mio. platzierte Fakten · 474 Institute ·
30 Länder** über fünf Stichtage; Voll-Katalog = 489 Institute / 4.278 Einreichungen,
wellenweise nachladbar.

Drei Dinge, die das offizielle Portal nicht leistet:

- **Verteilung statt Rangliste.** Peer-Gruppen nach Größenklasse, Konsolidierungskreis
  und Stichtag; Perzentilbänder statt nackter Tabellenführung. Ein Randwert liegt am Rand
  einer Verteilung, nicht an der Spitze einer Liste. Gemessen sind rund **6 %** der
  Reports in einer gegebenen Kennzahl Randwerte.
- **Plausibilität gegen die Population** — markiert, nie versteckt, nie verändert.
- **Länderexposure über Institute hinweg**: Heimatanteil, Länder-HHI und ein ehrliches
  Qualitätsflag für den Residualbucket. Der Median liegt bei **82,3 %** Heimatanteil
  (363 belastbare Reports).

- **Landing:** `index.html` · **Viewer (Standard):** `processed/zweig_a/viewer_json.html`
- **Wie es lädt:** Der JSON-Viewer holt einen schlanken `index.json` vorab und jeden Report
  **erst beim Öffnen** als per-Report-JSON-Shard (nativ `JSON.parse`, kein CSV-Parser im
  Browser). So skaliert er Richtung Voll-Load. Die Shards werden **aus dem Zweig-B-Parquet
  abgeleitet** (eine Transformationsstelle) und über den Orphan-`data`-Branch via **jsDelivr**
  ausgeliefert (Fallback: `raw.githubusercontent.com`).
- **Gabelseite** `processed/zweig_a/index.html`: JSON-Viewer (Standard) vs. CSV-Viewer (Legacy,
  nur lokal — braucht die 413 MB große `long_form_raw.csv`).
- **Lokal:** `python3 -m http.server 8766` im Repo-Root → `http://localhost:8766/`
- **Gestaltung:** ein redaktionelles System (#61) — ruhiger Kopf, Serif für Überschriften,
  ein einziger Akzent, und **Rot bedeutet Fokus, nie Wertung**. Zwei Tests halten das fest:
  die Akzentfarbe darf nur auf Fokus-Selektoren stehen, und jede Text-auf-Fläche-Paarung
  muss in beiden Themes WCAG AA erfüllen.

## Was es nicht ist

Keine Aufsicht und keine Bestenliste. Die Vergleichbarkeit über Institute hinweg ist
tatsächlich begrenzt: Rechnungslegung, Konsolidierungskreise und nationale Optionen
unterscheiden sich, und die Meldetaxonomie hat sich mitten im Bestand geändert. Jede
Rangliste trägt diesen Vorbehalt sichtbar mit. Uns ist ein „das können wir nicht sagen"
lieber als eine Genauigkeit, die die Daten nicht hergeben.

Und: **Fehlt ist nicht Null.** Institute dürfen nach CRR Art. 432 rechtmäßig auslassen,
und ein Template, das *wir* nicht platzieren können, ist unsere Lücke, nicht ihre. Der
Viewer unterscheidet beides überall — die zwei zu vermengen hieße, Schweigen still in
einen Befund zu verwandeln.

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
- **Phase 3** — Zweig B (Parquet/DuckDB) + Zweig A (JSON-Viewer, aus Zweig B gespeist) ✅ ·
  RF-4.1↔4.2-Brücke gebaut (5.275 beobachtete Zellen: 5.087 stabil, 63 umgebunden,
  125 mehrdeutig); ihre **Darstellung** in Zeitreihe und Sparkline ist offen (#26) —
  103 von 475 Instituten haben inzwischen Reports beiderseits des Bruchs
- **Phase 4** — Explorationen: sechs Benchmark-Profile (KM1, Headroom, Risiko, Liquidität,
  NPL/CQ3, ESG/41.00) ✅ · Perzentilbänder je Peer-Gruppe ✅ · Plausibilitätsprofil (#17) ✅ ·
  Footprint-Kennzahlen (#12) ✅ · Clustering und Transparenz-Matrix offen

## Automatisierte Pipeline (GitHub Actions)

`.github/workflows/pipeline.yml` fährt die ganze Kette ohne den Laptop. Ausgelöst wird
manuell (`workflow_dispatch`). Ein wöchentlicher Cron liegt auskommentiert bereit; die
Vorbedingung „ein manueller Lauf muss sauber durchlaufen" ist seit Lauf #5 erfüllt, offen
ist nur noch die Entscheidung über den Harvest (#8):

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

1. Reproduzierbarkeit: Roh-Layer immutable, jede Transformation skriptiert —
   und **byte-genau**: gleiche Eingaben, gleiche Ausgaben. Die Regel, die das
   trägt: *jedes Feld, das in die Ausgabe fließt, gehört in den `ORDER BY`.*
   Durchgesetzt von `scripts/determinism.py` im Ausführungspfad, nicht bloß im
   Test. Warum das ein eigenes Prinzip verdient hat und dreimal verletzt wurde:
   `docs/reproduzierbarkeit.md`.
2. Annahmen offenlegen (im Code/README), nicht bei Kleinigkeiten nachfragen.
3. „Fehlt" ≠ „Null" durchgängig erhalten (`filing-indicators`) — **auch in der
   Oberfläche**: der JSON-Viewer zeigt je Report, welche Templates bewusst nicht
   offengelegt wurden, wo unser Bestand lückt und wo die Meldung sich selbst
   widerspricht. Ohne Deklaration wird **keine** Aussage getroffen.
4. Vergleichbarkeitsfallen (Rechnungslegung, Konsolidierung, nationale Optionen) als
   Caveat in jeder Analyse benennen. **Neu seit der offenen Zeilenachse (#56):**
   Templates mit offener Achse zerfallen in zwei Klassen. Bei CCyB1 (`67.01.A`)
   ist die Zeile ein ISO-Ländercode und damit institutsübergreifend vergleichbar;
   bei CC2 (`66.02`) und LI2/LI3 (`64.01`, `64.02`) ist sie der **Bilanzposten
   des Instituts**, also Freitext in Landessprache — 5.324 verschiedene Zeilen
   allein in `64.02`. Diese sind innerhalb eines Reports auswertbar, aber ohne
   vorherige Zuordnung **nicht** für Peer-Vergleiche.
5. Resubmissions: pro (Institut, Modul, Stichtag) zählt nur die neueste Einreichung
   („latest wins"). Der **vollständige Katalog** inkl. älterer Fassungen bleibt als
   Audit-Trail in `interim/edap_recon/manifest_full.csv` (4.278 Einreichungen, Voll-Harvest
   via `harvest_catalog_query.py`).

---

*Gestaltung inspiriert von The Economist — dem wir die Einsicht verdanken, dass eine
Grafik eine Meinung haben darf, solange sie ihre Quelle nennt. Mit der Publikation in
keiner Weise verbunden; Schriften und Farbwerte sind eigene, und das rote Rechteck haben
wir ihnen gelassen.*
