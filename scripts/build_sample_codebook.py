"""Phase 2 Interim: Extract all dp<n> codes from sample reports + build mini codebook."""

from pathlib import Path
import csv
import re
from collections import Counter

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "interim" / "sample_DE"
RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
CODEBOOK_DIR = Path(__file__).resolve().parent.parent / "codebook"
CODEBOOK_DIR.mkdir(exist_ok=True)

# Regex to find dp<number>
DP_PATTERN = re.compile(r'dp(\d+)')


def extract_datapoints_from_csv(csv_path):
    """Extract all dp<n> codes from a single CSV file."""
    codes = set()
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Look in all columns for dp<n> patterns
                for value in row.values():
                    if value:
                        matches = DP_PATTERN.findall(str(value))
                        codes.update(matches)
    except Exception as e:
        print(f"    Error reading {csv_path.name}: {e}")
    return codes


def extract_from_directory(dir_path):
    """Recursively extract all dp<n> codes from all CSV files in directory."""
    all_codes = Counter()
    csv_files = list(dir_path.rglob("*.csv"))

    print(f"Scanning {len(csv_files)} CSV files...")
    for csv_file in csv_files:
        codes = extract_datapoints_from_csv(csv_file)
        for code in codes:
            all_codes[code] += 1

    return all_codes


def main():
    print("=" * 60)
    print("Phase 2: Building Sample Codebook from Extracted Datapoints")
    print("=" * 60)

    # Extract from sample reports (Phase 0)
    print("\n1. Extracting from sample reports...")
    sample_codes = extract_from_directory(SAMPLE_DIR)
    print(f"   Found {len(sample_codes)} unique datapoints in sample")

    # Extract from all downloaded reports (Phase 1)
    print("\n2. Extracting from all Phase 1 reports...")
    all_codes = Counter()
    for zip_file in RAW_DIR.glob("*.zip"):
        import zipfile
        try:
            with zipfile.ZipFile(zip_file, "r") as z:
                for name in z.namelist():
                    if name.endswith(".csv") and "/reports/" in name:
                        try:
                            content = z.read(name).decode("utf-8")
                            for line in content.splitlines():
                                matches = DP_PATTERN.findall(line)
                                for match in matches:
                                    all_codes[match] += 1
                        except:
                            pass
        except:
            pass

    print(f"   Found {len(all_codes)} unique datapoints across all reports")

    # Build mini codebook (placeholder labels)
    print("\n3. Building mini codebook...")
    mini_codebook = []
    for dp_code in sorted(all_codes.keys(), key=int):
        mini_codebook.append({
            "datapoint_code": f"dp{dp_code}",
            "frequency": all_codes[dp_code],
            "label": f"[TODO: DPM lookup] dp{dp_code}",
            "unit": "[TODO]",
            "template": "[TODO]",
        })

    # Save mini codebook
    codebook_path = CODEBOOK_DIR / "mini_codebook_from_reports.csv"
    with open(codebook_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=mini_codebook[0].keys())
        writer.writeheader()
        writer.writerows(mini_codebook)

    print(f"   ✓ Mini codebook: {codebook_path}")
    print(f"   Rows: {len(mini_codebook)}")

    # Most frequent datapoints
    print("\n4. Top 20 most frequent datapoints:")
    for code, freq in all_codes.most_common(20):
        print(f"   dp{code:8s} — appears {freq:3d} times")

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total unique datapoints: {len(all_codes)}")
    print(f"  Codebook created (with TODO placeholders for DPM lookup)")
    print(f"  Next: Manual DPM lookup or full Access DB extraction")
    print("=" * 60)


if __name__ == "__main__":
    main()
