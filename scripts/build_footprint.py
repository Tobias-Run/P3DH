"""Issue #12: Footprint-Kennzahlen je Institut aus dem Länder-Exposure (CCyB1).

Erzeugt `processed/footprint.csv` mit je (LEI, Konsolidierungskreis, Stichtag):

    domestic_share      Heimatland-Exposure / Gesamt
    country_hhi         Herfindahl über die Länderanteile (benannte Länder)
    n_countries         Zahl der benannten Länder
    x28_share           Anteil im Residualbucket "übrige Länder" -> QUALITÄTSFLAG
    total_exposure_eur  Bezugsgröße, in EUR normalisiert

Das ist eine Achse, die EDAP nicht anbietet: dort liegt ein Bank-ZIP neben dem
anderen, ein Quervergleich über Institute existiert nicht.

WARUM DAS ERST JETZT GEHT. `open_axis_country` gab es schon länger, aber die
Fakten trugen keine SPALTE — CCyB1 hat 13 davon, und sie mischen Exposure
(c0010-c0060), RWEA (c0070-c0110) und Prozentwerte (c0120/c0130). Ohne
Spaltenzuordnung hätte eine Summe Beträge mit Puffersätzen addiert. Seit #56
(offene Zeilenachse) und dem Label-Join steht fest, dass

    c0060 = "f Total exposure value"

die richtige und einzige Bezugsgröße ist. Ebenfalls erst dadurch tragen die
104.584 CCyB1-Beträge ein `data_type='monetary'` und damit `fact_value_eur` —
ohne das hätte der Vergleich PLN gegen EUR gestellt.

DREI FALLEN, an den Daten geprüft (Zahlen aus dem aktuellen Bestand):

  (a) `x1` ist die SUMMENZEILE, kein Land. Median x1/(Rest) = 1,0000 über 137
      Reports. Mitsummieren verdoppelt das Gesamtexposure.
  (b) `x28` ist ein Residualbucket ("übrige Länder"). Median-Anteil 0,5 %, aber
      13 Reports liegen über 30 % und 9 über 90 % — dort ist die
      Domestizitätsquote wertlos, weil das Exposure gar nicht benannt ist.
      Deshalb wandert x28 in den NENNER (es ist echtes Exposure), zählt aber
      nicht als Land, und `x28_share` steht als Flag daneben.
  (c) `entity_meta.country` sagt "Czech", `geo_names.csv` sagt "Czechia".
      8 Institute; ohne Normalisierung fallen die tschechischen Banken still
      auf 0 % Heimatanteil.

Run:  python3 scripts/build_footprint.py
"""

from pathlib import Path
import csv
import sys

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from determinism import ordered_query  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
OUT = ROOT / "processed" / "footprint.csv"

TEMPLATE = "67.01.A"          # CCyB1 — geografische Verteilung der Risikopositionen
EXPOSURE_COL = "0060"         # "f Total exposure value"
TOTAL_ROW = "x1"              # Summenzeile, KEIN Land
RESIDUAL_ROW = "x28"          # "übrige Länder" — Exposure ohne Länderangabe

# Ab hier ist die Domestizitätsquote nicht mehr aussagekräftig: der überwiegende
# Teil des Exposures ist gar keinem Land zugeordnet.
X28_UNRELIABLE = 0.30

# Namensabweichungen zwischen entity_meta.country (Herkunft: EBA-Stammdaten) und
# geo_names.csv (ISO 3166-1). Bewusst eine kleine Liste im Code statt einer
# Tabelle — heute ist genau ein Name betroffen. Wächst sie, gehört sie nach
# codebook/ als eigene Datei.
COUNTRY_ALIAS = {
    "Czech": "Czechia",
}


def normalize_country(name):
    """Heimatland-Name auf die Schreibweise von geo_names.csv bringen."""
    return COUNTRY_ALIAS.get((name or "").strip(), (name or "").strip())


def hhi(values):
    """Herfindahl-Index über Exposure-Beträge -> 0..1.

    Misst Konzentration sauberer als die reine Länderzahl: 30 Länder mit 95 %
    in einem davon sind nicht diversifiziert. 1,0 = alles in einem Land.
    Negative Beträge (Nettopositionen im Handelsbuch) gehen als Betrag ein —
    für die Konzentration zählt die Größe der Position, nicht ihr Vorzeichen.
    """
    weights = [abs(v) for v in values if v]
    total = sum(weights)
    if not total:
        return None
    return sum((w / total) ** 2 for w in weights)


def footprint(rows, home_country):
    """rows: [(country_name, exposure_eur)] EINES Reports, x1 bereits entfernt.

    `country_name` ist None für den Residualbucket x28.
    Liefert None, wenn kein verwertbares Exposure vorliegt — kein Wert ist
    besser als ein aus Null gerechneter (Arbeitsprinzip 3).
    """
    named = [(c, v) for c, v in rows if c and v]
    residual = sum(abs(v) for c, v in rows if not c and v)
    named_total = sum(abs(v) for _, v in named)
    grand_total = named_total + residual
    if not grand_total:
        return None

    home = normalize_country(home_country)
    domestic = sum(abs(v) for c, v in named if c == home)

    # Größtes Land mitführen. Es weicht bei 67 von 377 Reports vom Sitzland ab,
    # und die Gründe sind verschieden: Holdingsitz (Bank of Cyprus ist in Irland
    # registriert, das Geschäft liegt in Zypern), echte Auslandsdominanz
    # (Santander: UK vor Spanien) — und Meldefehler (BBVA meldet 2025-12-31
    # 190,6 Mrd unter Dänemark, wo im Vorquartal 188,8 Mrd unter Spanien
    # standen). Ohne diese Spalte sähe man in allen drei Fällen nur eine
    # niedrige Domestizitätsquote und wüsste nicht, warum.
    by_country = {}
    for c, v in named:
        by_country[c] = by_country.get(c, 0.0) + abs(v)
    largest = max(sorted(by_country), key=by_country.get) if by_country else ""

    return {
        "n_countries": len(by_country),
        "total_exposure_eur": grand_total,
        # Nenner schließt x28 ein: das Exposure existiert, wir wissen nur nicht wo.
        "domestic_share": domestic / grand_total,
        "country_hhi": hhi([v for _, v in named]),
        "x28_share": residual / grand_total,
        "home_country": home,
        "largest_country": largest,
        # Ohne Heimatland in den Meldedaten ist die Quote nicht interpretierbar
        # (nicht "0 %" — das wäre eine Aussage, die wir nicht treffen können).
        "reliable": bool(home) and residual / grand_total <= X28_UNRELIABLE,
    }


def main():
    if not PARQUET.exists():
        sys.exit(f"missing {PARQUET} — run scripts/build_zweig_b.py first")
    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM '{PARQUET}'")

    reports, meta = {}, {}
    for lei, scope, rp, name, country, land, val in ordered_query(con, f"""
        SELECT lei, scope, refPeriod, bank_name, country,
               open_axis_country, fact_value_eur
        FROM p
        WHERE template_id = '{TEMPLATE}' AND cell_col = '{EXPOSURE_COL}'
          AND fact_value_eur IS NOT NULL
          AND cell_row <> '{TOTAL_ROW}'          -- Summenzeile, siehe Docstring (a)
        ORDER BY lei, scope, refPeriod, open_axis_country, fact_value_eur,
                 bank_name, country
    """, "CCyB1-Länderexposure"):
        key = (lei, scope, rp)
        reports.setdefault(key, []).append((land, val))
        meta.setdefault(key, (name or "", country or ""))

    rows = []
    for key in sorted(reports):
        lei, scope, rp = key
        name, home = meta[key]
        fp = footprint(reports[key], home)
        if fp is None:
            continue
        rows.append({
            "lei": lei, "scope": scope, "refPeriod": rp, "bank_name": name,
            "home_country": fp["home_country"],
            "largest_country": fp["largest_country"],
            "n_countries": fp["n_countries"],
            "total_exposure_eur": f"{fp['total_exposure_eur']:.2f}",
            "domestic_share": f"{fp['domestic_share']:.4f}",
            "country_hhi": "" if fp["country_hhi"] is None else f"{fp['country_hhi']:.4f}",
            "x28_share": f"{fp['x28_share']:.4f}",
            "reliable": "true" if fp["reliable"] else "false",
        })

    fields = ["lei", "scope", "refPeriod", "bank_name", "home_country",
              "largest_country", "n_countries", "total_exposure_eur",
              "domestic_share", "country_hhi", "x28_share", "reliable"]
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    ok = [r for r in rows if r["reliable"] == "true"]
    shares = sorted(float(r["domestic_share"]) for r in ok)
    print(f"✓ {OUT.relative_to(ROOT)}  ({len(rows)} Reports, {len({r['lei'] for r in rows})} Institute)")
    print(f"  belastbar (Heimatland bekannt, x28 <= {X28_UNRELIABLE:.0%}): {len(ok)}")
    if shares:
        print(f"  Domestizitätsquote  Median {shares[len(shares)//2]:.1%} · "
              f"über 90 % heimatzentriert: {sum(1 for s in shares if s > 0.9)}")
    unreliable = len(rows) - len(ok)
    if unreliable:
        print(f"  ⚠ {unreliable} Reports ohne belastbare Quote (Heimatland fehlt "
              f"oder Exposure überwiegend im Residualbucket)")

    print("\nAm stärksten international (belastbar, kleinste Domestizitätsquote):")
    for r in sorted(ok, key=lambda r: float(r["domestic_share"]))[:5]:
        print(f"  {r['bank_name'][:38]:40s} {r['home_country'][:12]:14s} "
              f"{float(r['domestic_share']):6.1%} heimisch · {r['n_countries']:3d} Länder · "
              f"HHI {r['country_hhi']}")


if __name__ == "__main__":
    main()
