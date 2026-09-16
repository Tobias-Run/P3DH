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

  (d) DER SKALENFEHLER (#83). Bis dahin stand `reliable` bei 28 Zeilen auf
      `true`, deren Exposure um Größenordnungen zu klein ist — das war der
      Aufhänger jenes Issues. Der Beleg ist ING Bank Śląski:

          2025-06-30    39.863 EUR Gesamtexposure   domestic_share 0,9820
          2025-12-31    41.827.858.555 EUR          domestic_share 0,9858

      Faktor 10^6 im Betrag, die Quote praktisch unverändert. Genau das ist der
      Grund für die Spalte `vorbehalt` statt eines blossen Ja/Nein: ein
      gleichmässiger Skalenfehler **kürzt sich in jedem Verhältnis heraus**.
      `domestic_share`, `country_hhi` und `x28_share` bleiben gültig, nur
      `total_exposure_eur` ist unbrauchbar.

      Śląski ist zugleich der Grund, warum die Templateebene von
      `scale_flags.csv` mitgelesen wird: reportweit ist das Institut
      unauffällig (Versatz -0,15), skaliert ist genau `67.01.*` — also die
      Quelle dieser Datei.

Run:  python3 scripts/build_footprint.py
      (liest processed/scale_flags.csv, wenn vorhanden — erst
       scripts/build_report_scale.py)
"""

from pathlib import Path
import math
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


SCALE_FLAGS = ROOT / "processed" / "scale_flags.csv"


def lade_skalenmarken(pfad=None):
    """{(lei, scope, refPeriod): Urteil} — was #83 über diesen Report sagt.

    Beide Ebenen zählen, aber aus verschiedenen Gründen:

    **Report** — liegt der ganze Report um einen Faktor daneben, liegt sein
    CCyB1-Exposure mit. `verdacht` zählt hier mit: bei einem Betrag, der in
    keine Summe eingehen darf, ist ein Verdacht Vorbehalt genug.

    **Template** — und zwar nur `67.01.*`. Das ist die Quelle GENAU DIESER
    Datei, und es ist kein hypothetischer Fall: ING Bank Śląski ist reportweit
    unauffällig (Versatz -0,15) und hat trotzdem ein skaliertes CCyB1. Ein
    Filter nur auf die Reportebene hätte ihn durchgelassen.

    Fehlt die Datei, wird nichts markiert — die Prüfung verhält sich dann wie
    vor #83, statt stillschweigend jeden Report zu verdächtigen.
    """
    pfad = Path(pfad or SCALE_FLAGS)
    if not pfad.exists():
        return {}
    aus = {}
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("urteil") not in ("skaliert", "verdacht") or not r.get("lei"):
                continue
            if r.get("ebene") == "template" and not r.get("template_id", "").startswith(
                    TEMPLATE.split(".")[0] + "." + TEMPLATE.split(".")[1]):
                continue
            k = (r["lei"], r["scope"], r["refPeriod"])
            # `skaliert` schlägt `verdacht`, falls beide Ebenen zutreffen.
            if aus.get(k) != "skaliert":
                aus[k] = r["urteil"]
    return aus


# Wie viele Grössenordnungen die CCyB1-Summe unter dem TREA DESSELBEN Reports
# liegen darf, bevor sie unbrauchbar ist (#83 Punkt 3).
#
# Vier, und die Zahl ist gemessen: der eine echte Fall liegt bei −6,39, der
# nächste Wert der Verteilung bei −3,82 — und DER trägt bereits eine
# Skalenmarke. Der erste unmarkierte liegt bei −2,97. Zwischen Schwelle und
# legitimer Population liegt damit mehr als eine Grössenordnung.
TREA_ORDNUNGEN = 4.0


def unter_eigenem_trea(gesamt, trea, ordnungen=TREA_ORDNUNGEN):
    """Liegt die CCyB1-Summe um Grössenordnungen unter dem TREA DESSELBEN Reports?

    Das Issue schlägt den Peer-Median der Grössenklasse als Massstab vor. Der
    Vergleich INNERHALB des Reports ist der schärfere: er braucht keine
    Schichtung und ist gegen Institutsgrösse immun — ein kleines Institut hat
    ein kleines TREA und eine kleine CCyB1-Summe, das Verhältnis bleibt normal.

    Er fängt genau das, was `scale_flags.csv` NICHT fangen kann. Jene Marke
    beurteilt den Report als GANZES; ist er durchgehend skaliert, sind Zähler
    und Nenner gleichermassen zu klein und das Verhältnis unauffällig. Der eine
    Fall, der dem Skalendetektor entkam (Bank GPB International: CCyB1 meldet
    215,30 EUR, während KM1 im selben Report 1,52 Mrd trägt), ist ein
    TEMPLATE-lokaler Fehler — und nur hier sichtbar.

    Beide Prüfungen sind deshalb nötig und keine ersetzt die andere.
    """
    if not gesamt or not trea or gesamt <= 0 or trea <= 0:
        return False           # ohne Vergleichswert wird nichts behauptet
    return math.log10(gesamt / trea) < -ordnungen


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


def footprint(rows, home_country, skalenbefund="", trea=None):
    """rows: [(country_name, exposure_eur)] EINES Reports, x1 bereits entfernt.

    `country_name` ist None für den Residualbucket x28.
    `skalenbefund` ist das Urteil aus `processed/scale_flags.csv` (#83) — leer,
    wenn der Report unauffällig ist.
    `trea` ist der Gesamtrisikobetrag aus KM1 DESSELBEN Reports, falls
    vorhanden — der Massstab für die vierte Prüfung (#83 Punkt 3).

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
        # WELCHER Vorbehalt greift — nicht nur DASS einer greift. Die drei sind
        # verschieden schwer, und wer nur `reliable` liest, kann sie nicht
        # auseinanderhalten:
        #
        #   kein_heimatland  die Domestizitätsquote ist gar nicht bildbar
        #   residual         sie ist bildbar, aber der Grossteil des Exposures
        #                    ist keinem Land zugeordnet
        #   skala            die QUOTEN stimmen, der absolute Betrag nicht
        #
        # Der dritte ist der Grund für diese Spalte. Ein gleichmässiger
        # Skalenfehler kürzt sich in jedem Verhältnis heraus: `domestic_share`,
        # `country_hhi` und `x28_share` bleiben gültig, nur
        # `total_exposure_eur` ist unbrauchbar. Wer die Domestizität auswertet,
        # holt sich diese Reports also mit `vorbehalt == 'skala'` zurück; wer
        # Beträge summiert, darf das nicht.
        "vorbehalt": "|".join(filter(None, [
            "" if home else "kein_heimatland",
            "residual" if residual / grand_total > X28_UNRELIABLE else "",
            "skala" if skalenbefund else "",
            # Vierter Vorbehalt (#83 Punkt 3). Eigener Name, weil er etwas
            # ANDERES sagt als `skala`: dort ist der ganze Report verschoben
            # und die Quoten bleiben gültig, hier ist NUR dieses Template
            # verschoben — dann stimmen auch die Quoten nicht mehr gegen den
            # Rest des Reports.
            "unter_trea" if unter_eigenem_trea(grand_total, trea) else "",
        ])),
        # `reliable` sagt, was sein Name sagt: die Zeile ist im Ganzen zu
        # gebrauchen. Bis #83 blieb es bei skalierten Reports auf `true` — 28
        # Zeilen trugen ein um Grössenordnungen zu kleines Exposure und
        # meldeten sich als belastbar. Das war der Aufhänger des Issues.
        "reliable": (bool(home) and residual / grand_total <= X28_UNRELIABLE
                     and not skalenbefund
                     and not unter_eigenem_trea(grand_total, trea)),
        "skalenbefund": skalenbefund,
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

    marken = lade_skalenmarken()
    if marken:
        print(f"  Skalenmarken aus #83 geladen: {len(marken)} Reports")

    # Der Gesamtrisikobetrag aus KM1 DESSELBEN Reports — der Massstab für die
    # vierte Prüfung. Eigene Abfrage statt eines Joins: CCyB1 und KM1 haben
    # verschiedene Zeilenmengen, und ein Join würde Reports verlieren, die das
    # eine melden und das andere nicht.
    trea = {}
    for lei, scope, rp, v in ordered_query(con, """
        SELECT lei, scope, refPeriod, max(fact_value_eur)
        FROM p
        WHERE template_id = '61.00' AND cell_row = '0040' AND cell_col = '0010'
          AND fact_value_eur IS NOT NULL
        GROUP BY lei, scope, refPeriod
        ORDER BY lei, scope, refPeriod
    """, "KM1-TREA"):
        trea[(lei, scope, rp)] = v
    print(f"  KM1-TREA für den Grössenvergleich: {len(trea)} Reports")

    rows = []
    for key in sorted(reports):
        lei, scope, rp = key
        name, home = meta[key]
        fp = footprint(reports[key], home, marken.get(key, ""),
                       trea.get(key))
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
            "vorbehalt": fp["vorbehalt"],
            "skalenbefund": fp["skalenbefund"],
        })

    fields = ["lei", "scope", "refPeriod", "bank_name", "home_country",
              "largest_country", "n_countries", "total_exposure_eur",
              "domestic_share", "country_hhi", "x28_share", "reliable",
              "vorbehalt", "skalenbefund"]
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
    import collections
    gruende = collections.Counter(g for r in rows for g in r["vorbehalt"].split("|") if g)
    unreliable = len(rows) - len(ok)
    if unreliable:
        print(f"  ⚠ {unreliable} Reports mit Vorbehalt: "
              + "  ".join(f"{k}={v}" for k, v in sorted(gruende.items())))
        skal = [r for r in rows if "skala" in r["vorbehalt"]]
        if skal:
            print(f"    Die {len(skal)} mit Skalenbefund (#83) tragen GUELTIGE Quoten — "
                  f"nur ihr absoluter Betrag ist unbrauchbar. Fuer eine reine "
                  f"Domestizitaetsauswertung gehoeren sie wieder dazu.")

    print("\nAm stärksten international (belastbar, kleinste Domestizitätsquote):")
    for r in sorted(ok, key=lambda r: float(r["domestic_share"]))[:5]:
        print(f"  {r['bank_name'][:38]:40s} {r['home_country'][:12]:14s} "
              f"{float(r['domestic_share']):6.1%} heimisch · {r['n_countries']:3d} Länder · "
              f"HHI {r['country_hhi']}")


if __name__ == "__main__":
    main()
