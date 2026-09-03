"""Phase 2: XBRL-CSV → Long-Form Tidy Data Parser.
Converts individual .zip submissions to unified long-form format."""

from pathlib import Path
import csv
import zipfile
import json
from typing import Dict, List, Tuple

# Marker aus build_codebook.py: die Achse steht nicht im DPM-Modell, sondern
# entsteht beim Einreichen aus einem Dimensionswert.
OPEN_AXIS = "*"


def axis_member(open_dims: Dict[str, str]) -> str:
    """Dimensionswerte -> Zeilenschlüssel. {'RIO': 'eba_GA:AL'} -> 'AL'.

    Bei CCyB1 ist die Zeile das Land: die Datei trägt je Zeile eine Spalte `RIO`
    mit `eba_GA:AL`. Der Member-Code hinter dem letzten ':' ist der kompakte,
    stabile Schlüssel — bei geografischen Achsen zugleich der ISO-Code, den
    codebook/geo_names.csv auf den Ländernamen abbildet.

    Mehrere Dimensionen (Form `r*,c#,s*`: Zeile UND Blatt offen) werden
    verkettet. Welche davon fachlich "die Zeile" ist, sagt das DPM an dieser
    Stelle nicht — statt zu raten, geht die vollständige Kombination ein. Die
    Reihenfolge folgt den Spalten der Quelldatei und ist damit reproduzierbar.

    Nicht jede offene Achse trägt einen Member-Code: CC2 (`66.02`) und LI2/LI3
    (`64.01`) führen als Zeile den BILANZPOSTEN des Instituts, also Freitext —
    `qADQ=100. Provisions for risks and charges:`. Endet der auf einen
    Doppelpunkt, wäre der Teil dahinter leer und die Zeile fiele weg. Deshalb
    wird nur abgeschnitten, wenn dabei etwas übrig bleibt.
    """
    return "|".join(_member(v) for v in open_dims.values() if v)


def _member(value: str) -> str:
    """'eba_GA:AL' -> 'AL'; 'l. Fondi per rischi e oneri:' -> unverändert."""
    tail = value.rsplit(":", 1)[-1].strip()
    return tail or value.strip()


class XBRLCSVParser:
    """Parse XBRL-CSV report package into long-form tidy data."""

    def __init__(self, zip_path: Path, codebook_path: Path = None):
        self.zip_path = zip_path
        self.codebook = self._load_codebook(codebook_path)
        self.metadata = {}
        self.datapoints = []
        self.filing_indicators = {}

    def _load_codebook(self, codebook_path):
        """Load DPM codebook keyed by (datapoint_code, template) → cell coordinate.

        A datapoint can occur in several templates (shared variable), so the join
        key includes the template. Codebook template format: 'K_73.00.c'."""
        codebook = {}
        if codebook_path and codebook_path.exists():
            with open(codebook_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (row.get("datapoint_code", ""), row.get("template", ""))
                    codebook[key] = {
                        "row": row.get("row", ""),
                        "col": row.get("col", ""),
                        "cell_code": row.get("cell_code", ""),
                    }
        return codebook

    def parse(self) -> Tuple[Dict, List[Dict]]:
        """Parse .zip and return (metadata, datapoints_list)."""
        with zipfile.ZipFile(self.zip_path, "r") as z:
            # 1. Extract metadata
            self._extract_metadata(z)

            # 2. Extract filing indicators (templates reported: true/false)
            self.filing_indicators = self._extract_filing_indicators(z)

            # 3. Parse all k_NN.csv files
            self._extract_datapoints(z, self.filing_indicators)

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
            filing_csv = z.read(filing_file).decode("utf-8-sig")  # some files carry a BOM
            reader = csv.DictReader(filing_csv.splitlines())
            for row in reader:
                # FilingIndicators format: templateID="K_03.00" (uppercase, K_ prefix,
                # template-level only — no A/B/C sub-letter). Normalize to base id "03.00".
                raw_id = row.get("templateID", "")
                base_id = raw_id.upper().replace("K_", "").strip()
                reported = row.get("reported", "").lower() == "true"
                indicators[base_id] = reported
        except Exception as e:
            print(f"  Warning: FilingIndicators not found: {e}")
        return indicators

    def _extract_datapoints(self, z: zipfile.ZipFile, filing_indicators: Dict):
        """Parse all k_NN.csv files → long-form records."""
        datapoints = []
        k_files = [f for f in z.namelist() if "/k_" in f and f.endswith(".csv")]

        for k_file in k_files:
            # Extract template ID from filename (e.g., k_04.00.a.csv → 04.00.A)
            stem = Path(k_file).stem.replace("k_", "")
            template_id = stem.upper()
            # Codebook join key uses the DPM template code 'K_04.00.a' (lowercase sub-letter).
            template_code = "K_" + stem
            # Filing indicators are template-level only (K_04.00), so look up the
            # base id without the A/B/C sub-letter (04.00.A → 04.00).
            base_template = ".".join(template_id.split(".")[:2])
            reported = filing_indicators.get(base_template, False)

            try:
                k_csv = z.read(k_file).decode("utf-8-sig")  # some files carry a BOM
                reader = csv.DictReader(k_csv.splitlines())
                for row in reader:
                    dp_code = row.get("datapoint", "")
                    fact_value = row.get("factValue", "")

                    # Skip empty rows
                    if not dp_code or not fact_value:
                        continue

                    # Resolve cell coordinate from DPM codebook (datapoint × template)
                    cb_entry = self.codebook.get((dp_code, template_code), {})

                    # Open-axis templates (e.g. 67.01 CCyB1 geographical, 66.02 CC2,
                    # 64.0x LI2/LI3, 29.0x CR9/CR10) carry typed-dimension columns
                    # beyond datapoint/factValue (RIO=country, qADP/qABI=free text).
                    # The "row" of such a table is defined at filing time by this
                    # dimension value, not by a static DPM cell.
                    open_dims = {
                        k: v for k, v in row.items()
                        if k not in ("datapoint", "factValue") and (v or "").strip()
                    }
                    open_axis_dims = ";".join(f"{k}={v}" for k, v in open_dims.items())

                    # ... aber eine Koordinate gibt es sehr wohl: das DPM führt
                    # solche Zellen als '{K_67.01.a, r*, c0010}' — die SPALTE ist
                    # fest, nur die Zeile offen. Eine frühere Fassung hat den
                    # ganzen Eintrag verworfen und damit auch die bekannte Spalte;
                    # 409.057 Fakten (18 % des Bestands) blieben unplatzierbar (#56).
                    cell_row = cb_entry.get("row", "")
                    cell_col = cb_entry.get("col", "")
                    if cell_row == OPEN_AXIS:
                        # Leere Dimension -> leere Zeile: ohne Achsenwert gibt es
                        # keine Zeile, und geraten wird nicht ("Fehlt != Null").
                        cell_row = axis_member(open_dims)

                    record = {
                        "entityID": self.metadata.get("entityID", ""),
                        "refPeriod": self.metadata.get("refPeriod", ""),
                        "framework_version": self.metadata.get("framework_version", ""),
                        "template_id": template_id,
                        "template_reported": reported,
                        "datapoint_code": dp_code,
                        "cell_row": cell_row,
                        "cell_col": cell_col,
                        "open_axis_dims": open_axis_dims,
                        "fact_value": fact_value,
                        "baseCurrency": self.metadata.get("baseCurrency", ""),
                        "decimalsMonetary": self.metadata.get("decimalsMonetary", ""),
                        "source_file": self.zip_path.name,
                    }
                    datapoints.append(record)
            except Exception as e:
                print(f"  Error parsing {k_file}: {e}")

        self.datapoints = datapoints
        return datapoints


def _latest_filenames(manifest_path: Path):
    """Filenames of the latest-wins submissions (resolve_latest_submissions.py output)."""
    names = set()
    with open(manifest_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            url = row.get("url", "")
            if url:
                names.add(url.rstrip("/").split("/")[-1])
    return names


def _load_existing(path: Path, wanted: set):
    """Existing output rows split into (kept, dropped_sources, parsed_sources).

    kept = rows whose source_file is still wanted (they survive the merge);
    rows from files no longer in the manifest (stale resubmissions) are dropped."""
    kept, parsed, dropped = [], set(), set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                src = r.get("source_file", "")
                if src and src in wanted:
                    kept.append(r)
                    parsed.add(src)
                elif src:
                    dropped.add(src)
    return kept, dropped, parsed


def parse_all_reports(raw_dir: Path, codebook_path: Path, output_path: Path,
                      manifest_path: Path = None, incremental: bool = True):
    """Parse the latest-wins .zip submissions in raw_dir → combined long-form CSV.

    If manifest_path (manifest_latest.csv) is given, only the submissions it lists are
    parsed — older resubmissions present in raw/ are skipped (Resubmission-Policy).

    Incremental (default): rows of already-parsed source files are kept from the
    existing output, only new zips are parsed, and rows of source files that fell out
    of the manifest (superseded resubmissions) are dropped. Pass incremental=False
    (CLI: --full) to re-parse everything, e.g. after parser or codebook changes."""
    coverage = []  # report × template × reported (the "fehlt ≠ Null" matrix)
    zip_files = sorted(raw_dir.glob("*.zip"))

    latest = None
    if manifest_path and manifest_path.exists():
        latest = _latest_filenames(manifest_path)
        kept_zips = [z for z in zip_files if z.name in latest]
        skipped = len(zip_files) - len(kept_zips)
        zip_files = kept_zips
        if skipped:
            print(f"Resubmission-Policy: {skipped} ältere ZIP(s) übersprungen (nicht in manifest_latest.csv)")

    # Which source files stay valid in the merged output. Driven by the MANIFEST, not by
    # what happens to lie in raw/: a stateless run (CI) downloads only the new zips, so
    # rows of reports whose zip isn't on this machine must still survive the merge.
    # Only sources that fell out of the manifest (superseded resubmissions) are dropped.
    wanted = set(latest) if latest is not None else {z.name for z in zip_files}
    existing_rows, existing_cov = [], []
    if incremental:
        existing_rows, dropped, parsed_sources = _load_existing(output_path, wanted)
        cov_path = output_path.parent / "filing_indicators.csv"
        existing_cov, _, cov_sources = _load_existing(cov_path, wanted)
        # A submission can be parsed successfully and still yield no placeable facts
        # (e.g. modules whose templates carry only filing indicators). Those never show
        # up in the long-form, so the coverage matrix is the authoritative "already
        # seen" ledger — without it they would be re-parsed on every single run.
        parsed_sources |= cov_sources
        before = len(zip_files)
        zip_files = [z for z in zip_files if z.name not in parsed_sources]
        # a zip being (re)parsed must not keep its old coverage rows (would duplicate)
        reparse = {z.name for z in zip_files}
        existing_cov = [r for r in existing_cov if r.get("source_file") not in reparse]
        if dropped:
            print(f"Inkrementell: {len(dropped)} überholte Quelle(n) aus dem Bestand entfernt")
        print(f"Inkrementell: {before - len(zip_files)} bereits geparst, {len(zip_files)} neu zu parsen")
        if not zip_files and not dropped:
            print("✓ Nichts zu tun — Long-Form ist aktuell")
            return

    all_records = []
    print(f"Parsing {len(zip_files)} reports...")
    for i, zip_file in enumerate(zip_files, 1):
        try:
            parser = XBRLCSVParser(zip_file, codebook_path)
            metadata, datapoints = parser.parse()
            all_records.extend(datapoints)
            for template_id, reported in parser.filing_indicators.items():
                coverage.append({
                    "entityID": metadata.get("entityID", ""),
                    "refPeriod": metadata.get("refPeriod", ""),
                    "framework_version": metadata.get("framework_version", ""),
                    "template_id": template_id,
                    "reported": reported,
                    "source_file": zip_file.name,
                })
            print(f"  [{i:2d}/{len(zip_files)}] {zip_file.name[:50]:50s} {len(datapoints):6d} datapoints")
        except Exception as e:
            print(f"  [{i:2d}/{len(zip_files)}] {zip_file.name[:50]:50s} ERROR: {e}")

    LF_FIELDS = ["entityID", "refPeriod", "framework_version", "template_id",
                 "template_reported", "datapoint_code", "cell_row", "cell_col",
                 "open_axis_dims", "fact_value", "baseCurrency", "decimalsMonetary",
                 "source_file"]
    merged = existing_rows + all_records
    if merged:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LF_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(merged)
        print(f"\n✓ Long-form data: {output_path}")
        print(f"  Total records: {len(merged)} ({len(all_records)} neu, {len(existing_rows)} übernommen)")
    else:
        print("ERROR: No records extracted")

    # Coverage matrix — which templates each report declared reported / not reported.
    # This is the "fehlt ≠ Null" foundation: a template absent here was never declared,
    # reported=False means explicitly declared as not disclosed.
    COV_FIELDS = ["entityID", "refPeriod", "framework_version", "template_id",
                  "reported", "source_file"]
    merged_cov = existing_cov + coverage
    if merged_cov:
        cov_path = output_path.parent / "filing_indicators.csv"
        with open(cov_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(merged_cov)
        n_true = sum(1 for c in merged_cov if str(c["reported"]) == "True")
        print(f"✓ Filing indicators: {cov_path}")
        print(f"  {len(merged_cov)} rows ({n_true} reported / {len(merged_cov)-n_true} declared not-reported)")


if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parent.parent
    RAW_DIR = ROOT / "raw"
    CODEBOOK = ROOT / "codebook" / "dpm_codebook.csv"
    OUTPUT = ROOT / "processed" / "long_form_raw.csv"
    import sys
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    full = "--full" in sys.argv
    # Manifest to parse: CLI arg wins, else the CODIS parse manifest, else latest-wins.
    if args:
        MANIFEST = Path(args[0])
    else:
        MANIFEST = ROOT / "interim" / "edap_recon" / "manifest_parse.csv"
        if not MANIFEST.exists():
            MANIFEST = ROOT / "interim" / "edap_recon" / "manifest_latest.csv"

    parse_all_reports(RAW_DIR, CODEBOOK, OUTPUT, MANIFEST, incremental=not full)
