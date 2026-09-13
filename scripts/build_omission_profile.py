"""Ermessensausübung nach CRR Art. 432 messen (#43).

Ausgabe: processed/omission_profile.csv   (je Report)
         processed/omission_templates.csv (je Template × Klasse × Stichtag)

## Die Frage

Art. 432 CRR erlaubt, nicht wesentliche sowie proprietäre oder vertrauliche
Angaben wegzulassen. Zu diesem Ermessensspielraum gibt es Leitlinien, aber keine
auffindbare empirische Arbeit, die misst, wie er ausgeübt wird — weil man dafür
je Institut wissen müsste, was es WEGLÄSST, und das aus einem PDF nicht
rekonstruierbar ist.

`processed/filing_indicators.csv` ist genau diese Aussage, vom Melder selbst,
Template für Template: 64.898 Zeilen, davon 23.525 „offengelegt" und 41.373
„nicht offengelegt".

## Warum die naheliegende Kennzahl den Meldekalender misst

Die Rohquote „nicht offengelegt / deklariert" ist unbrauchbar. Gemessen:

    2025-06-30   35,4 % offengelegt
    2025-09-30   11,9 %
    2025-12-31   45,1 %
    2026-03-31   12,9 %

Das ist kein Verhalten, das ist die Offenlegungsfrequenz. `19.03` (OR3) steht an
drei Stichtagen bei rund 2 % und am 2025-12-31 bei 53,9 % — jährlich. `74.00`
(LIQ2) steht bei 62,8 / 2,5 / 62,9 / 2,8 — halbjährlich. `61.00` (KM1) bei rund
95 % an jedem Stichtag — vierteljährlich.

Wer über Stichtage hinweg mittelt, misst, welche Stichtage ein Institut meldet.

## Und warum die zweitnaheliegende die Institutsgrösse misst

Ein kleines Institut lässt mehr weg, weil es weniger hat: kein Handelsbuch,
keine internen Modelle, keine Verbriefungen. Die Rohquote ohne Schichtung ist
eine Grössenmessung mit einem Verhaltensetikett.

## Was hier stattdessen gemessen wird

Der Bezug ist dieselbe Konstruktion wie bei der Zellprüfung (#17): **die
Population derselben Koordinate.** Eine Koordinate ist hier
(Grössenklasse, Stichtag, Template) — sie absorbiert Kalender UND Grösse.

Je Koordinate wird die Offenlegungsquote der Peer-Gruppe gemessen und in drei
Bänder gelegt:

    erwartbar      >= ERWARTUNG      die klare Mehrheit der direkten Peers legt
                                     dieses Template an diesem Stichtag offen
    uneinheitlich  UNTYPISCH..ERWARTUNG   keine Erwartung ableitbar
    untypisch      <  UNTYPISCH      Weglassen ist hier die Regel

Gezählt wird nur im Band `erwartbar`: **ein Institut lässt etwas weg, das seine
direkten Peers am selben Stichtag offenlegen.** Das ist die engste Aussage, die
diese Daten tragen.

Die Bänder sind an der beobachteten Verteilung geeicht, nicht geraten. Über 745
Koordinaten mit n >= 20 ist sie U-förmig: 306 liegen unter 10 %, 84 über 90 %,
der Rest verteilt sich dazwischen. Der breite Mittelbau ist der Grund für das
dritte Band — ein Template, das 45 % der Klasse offenlegen, trägt keine
Erwartung, und ein Schwellenwert bei 50 % würde eine erfinden.

## Was das NICHT ist

**Kein Fehlverhalten.** Art. 432 ist eine ausdrückliche Erlaubnis. Die Zahl
sagt „hier weicht ein Institut von seinen Peers ab", nicht „hier wird etwas
verschwiegen".

**Und nicht sauber von Nichtanwendbarkeit getrennt.** Der Filing-Indicator sagt
„nicht offengelegt", nicht warum. Ein Institut ohne Handelsbuch legt
Marktrisikotemplates nicht offen, weil es keines hat. Die Peer-Gruppe drückt
diesen Anteil, sie eliminiert ihn nicht: auch innerhalb einer Grössenklasse
unterscheiden sich Geschäftsmodelle. Vollständig trennbar wäre das erst mit
einem Anwendbarkeitsmodell (#34); bis dahin ist `n_gegen_erwartung` eine
OBERGRENZE für Ermessensausübung, keine Messung davon. Die Spalte heisst
deshalb nicht `n_ermessen`.

## Art. 432(2) kennt eine Ausnahme von der Ausnahme

Die Angaben nach Art. 437 (Eigenmittel: CC1 `66.01`, CC2 `66.02`) und Art. 450
(Vergütung: REM1–REM5 `30.01`–`30.05`) sind von der Proprietäts-Ausnahme
ausdrücklich AUSGENOMMEN. Eine Auslassung dort kann sich nicht auf
Vertraulichkeit stützen und steht deshalb in einer eigenen Spalte.

Aufruf: python3 scripts/build_omission_profile.py
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
INDICATORS = ROOT / "processed" / "filing_indicators.csv"
OUT = ROOT / "processed" / "omission_profile.csv"
OUT_TPL = ROOT / "processed" / "omission_templates.csv"

# Eine Koordinate ist (Grössenklasse, Stichtag, Template). Unter 20 Instituten
# trägt der Anteil keine Erwartung — dieselbe Schranke wie MIN_INSTITUTES in
# check_plausibility.py, und aus demselben Grund.
MIN_PEER = 20

# Bandgrenzen, geeicht an der U-förmigen Verteilung über 745 Koordinaten.
# Bewusst weit auseinander: der Mittelbau bekommt ein eigenes Band, statt an
# einer 50-%-Schwelle in „erwartbar" oder „untypisch" gezwungen zu werden.
ERWARTUNG = 0.8
UNTYPISCH = 0.2

# Art. 432(2): von der Proprietäts-Ausnahme ausgenommen. Basis-Template-IDs,
# wie sie in den Filing-Indicators stehen (dort ohne Blatt-Suffix).
ART_432_2 = {
    "66.01": "Art. 437 Eigenmittel (CC1)",
    "66.02": "Art. 437 Eigenmittel (CC2)",
    "30.01": "Art. 450 Vergütung (REM1)",
    "30.02": "Art. 450 Vergütung (REM2)",
    "30.03": "Art. 450 Vergütung (REM3)",
    "30.04": "Art. 450 Vergütung (REM4)",
    "30.05": "Art. 450 Vergütung (REM5)",
}

FELDER = ["entityID", "lei", "scope", "refPeriod", "bank_name", "country",
          "institution_type", "deklaration", "n_deklariert", "n_offengelegt",
          "n_ausgelassen", "quote_roh", "n_erwartbar", "n_gegen_erwartung",
          "quote_gegen_erwartung", "n_art432_2", "n_uneinheitlich", "n_untypisch",
          "n_false_mit_daten", "n_true_ohne_daten", "n_signatur_geteilt",
          "templates_gegen_erwartung"]

# Ab dieser Länge ist eine WIEDERHOLTE Auslassungsmenge kein Zufall mehr. Eine
# einzelne gemeinsame Auslassung (`66.02`) können 19 Institute unabhängig
# voneinander beschliessen; elf identische Templates in derselben Reihenfolge
# bei sechs Instituten in vier Ländern nicht.
SIGNATUR_LANG = 3
SIGNATUR_HAEUFIG = 3

FELDER_TPL = ["institution_type", "refPeriod", "template_id", "template_title",
              "n_peer", "n_offengelegt", "quote_peer", "band", "art_432_2"]


def lade_gelieferte(con):
    """{(entityID, refPeriod): {Basis-Template-ID}} — was wirklich im Bestand liegt.

    Die Gegenprobe zur Deklaration. Ohne sie misst diese Auswertung, was
    Institute SAGEN, und verkauft es als das, was sie TUN.

    Das Parquet führt Blatt-IDs (`66.02.A`), die Filing-Indicators Basis-IDs
    (`66.02`); zusammengefasst wird auf die ersten beiden Segmente.
    """
    from determinism import ordered_query as ordered

    aus = collections.defaultdict(set)
    for eid, rp, tid in ordered(con, f"""
        SELECT DISTINCT entityID, CAST(refPeriod AS VARCHAR) AS refPeriod, template_id
        FROM '{PARQUET}'
        ORDER BY entityID, refPeriod, template_id
    """, "gelieferte Templates"):
        aus[(eid, rp)].add(basis_id(tid))
    return aus


def basis_id(template_id):
    """`66.02.A` -> `66.02`, `61.00` -> `61.00`."""
    teile = template_id.split(".")
    return ".".join(teile[:2]) if len(teile) > 2 else template_id


def deklaration_von(n_offengelegt, n_false_mit_daten):
    """Trägt die Deklaration dieses Reports überhaupt eine Aussage?

    Acht Reports deklarieren JEDES Template als „nicht offengelegt" und liefern
    trotzdem Daten — PPF Financial Holdings am 2025-12-31 für 46 Templates, OTP
    Luxembourg für 25. Das ist kein Ermessen nach Art. 432, das ist eine
    fehlerhafte Deklaration.

    Sie als Auslassung zu zählen wäre der teuerste Fehler dieser Auswertung: sie
    stünden mit einer Quote von 1,0 an der Spitze jeder Rangliste, und die
    Rangliste hiesse „Ermessensausübung".
    """
    if n_offengelegt == 0 and n_false_mit_daten > 0:
        return "unbrauchbar"
    if n_false_mit_daten > 0:
        return "widersprüchlich"
    return "stimmig"


def band_von(quote):
    """Trägt diese Koordinate eine Erwartung — und welche?

    Drei Bänder statt einer Schwelle. Ein Template, das 45 % einer Klasse
    offenlegen, ist weder erwartbar noch untypisch; es an einer 50-%-Grenze in
    eines von beiden zu zwingen hiesse, eine Erwartung zu erfinden, die die
    Daten nicht hergeben.
    """
    if quote >= ERWARTUNG:
        return "erwartbar"
    if quote < UNTYPISCH:
        return "untypisch"
    return "uneinheitlich"


def lade(con):
    """Filing-Indicators plus Metadaten, je Report und Template."""
    from determinism import ordered_query as ordered

    return ordered(con, f"""
        WITH meta AS (
          SELECT DISTINCT entityID, refPeriod, lei, scope, bank_name, country,
                 institution_type
          FROM '{PARQUET}'
        )
        SELECT f.entityID, CAST(f.refPeriod AS VARCHAR) AS refPeriod,
               f.template_id, f.reported,
               m.lei, m.scope, m.bank_name, m.country, m.institution_type
        FROM '{INDICATORS}' f
        LEFT JOIN meta m ON m.entityID = f.entityID
                        AND CAST(m.refPeriod AS VARCHAR) = CAST(f.refPeriod AS VARCHAR)
        ORDER BY f.entityID, f.refPeriod, f.template_id, f.reported,
                 m.lei, m.scope, m.bank_name, m.country, m.institution_type
    """, "Filing-Indicators")


def lade_titel(con):
    """{Basis-Template-ID: Klartexttitel}.

    Die Filing-Indicators führen Basis-IDs (`66.02`), das Parquet Blatt-IDs
    (`66.02.A` … `66.02.F`). Zusammengefasst wird über den Präfix, und der
    Titel ist bei allen Blättern derselbe.
    """
    from determinism import ordered_query as ordered

    aus = {}
    for tid, titel in ordered(con, f"""
        SELECT template_id, max(template_title) AS titel
        FROM '{PARQUET}' WHERE template_title IS NOT NULL
        GROUP BY template_id ORDER BY template_id
    """, "Templatetitel"):
        aus.setdefault(tid.split(".")[0] + "." + tid.split(".")[1]
                       if tid.count(".") >= 1 else tid, titel)
    return aus


def peer_quoten(zeilen):
    """{(klasse, stichtag, template): (quote, n)} — die Erwartung je Koordinate.

    Reports ohne Grössenklasse bleiben draussen: ohne Schichtung wäre der
    Vergleich eine Grössenmessung. Sie tauchen in der Ausgabe trotzdem auf, dann
    aber ohne prüfbare Koordinaten — „nicht prüfbar", nicht „unauffällig".
    """
    zaehler = collections.Counter()
    gesamt = collections.Counter()
    for z in zeilen:
        if not z["institution_type"]:
            continue
        k = (z["institution_type"], z["refPeriod"], z["template_id"])
        gesamt[k] += 1
        if z["reported"]:
            zaehler[k] += 1
    return {k: (zaehler[k] / n, n) for k, n in gesamt.items() if n >= MIN_PEER}


def build():
    import duckdb

    con = duckdb.connect()
    roh = lade(con)
    titel = lade_titel(con)
    zeilen = [{"entityID": e, "refPeriod": rp, "template_id": t, "reported": bool(r),
               "lei": lei or "", "scope": sc or "", "bank_name": nm or "",
               "country": la or "", "institution_type": it or ""}
              for e, rp, t, r, lei, sc, nm, la, it in roh]

    quoten = peer_quoten(zeilen)

    geliefert = lade_gelieferte(con)

    je_report = collections.defaultdict(lambda: {
        "n_deklariert": 0, "n_offengelegt": 0, "n_erwartbar": 0,
        "n_uneinheitlich": 0, "n_untypisch": 0, "gegen": [], "art432": 0,
        "false_mit_daten": 0, "true_ohne_daten": 0})
    kopf = {}
    for z in zeilen:
        k = (z["entityID"], z["refPeriod"])
        kopf.setdefault(k, z)
        p = je_report[k]
        p["n_deklariert"] += 1
        # Gegenprobe Deklaration gegen Lieferung. Die beiden Richtungen sind
        # UNTERSCHIEDLICH belastbar, deshalb stehen sie in getrennten Spalten:
        #
        #   False + Daten  — belastbar. Liegen Fakten vor, wurden sie gemeldet;
        #                    die Deklaration „nicht offengelegt" ist dann falsch,
        #                    egal was unsere Kette tut. 175 Zeilen.
        #   True + keine Daten — NICHT belastbar. Kann Nichtlieferung sein, kann
        #                    aber auch eine Lücke in unserer Platzierung sein
        #                    (rein qualitative Templates wie 00.0x tragen keine
        #                    platzierbaren Fakten). 2.001 Zeilen — zehnmal so
        #                    viele, und keine einzige davon zuschreibbar.
        hat_daten = z["template_id"] in geliefert.get(k, ())
        if z["reported"]:
            p["n_offengelegt"] += 1
            if not hat_daten:
                p["true_ohne_daten"] += 1
        elif hat_daten:
            p["false_mit_daten"] += 1
        eintrag = quoten.get((z["institution_type"], z["refPeriod"], z["template_id"]))
        if eintrag is None:
            continue                      # keine Peer-Gruppe: nicht prüfbar
        band = band_von(eintrag[0])
        if band == "uneinheitlich":
            p["n_uneinheitlich"] += 1
        elif band == "untypisch":
            p["n_untypisch"] += 1
        else:
            p["n_erwartbar"] += 1
            if not z["reported"]:
                p["gegen"].append(z["template_id"])
                if z["template_id"] in ART_432_2:
                    p["art432"] += 1

    aus = []
    for k in sorted(je_report):
        p, z = je_report[k], kopf[k]
        ausgelassen = p["n_deklariert"] - p["n_offengelegt"]
        dek = deklaration_von(p["n_offengelegt"], p["false_mit_daten"])
        aus.append({
            "entityID": z["entityID"], "lei": z["lei"], "scope": z["scope"],
            "refPeriod": z["refPeriod"], "bank_name": z["bank_name"],
            "country": z["country"], "institution_type": z["institution_type"],
            "deklaration": dek,
            "n_false_mit_daten": p["false_mit_daten"],
            "n_true_ohne_daten": p["true_ohne_daten"],
            "n_deklariert": p["n_deklariert"], "n_offengelegt": p["n_offengelegt"],
            "n_ausgelassen": ausgelassen,
            "quote_roh": round(ausgelassen / p["n_deklariert"], 4),
            "n_erwartbar": p["n_erwartbar"],
            "n_gegen_erwartung": len(p["gegen"]),
            # Leer, nicht 0, wo es keine erwartbare Koordinate gibt. Eine 0 dort
            # läse sich als „nichts ausgelassen" statt als „nicht prüfbar".
            "quote_gegen_erwartung": (round(len(p["gegen"]) / p["n_erwartbar"], 4)
                                      if p["n_erwartbar"] else ""),
            "n_art432_2": p["art432"],
            "n_uneinheitlich": p["n_uneinheitlich"],
            "n_untypisch": p["n_untypisch"],
            "n_signatur_geteilt": 0,          # unten nachgetragen
            "templates_gegen_erwartung": "|".join(sorted(p["gegen"])),
        })

    # Wie viele ANDERE Reports lassen exakt dieselbe Menge weg? Das ist die
    # Spalte, die verhindert, dass ein gemeinsames Muster als individuelle
    # Ermessensausübung gelesen wird — siehe Modul-Docstring.
    haeufigkeit = collections.Counter(
        a["templates_gegen_erwartung"] for a in aus
        if a["templates_gegen_erwartung"] and a["deklaration"] != "unbrauchbar")
    for a in aus:
        s = a["templates_gegen_erwartung"]
        a["n_signatur_geteilt"] = haeufigkeit.get(s, 0) - 1 if s else 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(aus)

    offen = collections.Counter()
    for z in zeilen:
        if z["reported"]:
            offen[(z["institution_type"], z["refPeriod"], z["template_id"])] += 1
    tpl = []
    for k in sorted(quoten):
        q, n = quoten[k]
        tpl.append({
            "institution_type": k[0], "refPeriod": k[1], "template_id": k[2],
            "template_title": titel.get(k[2], ""), "n_peer": n,
            "n_offengelegt": offen[k], "quote_peer": round(q, 4),
            "band": band_von(q), "art_432_2": ART_432_2.get(k[2], ""),
        })
    with OUT_TPL.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER_TPL)
        w.writeheader()
        w.writerows(tpl)

    print(f"✓ {OUT}  ({len(aus)} Reports)")
    print(f"✓ {OUT_TPL}  ({len(tpl)} Koordinaten)")
    for s in bericht(aus, tpl):
        print("  " + s)
    return aus, tpl


def bericht(aus, tpl):
    zeilen = []
    b = collections.Counter(t["band"] for t in tpl)
    zeilen.append("Koordinaten je Band: " + "  ".join(f"{k}={v}" for k, v in sorted(b.items())))

    d = collections.Counter(a["deklaration"] for a in aus)
    zeilen.append("Deklaration: " + "  ".join(f"{k}={v}" for k, v in sorted(d.items())))
    zeilen.append(f"  Zeilen 'nicht offengelegt' trotz vorhandener Daten: "
                  f"{sum(a['n_false_mit_daten'] for a in aus)}")
    zeilen.append(f"  Zeilen 'offengelegt' ohne Fakt im Bestand (NICHT zuschreibbar): "
                  f"{sum(a['n_true_ohne_daten'] for a in aus)}")

    # Reports mit unbrauchbarer Deklaration fliegen aus jeder Kennzahl. Sie
    # stuenden sonst mit Quote 1,0 an der Spitze — und die Spitze einer Liste,
    # die „Ermessensausuebung" heisst, waere dann ein Deklarationsfehler.
    pruefbar = [a for a in aus if a["n_erwartbar"] and a["deklaration"] != "unbrauchbar"]
    zeilen.append(f"Reports mit prüfbarer Koordinate: {len(pruefbar)} von {len(aus)}"
                  f" ({d['unbrauchbar']} wegen unbrauchbarer Deklaration ausgeschlossen)")
    if pruefbar:
        gegen = sorted(float(a["quote_gegen_erwartung"]) for a in pruefbar)
        n = len(gegen)
        zeilen.append(
            "Quote gegen die Peer-Erwartung: "
            f"Median {gegen[n//2]:.3f} · p90 {gegen[int(0.9*(n-1))]:.3f} · "
            f"max {gegen[-1]:.3f} · ohne jede Abweichung {sum(1 for g in gegen if g == 0)}")

        je = collections.defaultdict(list)
        for a in pruefbar:
            je[a["institution_type"]].append(float(a["quote_gegen_erwartung"]))
        zeilen.append("je Grössenklasse (Median):")
        for kl in sorted(je):
            v = sorted(je[kl])
            zeilen.append(f"  {kl[:28]:30s} n={len(v):4d}  {v[len(v)//2]:.3f}")

        land = collections.defaultdict(list)
        for a in pruefbar:
            if a["country"]:
                land[a["country"]].append(float(a["quote_gegen_erwartung"]))
        gross = sorted(((k, sorted(v)) for k, v in land.items() if len(v) >= 10),
                       key=lambda kv: -kv[1][len(kv[1]) // 2])
        zeilen.append(f"Länder mit n >= 10, höchste Medianquote zuerst ({len(gross)} Länder):")
        for k, v in gross[:6]:
            zeilen.append(f"  {k[:28]:30s} n={len(v):4d}  {v[len(v)//2]:.3f}")

    a432 = sum(a["n_art432_2"] for a in pruefbar)
    zeilen.append(f"Auslassungen in Art.-432(2)-Templates (Eigenmittel/Vergütung): {a432}")

    # Der wichtigste Vorbehalt, und er ist quantifizierbar.
    mit = [a for a in pruefbar if a["templates_gegen_erwartung"]]
    sig = collections.Counter(a["templates_gegen_erwartung"] for a in mit)
    geteilt = sum(c for s, c in sig.items() if c >= SIGNATUR_HAEUFIG)
    lang = {s: c for s, c in sig.items()
            if c >= SIGNATUR_HAEUFIG and s.count("|") + 1 >= SIGNATUR_LANG}
    if mit:
        zeilen.append(
            f"Reports mit Abweichung: {len(mit)} · verschiedene Auslassungsmengen "
            f"{len(sig)} · in einer Menge, die >= {SIGNATUR_HAEUFIG}x vorkommt: "
            f"{geteilt} ({100*geteilt/len(mit):.0f} %)")
        zeilen.append(f"wiederholte LANGE Auslassungsmengen (>= {SIGNATUR_LANG} Templates) "
                      f"— gemeinsame Regel, nicht Ermessen:")
        for s, c in sorted(lang.items(), key=lambda kv: (-kv[1], kv[0]))[:4]:
            wo = {a["country"] for a in mit if a["templates_gegen_erwartung"] == s}
            zeilen.append(f"  {c:3d}x in {len(wo)} Ländern: {s}")

    haeufig = collections.Counter()
    for a in aus:
        for t in a["templates_gegen_erwartung"].split("|"):
            if t:
                haeufig[t] += 1
    if haeufig:
        zeilen.append("am häufigsten gegen die Erwartung weggelassen:")
        for t, c in haeufig.most_common(8):
            zeilen.append(f"  {t:10s} {c:4d}")
    return zeilen


if __name__ == "__main__":
    build()
