"""Phase 1: Download raw .zip reports from errp.eba.europa.eu.
Reads manifest.csv, downloads in parallel, skips existing files.

Known data quirk: ~1% of catalog entries are dead links (HTTP 404 "blob does not
exist" — the submission row exists in the EDAP catalog but the file was never
published or was withdrawn). These are expected; the script reports them as
failed and they simply stay missing."""

from pathlib import Path
import csv
import sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Manifest to download: CLI arg wins, else the latest-wins default.
_RECON = Path(__file__).resolve().parent.parent / "interim" / "edap_recon"
MANIFEST = Path(sys.argv[1]) if len(sys.argv) > 1 else _RECON / "manifest_latest.csv"
RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
RAW_DIR.mkdir(exist_ok=True)

MAX_WORKERS = 4  # Conservative for M1/8GB


def download_file(url, dest_path, timeout=30):
    """Download single file, return (url, success, msg)."""
    if dest_path.exists():
        return (url, True, f"exists ({dest_path.stat().st_size} bytes)")

    try:
        resp = requests.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        return (url, True, f"✓ {total} bytes")
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink()
        return (url, False, str(e)[:80])


def main():
    if not MANIFEST.exists():
        print(f"ERROR: Manifest not found at {MANIFEST}")
        print("Run: python scripts/harvest_catalog.py && python scripts/resolve_latest_submissions.py first")
        return

    # Load URLs from manifest
    urls = []
    with open(MANIFEST, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            urls.append(row["url"])

    print(f"Loaded {len(urls)} URLs from manifest")
    print(f"Downloading to {RAW_DIR} (max {MAX_WORKERS} workers)")

    # Download in parallel
    completed = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for url in urls:
            filename = url.split("/")[-1]
            dest = RAW_DIR / filename
            fut = executor.submit(download_file, url, dest)
            futures[fut] = url

        for fut in as_completed(futures):
            url, success, msg = fut.result()
            filename = url.split("/")[-1]
            status = "✓" if success else "✗"
            print(f"  {status} {filename[:50]:50s} {msg}")
            if success:
                completed += 1
            else:
                failed += 1

    print(f"\nDownload complete: {completed} ok, {failed} failed")
    print(f"Total files in {RAW_DIR}: {len(list(RAW_DIR.glob('*.zip')))}")


if __name__ == "__main__":
    main()
