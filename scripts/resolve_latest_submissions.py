"""Phase 1.5: Resubmission-Policy "latest wins".

Liest den vollständigen Roh-Katalog (manifest_urls.csv, eine Zeile je gesehene
Submission) und reduziert ihn auf genau eine Zeile je Einreichung — die mit dem
höchsten submission_ts.

Was „eine Einreichung" heisst, steht in `submissions.py` und NICHT hier. Bis
#88 stand die Regel zweimal im Repo, und diese Fassung war die falsche: ihr
Schlüssel enthielt die Spalte `module` (den numerischen PILLAR3-Code) statt des
Modultyps und verwarf damit CODIS, ESGDIS und FINDIS desselben Instituts als
Korrekturfassungen voneinander — 38 % der Einreichungen, lautlos.

Der Roh-Katalog selbst bleibt unverändert (Audit-Trail); dieser Schritt
erzeugt eine abgeleitete, gefilterte Sicht.

⚠️ Diese Ausgabe ist NICHT der Satz, den die Pipeline parst. Sie übergibt
`manifest_parse.csv` (aus `build_parse_manifest.py`, das den vollen Katalog
liest). Wer von Hand herunterlädt oder parst, nimmt ebenfalls jene Datei — sie
ist der Default beider Skripte.
"""

from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from submissions import latest_wins  # noqa: E402

RECON_DIR = Path(__file__).resolve().parent.parent / "interim" / "edap_recon"
MANIFEST_IN = RECON_DIR / "manifest_urls.csv"
MANIFEST_OUT = RECON_DIR / "manifest_latest.csv"


def main():
    if not MANIFEST_IN.exists():
        print(f"ERROR: {MANIFEST_IN} fehlt — erst harvest_catalog.py ausführen")
        return

    with open(MANIFEST_IN, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    latest_rows = latest_wins(rows)
    behalten = {r["url"] for r in latest_rows}
    superseded = [r for r in rows if r["url"] not in behalten]

    with open(MANIFEST_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(latest_rows)

    print(f"Roh-Katalog: {len(rows)} Submissions, {len(latest_rows)} eigenständige "
          f"(Institut, Konsolidierung, Meldebereich, Modultyp, Stichtag)")
    print(f"→ {len(latest_rows)} aktuelle Submissions nach {MANIFEST_OUT}")
    if superseded:
        print(f"\n{len(superseded)} ältere Resubmission(en) ausgeschlossen:")
        for row in sorted(superseded, key=lambda r: r["url"]):
            print(f"  - {row['lei']}.{row['consolidation']}_{row['country']}_{row['refdate']}"
                  f"  (verworfen: {row['submission_ts']})")


if __name__ == "__main__":
    main()
