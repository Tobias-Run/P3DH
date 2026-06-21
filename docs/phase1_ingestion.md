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

## Step 1.5: Resolve Resubmissions ("latest wins")

EDAP enthält pro (Institut, Modul, Stichtag) teils mehrere Submissions
(Korrekturen). Policy: nur die jeweils neueste (höchster `submission_ts`)
wird heruntergeladen/geparst. Ältere Fassungen bleiben im Roh-Katalog
(`manifest_urls.csv`) als Audit-Trail erhalten, fließen aber nicht in
Download/Parsing ein.

```bash
python3 scripts/resolve_latest_submissions.py
```

**What happens:**
1. Liest `manifest_urls.csv` (vollständiger Katalog, eine Zeile je Submission)
2. Gruppiert nach `(lei, consolidation, country, module, refdate)`
3. Behält je Gruppe nur die Zeile mit dem höchsten `submission_ts`
4. Schreibt `interim/edap_recon/manifest_latest.csv`, loggt verworfene Resubmissions

**Output:** `interim/edap_recon/manifest_latest.csv` — diese Datei konsumieren
Download und Parser, nicht `manifest_urls.csv`.

---

## Step 2: Download Reports

Parallel HTTP download from public URLs into `/raw/`.

```bash
python3 scripts/download_raw_reports.py
```

**What happens:**
1. Reads `manifest_latest.csv` (nur aktuellste Submission je Institut/Modul/Stichtag)
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

