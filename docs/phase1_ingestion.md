# Phase 1: Ingestion — Catalog Harvest & HTTP Download

**Goal:** Download all EBA Pillar 3 XBRL-CSV reports from EDAP into `/raw/`.

**Blockers:** None. Phase 1 is independent of DPM dictionary (Phase 2).

---

## Step 1: Harvest Catalog

Extract all submission URLs from EDAP Submissions table via Playwright headless browser automation.

```bash
cd /Users/tobibi/P3dh
python3 scripts/harvest_catalog.py
```

**What happens:**
1. Opens EDAP, navigates to Submissions table
2. Scrolls through virtualized table (150 iterations × 1s = ~2.5 min)
3. Extracts all `errp.eba.europa.eu/public-documents/CODIS/input/…zip` URLs
4. Saves manifest: `interim/edap_recon/manifest_urls.csv`

**Output columns:**
- `url` — direct HTTPS download link
- `lei`, `consolidation`, `country`, `module`, `refdate`, `submission_ts` — parsed from filename

**Notes:**
- Hardware constraint: M1/8GB → Chromium runs sequentially (see [[user-hardware]])
- Table is virtualized; scroll count is conservative (150) to ensure full enumeration
- Typical runtime: 2–5 min depending on network

---

## Step 1.5: Parse-Manifest bauen ("latest wins")

EDAP enthält pro (Institut, Modul, Stichtag) teils mehrere Submissions
(Korrekturen). Policy: nur die jeweils neueste (höchster `submission_ts`)
wird heruntergeladen/geparst. Ältere Fassungen bleiben im Roh-Katalog
(`manifest_urls.csv`) als Audit-Trail erhalten, fließen aber nicht in
Download/Parsing ein.

```bash
python3 scripts/build_parse_manifest.py
```

**What happens:**
1. Liest den vollen Katalog (`manifest_full.csv` und die Wellen-/Stichproben-Manifeste)
2. Gruppiert nach `(lei, consolidation, module, refdate, report_type)` —
   die Regel steht in `scripts/submissions.py`
3. Behält je Gruppe nur die Zeile mit dem höchsten `submission_ts`
4. Filtert auf XBRL-CSV-Pakete (die `*DISDOCS`-Pakete enthalten PDFs, kein XBRL)
5. Schreibt `interim/edap_recon/manifest_parse.csv`

**Output:** `interim/edap_recon/manifest_parse.csv` — **diese** Datei konsumieren
Download und Parser. Es ist auch der Default beider Skripte, und `pipeline.yml`
übergibt sie explizit.

> ⚠️ **`manifest_latest.csv` ist nicht diese Datei** (#88). Sie entsteht in
> `resolve_latest_submissions.py`, dessen Schlüssel den **Modultyp** nicht
> enthält — und die Spalte `module` trägt nur den numerischen PILLAR3-Code
> (`020000`), unter dem CODIS, ESGDIS, FINDIS, REMDIS, IRRBBDIS, MRELTLACDIS
> und GSIIDIS als eigenständige Meldungen liegen. „Latest wins" verwirft sie
> dort als überholte Resubmissions: **1.746 statt 2.829 Einreichungen, 38 %
> weg** (FINDIS 617 → 127, ESGDIS 289 → 53).
>
> Das Tückische ist nicht der Verlust, sondern seine Unsichtbarkeit: nichts
> schlägt fehl, alle Kennzahlen bleiben plausibel, und das Skript meldet eine
> Deduplikationszahl, die nach korrekter Arbeit aussieht. Bis September 2026
> stand hier die Anweisung, `manifest_latest.csv` zu konsumieren — wer ihr
> folgte, bekam einen kleineren Bestand, der wie ein vollständiger aussah.
>
> `country` gehört übrigens auch dann nicht in den Schlüssel, wenn es
> naheliegt: zwei Institute haben unter falschem Ländercode eingereicht und
> korrigiert (UniCredit Banka Slovenija als `FR` statt `SI`, Sparkasse Malta
> als `FR` statt `MT`). Mit `country` zählen beide Fassungen doppelt.

---

## Step 2: Download Reports

Parallel HTTP download from public URLs into `/raw/`.

```bash
python3 scripts/download_raw_reports.py
```

**What happens:**
1. Reads `manifest_parse.csv` (nur aktuellste Fassung je Institut/Modul**typ**/Stichtag)
2. Downloads each `.zip` in parallel (4 workers, respects M1 constraint)
3. Skips files already in `/raw/`
4. Prints progress per file

**Output:** `/raw/*.zip` + count

**Notes:**
- No authentication required (public HTTPS)
- Respects M1 CPU/RAM constraints with MAX_WORKERS=4
- Typical runtime: depends on total file size (estimated 100–500 MB for full catalog)

---

## Step 3 (Future): Metadata Extraction

Once `/raw/` is populated, extract `parameters.csv` from each `.zip` and join into extended manifest.
Deliverable: `processed/manifest_with_metadata.csv` (adds `baseCurrency`, `decimalsMonetary`, etc.).

---

## Troubleshooting

**Playwright timeout:**
- EDAP takes ~12s to load. If timeout occurs, increase `page.wait_for_timeout(12000)` in `harvest_catalog.py`.

**Table scroll doesn't extract URLs:**
- Power BI DOM structure may have changed. Check `interim/edap_recon/interactive_*.txt` from prior run.
- Alternative: Manually inspect browser DevTools (F12 → Network) to find URL pattern.

**Download fails with "Device not configured":**
- Retry manually: `curl -fL <url> -o raw/<filename>`

**DPM Dictionary not yet available for codebook:**
- Phase 1 doesn't need it. Phase 2 (Parsing + Long-Form conversion) will use `codebook/DPM2.0_release_4.0_2024-12-10.accdb`.

