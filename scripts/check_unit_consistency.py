"""Issue #9: Melden Institute Beträge in derselben Größenordnung?

Ausgangsbefund (Issue #4, Template 41.00): eine Minderheit der Institute
meldet in Millionen statt in Währungseinheiten, obwohl beide Lesarten für
sich plausibel aussehen — die Werte einer Zelle streuen dann bimodal über
~6 Größenordnungen (Faktor 10^6) statt kontinuierlich über die paar
Größenordnungen, die echte Bankgrößen-Unterschiede erklären.

Zwei unabhängige, sich ergänzende Prüfungen:

1. **Statistischer Gap-Scan** über ALLE monetären Zellen: sortiert man die
   log10-Beträge einer Zelle, ist eine einzelne Lücke von >=3 Größen-
   ordnungen mit >=3 Instituten auf jeder Seite ein Indiz für gemischte
   Einheiten — nicht für natürliche Größenstreuung (die ist kontinuierlich).
   Reine Heuristik: erkennt Kandidaten, entscheidet nichts automatisch.

2. **Label-Cross-Check**: `dpm_codebook.csv`-Spaltenlabels, die explizit auf
   eine Nicht-Basis-Einheit hinweisen ("Mln EUR", "Mio", "'000" …). Das ist
   das eigentliche Wurzelproblem: die Taxonomie deklariert für einzelne
   Spalten (nicht global) eine abweichende Einheit; ein Teil der Institute
   hält sich daran, der Rest meldet wie sonst üblich in Basis-Währungseinheiten.

Ergebnis dieser Prüfung für 41.00 und 45.00.A (beide „Gross carrying amount
(Mln EUR)"): **kein Parser-Bug** — das rohe XBRL-CSV trägt pro Fakt kein
scale/decimals-Attribut jenseits des global-deklarierten `decimalsMonetary`
(Präzision, keine Skalierung); das Roh-Sample bestätigt nur `datapoint,
factValue`-Spalten. Die Diskrepanz ist ein echtes Filer-Verhalten, keine
Ingestion-Lücke — und lässt sich institutsweise NICHT sicher korrigieren
(wir können nicht wissen, ob ein kleiner Wert „echt klein" oder „in Mio"
gemeint ist). Deshalb: Sperrliste statt Korrektur (`UNIT_AMBIGUOUS_TEMPLATES`,
verdrahtet in `build_zweig_b.py` als Spalte `unit_ambiguous`).

Lauf:  python3 scripts/check_unit_consistency.py
Out:   interim/unit_consistency_report.csv
"""

from pathlib import Path
import csv
import math
import sys

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
CODEBOOK = ROOT / "codebook" / "dpm_codebook.csv"
REPORT = ROOT / "interim" / "unit_consistency_report.csv"

MIN_GAP = 3.0     # Größenordnungen: >= das ist verdächtig, natürliche Bankgrößen-
                  # Streuung ist kontinuierlich, keine scharfe Lücke.
MIN_SIDE = 3      # Institute auf jeder Seite der Lücke, sonst zählt ein einzelner
                  # Ausreißer (eine sehr große/kleine Bank) fälschlich als "Lücke".

# Templates mit einem Spaltenlabel, das explizit eine Nicht-Basis-Einheit
# nennt ("Mln EUR"). Kuratiert aus einem Scan von dpm_codebook.csv (siehe
# find_label_ambiguous_templates) plus manueller Sichtprüfung — beide zeigen
# das bimodale bzw. auffällig breite Verteilungsmuster (siehe Docstring).
# Betrifft alle monetären Spalten des Templates (die "of which"-Spalten sind
# Aufschlüsselungen derselben Größe, tragen die Einheit implizit mit).
UNIT_AMBIGUOUS_TEMPLATES = {"41.00", "45.00.A"}

UNIT_LABEL_PATTERNS = ["mln", "mio", "million", "'000", "thousand"]


def gap_scan(values_by_cell):
    """Reine Funktion: {cell_key: [werte]} -> Liste verdächtiger Zellen.

    cell_key ist ein beliebiges hashbares Tupel (z. B. (template,row,col)).
    Verdächtig: größte Lücke zwischen sortierten log10(|wert|) >= MIN_GAP,
    mit mindestens MIN_SIDE Werten auf jeder Seite.
    """
    flagged = []
    for key, values in values_by_cell.items():
        logs = sorted(math.log10(abs(v)) for v in values if v)
        if len(logs) < 2 * MIN_SIDE:
            continue
        max_gap, gap_at = 0.0, -1
        for i in range(1, len(logs)):
            g = logs[i] - logs[i - 1]
            if g > max_gap:
                max_gap, gap_at = g, i
        below, above = gap_at, len(logs) - gap_at
        if max_gap >= MIN_GAP and below >= MIN_SIDE and above >= MIN_SIDE:
            flagged.append({
                "key": key, "gap": max_gap, "n": len(logs),
                "below": below, "above": above,
                "min_log10": logs[0], "max_log10": logs[-1],
            })
    flagged.sort(key=lambda f: -f["gap"])
    return flagged


def find_label_ambiguous_templates(codebook_rows):
    """Templates, deren Spaltenlabel eine Nicht-Basis-Einheit nennt.

    codebook_rows: Iterable von Dicts mit mind. 'template', 'col_label'.
    Liefert {template_code: {matched_labels}} — reine Funktion, testbar ohne Datei.
    """
    hits = {}
    for r in codebook_rows:
        label = (r.get("col_label") or "").lower()
        if any(p in label for p in UNIT_LABEL_PATTERNS):
            hits.setdefault(r.get("template", ""), set()).add(r.get("col_label", ""))
    return hits


def _load_codebook_rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    import duckdb

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt — erst build_zweig_b.py")
        return 2
    if not CODEBOOK.exists():
        print(f"ERROR: {CODEBOOK} fehlt")
        return 2

    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT template_id, cell_row, cell_col, MAX(col_label), MAX(row_label),
               LIST(fact_value)
        FROM '{PARQUET}'
        WHERE data_type='monetary' AND fact_value IS NOT NULL AND fact_value <> 0
        GROUP BY 1, 2, 3
        HAVING COUNT(DISTINCT lei) >= {2 * MIN_SIDE}
    """).fetchall()

    values_by_cell = {(t, r, c): vals for t, r, c, _, _, vals in rows}
    labels = {(t, r, c): (cl, rl) for t, r, c, cl, rl, _ in rows}

    flagged = gap_scan(values_by_cell)

    codebook_rows = _load_codebook_rows(CODEBOOK)
    label_hits = find_label_ambiguous_templates(codebook_rows)

    print(f"Zellen geprüft: {len(values_by_cell)} (monetär, >= {2*MIN_SIDE} Institute)")
    print(f"Statistisch auffällig (Lücke >= {MIN_GAP:.0f} Größenordnungen): {len(flagged)}")
    print(f"\nTemplates mit 'Mln EUR'/'Mio'-Spaltenlabel im Codebook: {len(label_hits)}")
    for tmpl, lbls in sorted(label_hits.items()):
        print(f"  {tmpl:12s} {sorted(lbls)[0][:55]}")

    with open(REPORT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["template_id", "cell_row", "cell_col", "col_label", "row_label",
                    "gap_orders_of_magnitude", "n_institutes", "n_below_gap", "n_above_gap",
                    "min_log10", "max_log10", "label_flags_unit"])
        for fl in flagged:
            t, r, c = fl["key"]
            cl, rl = labels.get((t, r, c), ("", ""))
            w.writerow([t, r, c, cl, rl, f"{fl['gap']:.2f}", fl["n"], fl["below"], fl["above"],
                       f"{fl['min_log10']:.2f}", f"{fl['max_log10']:.2f}",
                       t in UNIT_AMBIGUOUS_TEMPLATES])

    print(f"\n→ Report: {REPORT.relative_to(ROOT)}")
    print(f"\nSperrliste (nicht automatisch korrigiert, siehe Docstring): {sorted(UNIT_AMBIGUOUS_TEMPLATES)}")
    print("  verdrahtet in build_zweig_b.py als Spalte 'unit_ambiguous'")

    top = flagged[:10]
    if top:
        print("\nTop-10 auffällige Zellen (nicht automatisch gesperrt — zur Sichtprüfung):")
        for fl in top:
            t, r, c = fl["key"]
            cl, _ = labels.get((t, r, c), ("", ""))
            print(f"  {t:10s} r{r} c{c}  Lücke={fl['gap']:.1f}  n={fl['n']:4d}  {str(cl)[:45]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
