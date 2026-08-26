"""Lädt die beiden DPM-Quellartefakte, die der Codebook-Bau braucht.

Beide sind groß und gitignored, ihre URLs standen bisher nur als Kommentar in
den jeweiligen Skripten — der Codebook-Rebuild war damit ein manueller Schritt
und lief nie in CI. Dieses Skript macht ihn reproduzierbar:

  codebook/DPM2_v4.2.accdb    DPM-2.0-Dictionary (kumulativ, RF 4.0/4.1/4.2)
                              -> build_codebook.py
  codebook/dpm_table_layout.zip  EBA Annotated Table Layout (Template-Titel)
                              -> extract_template_titles.py

Idempotent: vorhandene Dateien werden übersprungen (`--force` erzwingt neu).
Der Download wird erst nach vollständigem Transfer an seinen Zielnamen
verschoben, damit ein Abbruch keine halbe Datei hinterlässt, die beim nächsten
Lauf als „schon da" gilt.

Lauf:  python3 scripts/fetch_dpm_sources.py [--force]
"""

from pathlib import Path
from urllib.request import urlopen, Request
import argparse
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
CODEBOOK = ROOT / "codebook"

DPM_ZIP_URL = ("https://www.eba.europa.eu/sites/default/files/2025-11/"
               "d67068fe-6327-4890-9163-3a9fcdabb58f/"
               "DPM2%20Database_v%204_2_20251125.zip")
DPM_DB = CODEBOOK / "DPM2_v4.2.accdb"

LAYOUT_URL = ("https://www.eba.europa.eu/sites/default/files/2025-07/"
              "44989a9c-e7e8-4126-8032-1156dc1c4b51/"
              "3.d%20DPM%20table%20layout%20and%20data%20point%20categorization__new.zip")
LAYOUT_ZIP = CODEBOOK / "dpm_table_layout.zip"

TIMEOUT = 300
CHUNK = 1 << 20


def download(url: str, dest: Path) -> None:
    """Streamt nach dest.tmp und benennt erst am Ende um (kein halber Rest)."""
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    req = Request(url, headers={"User-Agent": "P3DH/1.0 (research pipeline)"})
    with urlopen(req, timeout=TIMEOUT) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("content-length") or 0)
        done = 0
        while True:
            chunk = r.read(CHUNK)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r    {done / 1e6:.0f}/{total / 1e6:.0f} MB", end="", flush=True)
    if total:
        print()
    tmp.replace(dest)


def fetch_layout(force: bool) -> None:
    if LAYOUT_ZIP.exists() and not force:
        print(f"  ✓ {LAYOUT_ZIP.name} schon da ({LAYOUT_ZIP.stat().st_size / 1e6:.0f} MB)")
        return
    print(f"  ↓ {LAYOUT_ZIP.name}")
    download(LAYOUT_URL, LAYOUT_ZIP)
    print(f"  ✓ {LAYOUT_ZIP.name} ({LAYOUT_ZIP.stat().st_size / 1e6:.0f} MB)")


def fetch_dpm_db(force: bool) -> None:
    """Lädt das DPM-Zip und packt die .accdb daraus aus."""
    if DPM_DB.exists() and not force:
        print(f"  ✓ {DPM_DB.name} schon da ({DPM_DB.stat().st_size / 1e6:.0f} MB)")
        return
    zip_path = CODEBOOK / "dpm2_database.zip"
    print(f"  ↓ {zip_path.name}")
    download(DPM_ZIP_URL, zip_path)

    with zipfile.ZipFile(zip_path) as z:
        members = [n for n in z.namelist() if n.lower().endswith(".accdb")]
        if not members:
            raise SystemExit(f"ERROR: keine .accdb in {zip_path.name} "
                             f"(enthält: {z.namelist()[:5]})")
        member = max(members, key=lambda n: z.getinfo(n).file_size)
        print(f"  entpacke {member}")
        with z.open(member) as src, open(DPM_DB, "wb") as dst:
            shutil.copyfileobj(src, dst, CHUNK)

    zip_path.unlink()   # das Zip wird nach dem Entpacken nicht mehr gebraucht
    print(f"  ✓ {DPM_DB.name} ({DPM_DB.stat().st_size / 1e6:.0f} MB)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="auch dann laden, wenn die Datei schon vorhanden ist")
    args = ap.parse_args()

    CODEBOOK.mkdir(parents=True, exist_ok=True)
    print("DPM-Quellen:")
    try:
        fetch_layout(args.force)
        fetch_dpm_db(args.force)
    except Exception as e:
        print(f"\n✗ Download fehlgeschlagen: {e}")
        return 1
    print("\n✓ DPM-Quellen bereit — jetzt extract_template_titles.py und build_codebook.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
