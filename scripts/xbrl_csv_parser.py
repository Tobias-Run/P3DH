"""Phase 2: XBRL-CSV → Long-Form Tidy Data Parser.
Converts individual .zip submissions to unified long-form format."""

from pathlib import Path
import csv
import zipfile
import json
from typing import Dict, List, Tuple


class XBRLCSVParser:
    """Parse XBRL-CSV report package into long-form tidy data."""

    def __init__(self, zip_path: Path, codebook_path: Path = None):
        self.zip_path = zip_path
        self.codebook = self._load_codebook(codebook_path)
        self.metadata = {}
        self.datapoints = []

    def _load_codebook(self, codebook_path):
        """Load datapoint codebook (dp<n> → label)."""
        codebook = {}
        if codebook_path and codebook_path.exists():
            with open(codebook_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dp_code = row.get("datapoint_code", "")
                    codebook[dp_code] = {
                        "label": row.get("label", ""),
                        "unit": row.get("unit", ""),
                        "template": row.get("template", ""),
                    }
        return codebook

    def parse(self) -> Tuple[Dict, List[Dict]]:
        """Parse .zip and return (metadata, datapoints_list)."""
        with zipfile.ZipFile(self.zip_path, "r") as z:
            # 1. Extract metadata
            self._extract_metadata(z)

            # 2. Extract filing indicators (templates reported: true/false)
            filing_indicators = self._extract_filing_indicators(z)

            # 3. Parse all k_NN.csv files
            self._extract_datapoints(z, filing_indicators)

        return self.metadata, self.datapoints

    def _extract_metadata(self, z: zipfile.ZipFile):
        """Extract parameters.csv → metadata dict."""
        try:
            params_file = next(f for f in z.namelist() if f.endswith("parameters.csv"))
            params_csv = z.read(params_file).decode("utf-8-sig")
            reader = csv.DictReader(params_csv.splitlines())
            params_dict = {}
            for row in reader:
                params_dict[row.get("name", "")] = row.get("value", "")

            self.metadata = {
                "entityID": params_dict.get("entityID", ""),
                "refPeriod": params_dict.get("refPeriod", ""),
                "baseCurrency": params_dict.get("baseCurrency", ""),
                "decimalsMonetary": params_dict.get("decimalsMonetary", ""),
                "framework_version": self._extract_framework_version(z),
                "submission_file": self.zip_path.name,
            }
        except Exception as e:
            print(f"ERROR extracting metadata: {e}")

    def _extract_framework_version(self, z: zipfile.ZipFile) -> str:
        """Extract framework version from report.json."""
        try:
            report_json = z.read(next(f for f in z.namelist() if f.endswith("report.json")))
            data = json.loads(report_json)
            extends = data.get("documentInfo", {}).get("extends", [])
            if isinstance(extends, list):
                extends = extends[0] if extends else ""
            # Format: http://…/pillar3/4.1/mod/codis.json → 4.1
            if "pillar3/" in extends:
                version = extends.split("pillar3/")[1].split("/")[0]
                return version
        except:
            pass
        return ""

    def _extract_filing_indicators(self, z: zipfile.ZipFile) -> Dict[str, bool]:
        """Extract FilingIndicators.csv → template→reported mapping."""
        indicators = {}
        try:
            filing_file = next(f for f in z.namelist() if f.endswith("FilingIndicators.csv"))
            filing_csv = z.read(filing_file).decode("utf-8")
            reader = csv.DictReader(filing_csv.splitlines())
            for row in reader:
                template_id = row.get("templateID", "").upper()
                reported = row.get("reported", "").lower() == "true"
                indicators[template_id] = reported
        except Exception as e:
            print(f"  Warning: FilingIndicators not found: {e}")
        return indicators

    def _extract_datapoints(self, z: zipfile.ZipFile, filing_indicators: Dict):
        """Parse all k_NN.csv files → long-form records."""
        datapoints = []
        k_files = [f for f in z.namelist() if "/k_" in f and f.endswith(".csv")]

        for k_file in k_files:
            # Extract template ID from filename (e.g., k_01.00.csv → 01.00)
            template_id = Path(k_file).stem.replace("k_", "").upper()
            # Check if template was filed
            reported = filing_indicators.get(template_id, False)

            try:
                k_csv = z.read(k_file).decode("utf-8")
                reader = csv.DictReader(k_csv.splitlines())
                for row in reader:
                    dp_code = row.get("datapoint", "")
                    fact_value = row.get("factValue", "")

                    # Skip empty rows
                    if not dp_code or not fact_value:
                        continue

                    # Look up label/unit in codebook
                    cb_entry = self.codebook.get(dp_code, {})

                    record = {
                        "entityID": self.metadata.get("entityID", ""),
                        "refPeriod": self.metadata.get("refPeriod", ""),
                        "framework_version": self.metadata.get("framework_version", ""),
                        "template_id": template_id,
                        "template_reported": reported,
                        "datapoint_code": dp_code,
                        "datapoint_label": cb_entry.get("label", "[TODO]"),
                        "fact_value": fact_value,
                        "unit": cb_entry.get("unit", "[TODO]"),
                        "baseCurrency": self.metadata.get("baseCurrency", ""),
                        "decimalsMonetary": self.metadata.get("decimalsMonetary", ""),
                    }
                    datapoints.append(record)
            except Exception as e:
                print(f"  Error parsing {k_file}: {e}")

        self.datapoints = datapoints
        return datapoints


def parse_all_reports(raw_dir: Path, codebook_path: Path, output_path: Path):
    """Parse all .zip files in raw_dir → combined long-form CSV."""
    all_records = []
    zip_files = list(raw_dir.glob("*.zip"))

    print(f"Parsing {len(zip_files)} reports...")
    for i, zip_file in enumerate(zip_files, 1):
        try:
            parser = XBRLCSVParser(zip_file, codebook_path)
            metadata, datapoints = parser.parse()
            all_records.extend(datapoints)
            print(f"  [{i:2d}/{len(zip_files)}] {zip_file.name[:50]:50s} {len(datapoints):6d} datapoints")
        except Exception as e:
            print(f"  [{i:2d}/{len(zip_files)}] {zip_file.name[:50]:50s} ERROR: {e}")

    # Write long-form CSV
    if all_records:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = list(all_records[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_records)
        print(f"\n✓ Long-form data: {output_path}")
        print(f"  Total records: {len(all_records)}")
    else:
        print("ERROR: No records extracted")


if __name__ == "__main__":
    RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
    CODEBOOK = Path(__file__).resolve().parent.parent / "codebook" / "mini_codebook_from_reports.csv"
    OUTPUT = Path(__file__).resolve().parent.parent / "processed" / "long_form_raw.csv"

    parse_all_reports(RAW_DIR, CODEBOOK, OUTPUT)
