"""Zerlegt einen EDAP-Submission-Dateinamen/-URL in Manifest-Felder.
Schema:  {LEI}.{CON|IND}_{Land}_PILLAR3{Modul}_CODIS_{Stichtag}_{Timestamp}.zip
Framework-Version steht NICHT im Namen -> aus reports/report.json (extends) lesen.
"""
import re
import sys

PAT = re.compile(
    r"(?P<lei>[A-Z0-9]+)\."
    r"(?P<consolidation>CON|IND)_"
    r"(?P<country>[A-Z]{2})_"
    r"PILLAR3(?P<module>\d+)_"
    r"(?P<framework_family>CODIS)_"
    r"(?P<refdate>\d{4}-\d{2}-\d{2})_"
    r"(?P<submission_ts>\d+)\.zip$"
)


def parse(name_or_url: str) -> dict:
    name = name_or_url.rsplit("/", 1)[-1]
    m = PAT.search(name)
    if not m:
        raise ValueError(f"Dateiname passt nicht zum Schema: {name}")
    d = m.groupdict()
    d["filename"] = name
    if name_or_url.startswith("http"):
        d["source_url"] = name_or_url
    return d


if __name__ == "__main__":
    import json
    for arg in sys.argv[1:]:
        print(json.dumps(parse(arg), ensure_ascii=False))
