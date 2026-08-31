"""Build the parse manifest: union of the original latest-wins set and the random
sample, filtered to XBRL-CSV report packages.

All Pillar 3 XBRL modules share the same package structure (reports/k_*.csv,
FilingIndicators.csv, parameters.csv) and are covered by the DPM codebook —
CODIS, MRELTLACDIS (K_90/91), REMDIS (K_30), FINDIS, IRRBBDIS, ESGDIS, GSIIDIS.
Excluded are only the *DISDOCS packages: those contain the banks' qualitative
Pillar 3 PDF reports, not XBRL-CSV (candidate for a separate PDF index later).

Output: interim/edap_recon/manifest_parse.csv — consumed by xbrl_csv_parser.py.
"""

from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent.parent
RECON = ROOT / "interim" / "edap_recon"
SOURCES = [RECON / "manifest_full.csv",     # Voll-Katalog (alle Stichtage)
           RECON / "manifest_latest.csv", RECON / "manifest_sample.csv",
           RECON / "manifest_wave.csv"]   # full reference-date waves (e.g. 2025-12-31)
OUT = RECON / "manifest_parse.csv"

# "latest wins" (README, Arbeitsprinzip 5) muss HIER greifen, nicht erst beim
# Parsen: die Wellen- und Voll-Kataloge listen jede je gesehene Einreichung,
# inklusive überholter Fassungen. Ohne diese Reduktion lädt ein full_reparse
# 1.963 ZIPs, von denen 1.097 ältere Resubmissions sind, die anschliessend
# verworfen werden — mehr Downloads als der vollständige Bestand (1.739)
# überhaupt braucht.
GROUP_KEYS = ("lei", "consolidation", "module", "refdate")


def report_type(url):
    """CODIS / FINDIS / ESGDIS / IRRBBDIS / REMDIS / ... aus dem Dateinamen.

    ⚠️ Die Spalte `module` reicht als Schlüssel NICHT: sie trägt nur den
    numerischen Modulcode (020000 = RF 4.1, 020100 = 4.2), und unter EINEM
    Code liegen mehrere fachlich verschiedene Meldungen. Beispiel aus dem
    Katalog — (0W2PZJM8XOY22M4GG883, CON, 020000, 2025-06-30) enthält CODIS,
    ESGDIS und FINDIS als drei eigenständige Einreichungen. Ohne den Typ im
    Schlüssel würde "latest wins" zwei davon als überholte Resubmissions
    verwerfen und damit echten Bestand löschen (gemessen: 1.091 von 1.946
    Quelldateien).

    Dateiname: <LEI>.<CON|IND>_<LAND>_PILLAR3<modul>_<TYP>_<stichtag>_<ts>.zip
    """
    parts = url.rsplit("/", 1)[-1].split("_")
    return parts[3] if len(parts) > 3 else ""


def latest_wins(rows):
    """Reine Funktion: eine Zeile je (lei, consolidation, module, refdate,
    Berichtstyp) — die mit dem höchsten submission_ts. Eingabereihenfolge egal."""
    best = {}
    for r in rows:
        key = tuple(r[k] for k in GROUP_KEYS) + (report_type(r["url"]),)
        cur = best.get(key)
        if cur is None or r["submission_ts"] > cur["submission_ts"]:
            best[key] = r
    return sorted(best.values(), key=lambda r: r["url"])


def main():
    rows, seen = [], set()
    for src in SOURCES:
        if not src.exists():
            continue
        with open(src, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                # DISDOCS sind die qualitativen PDF-Berichte, kein XBRL-CSV.
                if "DISDOCS" in r["url"] or r["url"] in seen:
                    continue
                seen.add(r["url"])
                rows.append(r)

    kept = latest_wins(rows)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kept[0].keys())
        w.writeheader()
        w.writerows(kept)

    leis = {r["lei"] for r in kept}
    reports = {(r["lei"], r["consolidation"], r["refdate"]) for r in kept}
    print(f"✓ {OUT}")
    print(f"  {len(kept)} XBRL-Submissions · {len(leis)} Institute · {len(reports)} Reports")
    print(f"  ({len(rows) - len(kept)} überholte Resubmissions ausgeschlossen)")


if __name__ == "__main__":
    main()
