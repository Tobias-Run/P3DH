"""Phase 1.5: Extract parameters.csv from each .zip and build extended manifest."""

from pathlib import Path
import csv
import zipfile
import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
MANIFEST_IN = Path(__file__).resolve().parent.parent / "interim" / "edap_recon" / "manifest_urls.csv"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "processed"
PROCESSED_DIR.mkdir(exist_ok=True)

MANIFEST_OUT = PROCESSED_DIR / "manifest_with_metadata.csv"


def extract_parameters(zip_path):
    """Extract parameters.csv from .zip, return dict."""
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            # Find parameters.csv (may be nested under a directory)
            params_file = None
            for name in z.namelist():
                if name.endswith("parameters.csv"):
                    params_file = name
                    break
            if not params_file:
                return {"error": "no parameters.csv"}

            params_csv = z.read(params_file).decode("utf-8-sig")  # BOM handling
            reader = csv.DictReader(params_csv.splitlines())
            params_dict = {}
            for row in reader:
                name = row.get("name", "")
                value = row.get("value", "")
                params_dict[name] = value
            return {
                "baseCurrency": params_dict.get("baseCurrency", ""),
                "decimalsMonetary": params_dict.get("decimalsMonetary", ""),
                "refPeriod": params_dict.get("refPeriod", ""),
                "entityID": params_dict.get("entityID", ""),
            }
    except Exception as e:
        return {"error": str(e)[:50]}


def main():
    # Load base manifest
    manifest = []
    with open(MANIFEST_IN, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        manifest = list(reader)

    print(f"Loaded {len(manifest)} entries from base manifest")

    # Extract metadata from each .zip
    extended = []
    for row in manifest:
        filename = row["url"].split("/")[-1]
        zip_path = RAW_DIR / filename

        params = extract_parameters(zip_path)
        row.update(params)
        extended.append(row)
        print(f"  ✓ {filename[:60]:60s} {params.get('baseCurrency', 'ERROR')}")

    # Write extended manifest
    with open(MANIFEST_OUT, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(extended[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(extended)

    print(f"\n✓ Extended manifest: {MANIFEST_OUT}")
    print(f"  Columns: {', '.join(fieldnames)}")

    # Summary stats
    df = pd.DataFrame(extended)
    print(f"\nCurrency distribution:")
    print(df["baseCurrency"].value_counts())
    print(f"\nReference periods:")
    print(df["refPeriod"].value_counts())


if __name__ == "__main__":
    main()
