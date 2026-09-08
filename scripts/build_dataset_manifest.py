"""Datensatz-Manifest neben dem Parquet (#20).

## Warum das nicht optional ist

Der `data`-Branch wird force-gepusht und trägt genau EINEN Commit. Er hat keine
Historie: jeder Lauf ersetzt den vorigen Stand vollständig. Ein Parquet ohne
beiliegendes Manifest ist damit ein Datensatz ohne Herkunft — man kann ihm nicht
ansehen, aus welchem Code, welchem Codebook und welchem Katalogstand er entstanden
ist, und zwei Downloads von verschiedenen Tagen sind nicht unterscheidbar.

Alle Zahlen werden aus dem Parquet GEZÄHLT, nicht eingetragen. Eine Kennzahl, die
man von Hand pflegt, ist eine Kennzahl, die irgendwann lügt — genau das ist
`SESSION_STATUS.md` passiert.

Ausgabe: `processed/long/manifest.json`, deterministisch (sortierte Schlüssel),
mitpubliziert von `publish_data_branch.sh`.
"""

from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess

import duckdb

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
FINGERPRINT = ROOT / "processed" / "codebook_fingerprint.txt"
CODEBOOK = ROOT / "codebook" / "dpm_codebook.csv"
CATALOGUE = ROOT / "interim" / "edap_recon" / "manifest_full.csv"
OUT = PARQUET.parent / "manifest.json"

SOURCE = {
    "name": "EBA Pillar 3 Data Hub",
    "portal": "https://edap-public.eba.europa.eu/Report/index/MTE1",
    "overview": "https://www.eba.europa.eu/risk-and-data-analysis/pillar-3-data-hub",
    "rights": ("Die Offenlegungsdaten stammen von der Europäischen "
               "Bankenaufsichtsbehörde (EBA) und sind gesondert zu zitieren. "
               "Siehe DISCLAIMER.md — die MIT-Lizenz dieses Repositories deckt "
               "den Datensatz NICHT ab."),
}


def _git(*args, default=""):
    """Git-Angaben sind Beiwerk: ein Manifest ohne Commit ist besser als keins."""
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args],
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return default


def _rows(path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return sum(1 for _ in fh) - 1


def counts(con):
    """Eine Abfrage je Kennzahl — lesbar wichtiger als schnell (läuft einmal)."""
    one = lambda q: con.execute(q).fetchone()[0]  # noqa: E731
    return {
        "facts": one("SELECT count(*) FROM p"),
        "reports": one("SELECT count(DISTINCT (entityID, scope, refPeriod)) FROM p"),
        "institutions": one("SELECT count(DISTINCT lei) FROM p"),
        "countries": one("SELECT count(DISTINCT country) FROM p WHERE country IS NOT NULL"),
        "templates": one("SELECT count(DISTINCT template_id) FROM p"),
        "datapoints": one("SELECT count(DISTINCT datapoint_code) FROM p"),
        "facts_without_row": one("SELECT count(*) FROM p WHERE cell_row IS NULL OR cell_row = ''"),
        "monetary_facts_eur": one("SELECT count(*) FROM p WHERE fact_value_eur IS NOT NULL"),
    }


def breakdowns(con):
    rows = lambda q: [list(r) for r in con.execute(q).fetchall()]  # noqa: E731
    return {
        "reference_dates": rows(
            "SELECT refPeriod, count(*) FROM p GROUP BY 1 ORDER BY 1"),
        "framework_versions": rows(
            "SELECT framework_version, count(*) FROM p GROUP BY 1 ORDER BY 1"),
        "currencies": rows(
            "SELECT currency, count(*) FROM p WHERE currency IS NOT NULL "
            "GROUP BY 1 ORDER BY 2 DESC, 1"),
    }


def schema(con):
    return [{"column": n, "type": t} for n, t, *_ in
            con.execute("DESCRIBE SELECT * FROM p").fetchall()]


def build():
    if not PARQUET.exists():
        raise SystemExit(f"kein Parquet unter {PARQUET} — erst build_zweig_b.py laufen lassen")

    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM '{PARQUET.as_posix()}'")

    fingerprint = (FINGERPRINT.read_text(encoding="utf-8").strip()
                   if FINGERPRINT.exists() else None)

    manifest = {
        "dataset": "P3DH — EBA Pillar 3 Offenlegungen, aufgelöst und normalisiert",
        # Der einzige Zeitstempel, der hier hingehört: wann DIESER Bestand
        # gebaut wurde. Er bricht die Byte-Gleichheit zweier Läufe — bewusst.
        # Der `data`-Branch hat keine Historie; ohne diese Angabe sind zwei
        # Downloads von verschiedenen Tagen nicht unterscheidbar.
        "generated_at_utc": datetime.now(timezone.utc)
                            .replace(microsecond=0).isoformat(),
        "generator": {
            "repository": "https://github.com/Tobias-Run/P3DH",
            "commit": _git("rev-parse", "HEAD") or None,
            "commit_short": _git("rev-parse", "--short", "HEAD") or None,
            "commit_date_utc": _git("log", "-1", "--format=%cI") or None,
            "describe": _git("describe", "--tags", "--always") or None,
        },
        "source": SOURCE,
        "coverage": counts(con),
        "breakdown": breakdowns(con),
        "provenance": {
            "catalogue_submissions": _rows(CATALOGUE),
            "codebook_rows": _rows(CODEBOOK),
            "codebook_sha256": fingerprint,
        },
        "schema": schema(con),
        "documentation": "docs/datensatz.md",
        "known_limitations": "docs/datensatz.md#bekannte-einschränkungen",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False,
                              sort_keys=True) + "\n", encoding="utf-8")

    c = manifest["coverage"]
    print(f"✓ {OUT}")
    print(f"  {c['facts']:,} Fakten · {c['reports']:,} Reports · "
          f"{c['institutions']:,} Institute · {c['templates']:,} Templates")
    print(f"  Commit {manifest['generator']['commit_short']} · "
          f"Codebook {(fingerprint or 'unbekannt')[:12]}")
    return manifest


if __name__ == "__main__":
    build()
