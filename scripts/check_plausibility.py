"""Issue #17: Plausibilitäts-Profil je Institut — Werte gegen die Population.

Ergänzt den Gap-Scan aus #9, der einen strukturellen blinden Fleck hat: er sucht
eine SCHARFE bimodale Lücke (>=3 Größenordnungen, >=3 Institute je Seite). Wo die
Werte über viele Größenordnungen VERSCHMIERT streuen, findet er nichts. Der
schlimmste Fall im Bestand fällt genau dadurch: REM1 `30.01` r0020/c0020 streut
über 14 Größenordnungen (Rabobank meldet 11,7 Bio. EUR fixe Vergütung für 9
Vorstandsmitglieder) und steht NICHT in `interim/unit_consistency_report.csv`.

Drei Verfahren, bewusst unterschiedlich verwundbar:

1. **cell_outlier** — robuster Ausreißer gegen die eigene Zellpopulation:
   Median und MAD auf log10(|Wert|), geflaggt ab z > OUTLIER_Z. Der Maßstab
   ist die Zelle selbst, nicht eine globale Konstante. Eine globale Schranke
   ("Prozente <= 1") wäre falsch: Zellen unterscheiden sich legitim in ihrer
   Konvention, und echte Bankgrößen-Unterschiede erklären im Median 3,76
   Größenordnungen Streuung.

   Zwei Eigenschaften dieses Tests sind hart erarbeitet und dürfen nicht
   stillschweigend zurückgedreht werden:

   a) **Nur die OBERE Flanke.** Die untere Flanke einer Exposure-Verteilung
      ist natürlich: sehr viele Institute haben nahe null Exposure zu einer
      gegebenen Kategorie, und ein Betrag von 100 EUR in einer Zelle mit
      Median 10^8 ist eine kleine Position, kein Meldefehler. Symmetrisch
      geprüft lagen 9.750 von 12.744 Befunden UNTER dem Median, davon 2.645
      bei |Wert| < 1 Währungseinheit (Deutsche Bank meldet 1,7·10^-11 EUR —
      der Gleitkomma-Rest einer effektiven Null). Das ist Rauschen, kein
      Produkt. Die untere Flanke gehört zu den Ratio-Regeln (3), die dort
      mit fachlichem Wissen statt Statistik urteilen.

   b) **Monetäre Zellen werden in EUR verglichen** (`fact_value_eur`), nicht
      in Meldewährung. Sonst schlägt der Test auf die Währung an statt auf
      den Wert: HUF/EUR ~400 und NOK/EUR ~11,7 verschieben log10 um bis zu
      2,6 Größenordnungen, was bei einem typischen MAD von 0,4 bereits über
      der Schwelle liegt. Vorher stammten 43 % der Befunde von Nicht-EUR-
      Meldern, allein 858 von zwei norwegischen Instituten.

2. **cell_incoherent** — die Zelle SELBST ist unbrauchbar. Streut schon der
   Rumpf (p10..p90) über >= INCOHERENT_SPREAD Größenordnungen, ist keine
   Instituts-Zuschreibung mehr zu verantworten: dann ist unklar, welche Lesart
   die richtige ist, nicht welches Institut falsch liegt. Solche Zellen werden
   ausdrücklich OHNE Schuldzuweisung ausgewiesen und aus (1) ausgenommen.
   Belegbeispiel: `09.05` c0020 ("Of which exposures in default", als
   `percentage` typisiert) streut über 6,47 Größenordnungen bis 28,5 Mrd —
   303 Werte <= 1 gegen 316 > 1, also eine echte 50:50-Spaltung der Lesart.

3. **ratio** — fachlich begründete Korridore auf abgeleiteten Verhältnissen
   INNERHALB eines Reports (RATIO_RULES). Diese sind gegen genau die Fehler
   immun, die (1) und (2) plagen: meldet ein Institut durchgängig in Millionen,
   kürzt sich der Faktor im Quotienten heraus. Sie bringen dafür fachliches
   Wissen ein, das die Statistik nicht hat.

Schwellen sind an der beobachteten Verteilung geeicht, nicht geraten — siehe
die Konstanten unten.

**Kein Werturteil über Institute.** Das Ergebnis ist ein reproduzierbarer
Konsistenz-Check, der sagt "dieser Wert passt nicht zur Population", nicht
"dieses Institut meldet falsch". Ein Ausreißer kann eine korrekte Besonderheit
sein; die Entscheidung bleibt beim Leser.

Lauf:  python3 scripts/check_plausibility.py
Out:   interim/plausibility_cells.csv      (Zellstatistik, inkl. unbrauchbarer Zellen)
       interim/plausibility_findings.csv   (Einzelbefunde je Fakt)
       processed/quality_profile.csv       (Profil je Institut/Report)
"""

from pathlib import Path
import csv
import math
import sys

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
CELLS_OUT = ROOT / "interim" / "plausibility_cells.csv"
FINDINGS_OUT = ROOT / "interim" / "plausibility_findings.csv"
PROFILE_OUT = ROOT / "processed" / "quality_profile.csv"

# Mindestbesetzung einer Zelle, damit Median/MAD tragen. Unter ~20 Instituten
# verschiebt ein einzelner Ausreißer den Median selbst zu stark.
MIN_INSTITUTES = 20

# Ausreißer ab |robustem z| > 6. Konservativ: bei normalverteilten log-Werten
# entspräche das ~1 Fehlalarm auf 10^9. Wir wollen wenige, harte Befunde.
OUTLIER_Z = 6.0

# Zelle gilt als unbrauchbar, wenn schon ihr Rumpf (p10..p90) >= 6 Größen-
# ordnungen streut. Geeicht an der beobachteten Verteilung über 4.569 Zellen
# mit >= 20 Instituten: Median 3,76 · p75 4,45 · p90 5,12 · p95 5,85 · p99 7,05.
# 6,0 liegt oberhalb von p95 und entspricht exakt dem Faktor einer Einheiten-
# Verwechslung (10^6 = Millionen statt Währungseinheiten) — ist der Rumpf so
# breit wie eine volle Einheiten-Verwechslung, ist keine Zuschreibung sicher.
INCOHERENT_SPREAD = 6.0

# Schweregrad nach Abstand vom Zellmedian, in Größenordnungen. 6 = eine volle
# Einheiten-Verwechslung, 3 = Faktor 1000.
SEVERITY_HIGH = 6.0
SEVERITY_MID = 3.0


# --- Fachliche Ratio-Regeln ------------------------------------------------
# Deklarativ, damit neue Regeln ohne Codeänderung dazukommen. Jede Regel bildet
# innerhalb EINES Reports (lei, scope, refPeriod) und einer Spalte den Quotienten
# zweier Zeilen und prüft ihn gegen einen Korridor.
#
# REM1 (30.01/30.02): Zeile 0010 ist die Kopfzahl der "identified staff"
# (typisiert integer), Zeile 0020 die fixe Gesamtvergütung derselben Gruppe —
# der Quotient ist die Vergütung pro Kopf. Beobachtet über 1.324 Paare:
#   p25 46.500 · Median 142.516 · p75 305.537 EUR
# Der Korridor 1.000 .. 20.000.000 EUR ist bewusst weit ausserhalb dieser
# Perzentile gewählt: unten deckt er auch geringfügige Aufsichtsratsvergütungen
# ab, oben die höchstbezahlten Banker Europas. Was darunter oder darüber liegt,
# ist keine Gehaltsfrage mehr, sondern eine Einheitenfrage.
RATIO_RULES = [
    {
        "id": "rem_per_head",
        "templates": ("30.01", "30.02"),
        "numerator_row": "0020",     # Total fixed remuneration (monetary, EUR)
        "denominator_row": "0010",   # Number of identified staff (integer)
        "lo": 1_000.0,
        "hi": 20_000_000.0,
        "label": "Fixe Vergütung pro identifiziertem Mitarbeiter",
        "unit": "EUR",
    },
]


def cell_stats(values):
    """Robuste Kennzahlen einer Zellpopulation auf log10(|Wert|).

    values: Iterable numerischer Werte (Nullen und None werden ignoriert —
    log10(0) ist undefiniert, und eine gemeldete Null ist kein Größenindiz).

    Liefert None, wenn zu wenige verwertbare Werte übrig bleiben, sonst ein
    Dict mit n, median, mad, spread (p90-p10) und incoherent.
    """
    logs = sorted(math.log10(abs(v)) for v in values if v)
    n = len(logs)
    if n < MIN_INSTITUTES:
        return None
    mid = n // 2
    median = logs[mid] if n % 2 else (logs[mid - 1] + logs[mid]) / 2
    devs = sorted(abs(x - median) for x in logs)
    m = len(devs) // 2
    mad = devs[m] if len(devs) % 2 else (devs[m - 1] + devs[m]) / 2
    spread = logs[int(0.9 * (n - 1))] - logs[int(0.1 * (n - 1))]
    return {"n": n, "median": median, "mad": mad, "spread": spread,
            "incoherent": spread >= INCOHERENT_SPREAD}


def robust_z(value, stats):
    """Abstand ÜBER dem Zellmedian in robusten Standardabweichungen (MAD).

    Einseitig: Werte unterhalb des Medians liefern 0. Begründung im Modul-
    Docstring (1a) — die untere Flanke ist bei Exposure-Daten natürlich, ihre
    Prüfung gehört zu den fachlichen Ratio-Regeln.

    Bei mad == 0 (mehr als die Hälfte der Zelle trägt exakt denselben Betrag)
    ist der Quotient nicht definiert; wir weichen auf den reinen Abstand in
    Größenordnungen aus, damit eine solche Zelle nicht ALLE abweichenden Werte
    als unendlich auffällig meldet.
    """
    if not value:
        return 0.0
    d = math.log10(abs(value)) - stats["median"]
    if d <= 0:
        return 0.0
    scale = 1.4826 * stats["mad"]
    return d / scale if scale > 1e-9 else d


def severity(deviation_orders):
    if deviation_orders >= SEVERITY_HIGH:
        return "hoch"
    if deviation_orders >= SEVERITY_MID:
        return "mittel"
    return "niedrig"


def ratio_violations(rule, pairs):
    """Reine Funktion: prüft einen Korridor gegen Zähler/Nenner-Paare.

    pairs: Iterable von (key, numerator, denominator). key ist beliebig
    (typisch: (lei, scope, refPeriod, template_id, cell_col)).

    Liefert Befunde für Paare ausserhalb [lo, hi]. Nenner <= 0 wird
    übersprungen — eine Kopfzahl von 0 ist keine Plausibilitätsaussage über
    die Vergütung, sondern eine eigene (hier nicht behandelte) Frage.
    """
    out = []
    for key, num, den in pairs:
        if den is None or num is None or den <= 0:
            continue
        ratio = num / den
        if rule["lo"] <= ratio <= rule["hi"]:
            continue
        # Abstand zum verletzten Rand, in Größenordnungen — vergleichbar mit
        # dem Abstandsmaß der Zell-Ausreißer, damit ein Schweregrad über beide
        # Verfahren dasselbe bedeutet.
        bound = rule["lo"] if ratio < rule["lo"] else rule["hi"]
        dev = abs(math.log10(ratio / bound)) if ratio > 0 else SEVERITY_HIGH
        out.append({"key": key, "rule": rule["id"], "ratio": ratio,
                    "bound": bound, "deviation_orders": dev,
                    "severity": severity(dev)})
    return out


def _rel(path):
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def main():
    import duckdb

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt — erst scripts/build_zweig_b.py")
        return 2

    con = duckdb.connect()
    CELLS_OUT.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_OUT.parent.mkdir(parents=True, exist_ok=True)

    # --- 1/2: Zellpopulationen. Nur geschlossene Achsen: bei offenen Achsen
    # ist (template,row,col) keine Zelle, sondern ein ganzes Gitter je
    # Dimensionswert (67.01.A hätte sonst 57.502 "Werte einer Zelle").
    # `comparable`: monetäre Werte in EUR (sonst misst der Test die Meldewährung,
    # siehe Docstring 1b), alle anderen Typen sind einheitenfrei und gehen roh ein.
    # Monetäre Fakten ohne FX-Kurs fallen damit heraus — richtig so, sie sind
    # institutsübergreifend schlicht nicht vergleichbar.
    COMPARABLE = ("CASE WHEN data_type='monetary' THEN fact_value_eur "
                  "ELSE fact_value END")
    cells = {}
    rows = con.execute(f"""
        SELECT template_id, cell_row, cell_col,
               any_value(row_label), any_value(col_label), any_value(data_type),
               LIST({COMPARABLE})
        FROM '{PARQUET}'
        WHERE {COMPARABLE} IS NOT NULL AND {COMPARABLE} <> 0
          AND cell_row IS NOT NULL AND cell_row <> ''
          AND data_type IN ('monetary', 'percentage', 'decimal', 'integer')
        GROUP BY 1, 2, 3
        HAVING count(DISTINCT lei) >= {MIN_INSTITUTES}
    """).fetchall()
    labels = {}
    for t, r, c, rl, cl, dt, vals in rows:
        st = cell_stats(vals)
        if st:
            cells[(t, r, c)] = st
            labels[(t, r, c)] = (rl or "", cl or "", dt or "")

    coherent = {k: v for k, v in cells.items() if not v["incoherent"]}
    print(f"Zellen mit >= {MIN_INSTITUTES} Instituten: {len(cells):,}")
    print(f"  davon auswertbar (Rumpfstreuung < {INCOHERENT_SPREAD:.0f} Größenordnungen): {len(coherent):,}")
    print(f"  unbrauchbar — keine Zuschreibung: {len(cells)-len(coherent):,}")

    # --- Einzelbefunde: Ausreißer in auswertbaren Zellen
    findings = []
    for lei, scope, rp, bank, t, r, c, val in con.execute(f"""
        SELECT lei, scope, refPeriod, bank_name, template_id, cell_row, cell_col,
               {COMPARABLE}
        FROM '{PARQUET}'
        WHERE {COMPARABLE} IS NOT NULL AND {COMPARABLE} <> 0
          AND cell_row IS NOT NULL AND cell_row <> ''
    """).fetchall():
        st = coherent.get((t, r, c))
        if st is None:
            continue
        z = robust_z(val, st)
        if z <= OUTLIER_Z:
            continue
        dev = math.log10(abs(val)) - st["median"]
        findings.append({
            "lei": lei, "scope": scope, "refPeriod": rp, "bank_name": bank or "",
            "template_id": t, "cell_row": r, "cell_col": c,
            "rule": "cell_outlier", "value": val,
            "reference": 10 ** st["median"], "n_population": st["n"],
            "deviation_orders": dev, "severity": severity(dev),
        })

    # --- 3: fachliche Ratio-Regeln
    for rule in RATIO_RULES:
        tpls = ",".join(f"'{t}'" for t in rule["templates"])
        pairs, meta = [], {}
        for lei, scope, rp, bank, t, col, num, den in con.execute(f"""
            WITH num AS (
              SELECT DISTINCT lei, scope, refPeriod, template_id, cell_col,
                     any_value(bank_name) OVER (PARTITION BY lei) AS bank_name,
                     fact_value_eur AS v
              FROM '{PARQUET}'
              WHERE template_id IN ({tpls}) AND cell_row = '{rule["numerator_row"]}'
                AND fact_value_eur IS NOT NULL),
                 den AS (
              SELECT DISTINCT lei, scope, refPeriod, template_id, cell_col,
                     fact_value AS v
              FROM '{PARQUET}'
              WHERE template_id IN ({tpls}) AND cell_row = '{rule["denominator_row"]}'
                AND fact_value IS NOT NULL)
            SELECT num.lei, num.scope, num.refPeriod, num.bank_name,
                   num.template_id, num.cell_col, num.v, den.v
            FROM num JOIN den USING (lei, scope, refPeriod, template_id, cell_col)
        """).fetchall():
            key = (lei, scope, rp, t, col)
            pairs.append((key, num, den))
            meta[key] = bank or ""
        viol = ratio_violations(rule, pairs)
        print(f"\nRegel {rule['id']}: {len(pairs):,} Paare geprüft, {len(viol)} ausserhalb "
              f"[{rule['lo']:,.0f} .. {rule['hi']:,.0f}] {rule['unit']}")
        for v in viol:
            lei, scope, rp, t, col = v["key"]
            findings.append({
                "lei": lei, "scope": scope, "refPeriod": rp, "bank_name": meta[v["key"]],
                "template_id": t, "cell_row": rule["numerator_row"], "cell_col": col,
                "rule": rule["id"], "value": v["ratio"], "reference": v["bound"],
                "n_population": len(pairs),
                "deviation_orders": v["deviation_orders"], "severity": v["severity"],
            })

    # --- Ausgabe: Zellstatistik
    with open(CELLS_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["template_id", "cell_row", "cell_col", "row_label", "col_label",
                    "data_type", "n_values", "median_log10", "mad_log10",
                    "spread_p10_p90", "status"])
        for k in sorted(cells):
            st, (rl, cl, dt) = cells[k], labels[k]
            w.writerow([*k, rl, cl, dt, st["n"], f"{st['median']:.3f}",
                        f"{st['mad']:.3f}", f"{st['spread']:.2f}",
                        "unbrauchbar" if st["incoherent"] else "auswertbar"])

    # --- Ausgabe: Einzelbefunde
    findings.sort(key=lambda f: -f["deviation_orders"])
    with open(FINDINGS_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lei", "scope", "refPeriod", "bank_name", "template_id",
                    "cell_row", "cell_col", "rule", "value", "reference",
                    "n_population", "deviation_orders", "severity"])
        for fi in findings:
            w.writerow([fi["lei"], fi["scope"], fi["refPeriod"], fi["bank_name"],
                        fi["template_id"], fi["cell_row"], fi["cell_col"], fi["rule"],
                        f"{fi['value']:.6g}", f"{fi['reference']:.6g}",
                        fi["n_population"], f"{fi['deviation_orders']:.2f}",
                        fi["severity"]])

    # --- Ausgabe: Profil je Institut/Report
    # Rohe Befundzahlen sind als Vergleich unfair: wer 136 Templates meldet,
    # hat mehr Gelegenheiten aufzufallen als wer 4 meldet. Deshalb zusätzlich
    # die Rate je 1.000 tatsächlich PRÜFBARER Fakten (= Fakten in auswertbaren
    # Zellen; Fakten in unbrauchbaren Zellen waren nie im Test und dürfen den
    # Nenner nicht aufblähen).
    checked = {}
    for lei, scope, rp, t, r, c, n in con.execute(f"""
        SELECT lei, scope, refPeriod, template_id, cell_row, cell_col, count(*)
        FROM '{PARQUET}'
        WHERE {COMPARABLE} IS NOT NULL AND {COMPARABLE} <> 0
          AND cell_row IS NOT NULL AND cell_row <> ''
        GROUP BY 1, 2, 3, 4, 5, 6
    """).fetchall():
        if (t, r, c) in coherent:
            checked[(lei, scope, rp)] = checked.get((lei, scope, rp), 0) + n

    profile = {}
    for fi in findings:
        key = (fi["lei"], fi["scope"], fi["refPeriod"])
        p = profile.setdefault(key, {"bank_name": fi["bank_name"], "n": 0,
                                     "hoch": 0, "mittel": 0, "niedrig": 0,
                                     "templates": set(), "max_dev": 0.0})
        p["n"] += 1
        p[fi["severity"]] += 1
        p["templates"].add(fi["template_id"])
        p["max_dev"] = max(p["max_dev"], fi["deviation_orders"])

    with open(PROFILE_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lei", "scope", "refPeriod", "bank_name", "n_findings",
                    "n_hoch", "n_mittel", "n_niedrig", "n_facts_checked",
                    "findings_per_1000", "n_templates", "templates",
                    "max_deviation_orders"])
        for (lei, scope, rp), p in sorted(profile.items(), key=lambda kv: -kv[1]["n"]):
            nchk = checked.get((lei, scope, rp), 0)
            rate = f"{p['n'] / nchk * 1000:.2f}" if nchk else ""
            w.writerow([lei, scope, rp, p["bank_name"], p["n"], p["hoch"], p["mittel"],
                        p["niedrig"], nchk, rate, len(p["templates"]),
                        "|".join(sorted(p["templates"])), f"{p['max_dev']:.2f}"])

    n_reports = con.execute(
        f"SELECT count(*) FROM (SELECT DISTINCT lei, scope, refPeriod FROM '{PARQUET}')").fetchone()[0]
    print(f"\nBefunde: {len(findings):,} in {len(profile)} von {n_reports} Reports")
    for sev in ("hoch", "mittel", "niedrig"):
        print(f"  {sev:8s} {sum(1 for f in findings if f['severity']==sev):,}")

    print("\nTop-8 Befunde (größter Abstand zum Referenzwert):")
    for fi in findings[:8]:
        print(f"  {str(fi['bank_name'])[:34]:34s} {fi['template_id']:8s} "
              f"r{fi['cell_row']} c{fi['cell_col']}  {fi['rule']:13s} "
              f"{fi['deviation_orders']:5.1f} Größenordnungen")

    for path in (CELLS_OUT, FINDINGS_OUT, PROFILE_OUT):
        print(f"→ {_rel(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
