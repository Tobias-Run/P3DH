"""Ähnliche Institute aus dem Länder-Exposure-Profil (#13, #27).

Ausgabe: processed/peer_similarity.csv

## Die Frage, die die formale Peer-Gruppe nicht beantwortet

Der Viewer schichtet für Perzentile nach Grössenklasse × Konsolidierungskreis ×
Stichtag. Das ist für Perzentile richtig, beantwortet aber nicht, was ein Leser
wissen will: **mit wem ist dieses Institut eigentlich vergleichbar?** Institute
derselben Grössenklasse melden zwischen 4 und 45 Templates; zwei Häuser mit
gleicher Bilanzsumme können völlig verschiedene Geschäftsmodelle haben und
werden heute trotzdem gegeneinander perzentiliert.

## Das Mass: Überlappung, nicht Distanz

Je Report wird aus `67.01.A` (CCyB1, Spalte `0060` „Total exposure value") die
Länderverteilung des Exposures als ANTEILSVEKTOR gebildet. Die Ähnlichkeit
zweier Institute ist die Summe der elementweisen Minima:

    überlappung(p, q) = Σ_land min(p_land, q_land)

Das ist bewusst kein Kosinus und keine euklidische Distanz. Der Wert ist direkt
lesbar: **„0,68" heisst, dass 68 % des Exposures beider Häuser in denselben
Ländern liegt** — und genau diese Begründung verlangt #27. Eine Kosinus-Distanz
von 0,91 sagt einem Leser nichts.

## Die Gegenprobe: das Verfahren findet Konzerne, ohne sie zu kennen

    1,0000  Investeringsmaatschappij Argenta  ->  Argenta Bank- en Verzekeringsgroep
    0,9999  ING Groep N.V.                    ->  ING Bank N.V.
    0,9996  OTP Luxembourg S.à r.l.           ->  OTP banka d.d.

Alle drei sind Mutter und Tochter derselben Gruppe — und das Verfahren setzt
sie fast deckungsgleich, **ohne je einen Konzerngraphen gesehen zu haben.** Die
Spalte `beziehung` benennt das im Nachhinein aus #32/#42, und die Häufung ist
der eigentliche Beleg: unter den 100 besten Treffern sind 22 konzernintern,
unter den 129 Treffern unterhalb von 0,80 noch genau einer.

Der Ertrag steht daneben — starke Ähnlichkeit zwischen UNABHÄNGIGEN Häusern:

    0,9977  Mediocredito Centrale  ->  ICCREA Banca
    0,9914  Alior Bank             ->  BNP Paribas Bank Polska
    0,9914  ING Bank Śląski        ->  BNP Paribas Bank Polska

## Was das Mass NICHT kann, und es betrifft ein Drittel der Fälle

Zwei rein national tätige Banken desselben Landes überlappen sich zwangsläufig
fast vollständig — sie haben beide fast alles im selben Land. Gemessen: bei
Instituten mit über 90 % Domestizität liegt die beste Überlappung im Median bei
**0,975**, bei breiter aufgestellten nur bei 0,760. Das sind 116 von 326
Reports, und für sie heisst „ähnlich" im Wesentlichen „auch inländisch".

Das ist keine Fehlmessung, sondern die Grenze der Kennzahl: Länder-Exposure
unterscheidet Geschäftsmodelle nur dort, wo Geografie sie unterscheidet.
Deshalb stehen `n_laender` und `groesste_gemeinsamkeit` in jeder Zeile — wer
eine Überlappung von 0,99 bei fünf Ländern sieht, weiss, was er vor sich hat.
#27 nennt die beiden weiteren Achsen (Template-Fingerabdruck, Risikomix aus
OV1); sie sind hier nicht gebaut.

## Drei Randbedingungen, und alle drei stehen im Artefakt

**Ähnlichkeit ist keine Peer-Gruppe.** Die Perzentile im Benchmark bleiben auf
der formalen Schichtung. Diese Liste ist explorativ; sie als aufsichtlich
anerkannte Vergleichsgruppe zu lesen wäre falsch, und der Viewer beschriftet
sie entsprechend.

**Zwei Länder sind keine Ähnlichkeit.** Zwei Institute mit je zwei Ländern
erreichen trivial eine Überlappung von 1,0. `MIN_LAENDER` fordert eine
Mindestbreite; darunter entsteht gar kein Eintrag — die Liste fehlt dann, statt
eine instabile Nachbarschaft zu behaupten.

**Verglichen wird nur innerhalb desselben Stichtags.** Sonst stünde neben einem
Institut sein eigener Vorquartalsbericht als „ähnlichstes Institut", und das
wäre wahr und nutzlos.

Aufruf: python3 scripts/build_peer_similarity.py
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
OUT = ROOT / "processed" / "peer_similarity.csv"

TEMPLATE = "67.01.A"
SPALTE = "0060"              # f Total exposure value

# Unter so vielen Ländern trägt die Überlappung nicht: zwei Institute mit je
# zwei Ländern erreichen trivial 1,0, und die Nachbarschaft wechselt mit jeder
# Welle. Die verbleibenden Profile sind breit genug — Median 32 Länder, erstes
# Dezil 11, Maximum 216.
MIN_LAENDER = 5

# Unterhalb dieser Überlappung ist „ähnlich" keine Aussage mehr. 0,30 heisst:
# weniger als ein Drittel des Exposures liegt in denselben Ländern.
MIN_UEBERLAPPUNG = 0.30

# Wie viele Nachbarn je Report. Fünf, weil der Viewer sie als Liste zeigt und
# der Shard sie mitträgt — die Grösse ist eine Anzeigeentscheidung.
TOP_K = 5

FELDER = ["lei", "scope", "refPeriod", "bank_name", "country", "institution_type",
          "n_laender", "rang", "nachbar_lei", "nachbar_scope", "nachbar_name",
          "nachbar_country", "nachbar_institution_type", "nachbar_n_laender",
          "ueberlappung", "gemeinsame_laender", "groesste_gemeinsamkeit",
          "beziehung"]

GLEIF = ROOT / "processed" / "lei_relations.csv"
EZB = ROOT / "processed" / "coverage_gap.csv"


def lade_konzerne(gleif=None, ezb=None):
    """{lei: {Gruppenkopf}} aus beiden Konzerngraphen (#32, #42).

    Nicht um zu filtern, sondern um zu BENENNEN. Die stärksten Nachbarschaften
    sind konzernintern — ING Groep und ING Bank liegen bei 0,9999, Argenta
    Holding und Argenta Bank bei 1,0000. Das ist die beste Gegenprobe, die
    dieses Verfahren haben kann: es findet Konzernzugehörigkeit aus der
    Exposure-Geografie wieder, **ohne je einen Konzerngraphen gesehen zu
    haben.**

    Als Vorschlag „ähnliche Institute" ist derselbe Treffer allerdings wertlos
    — dass eine Bank ihrer eigenen Mutter ähnelt, weiss der Leser. Die Spalte
    trennt beides, statt eine der beiden Lesarten zu erzwingen.

    Beide Graphen zusammen, weil sie verschiedene Fragen beantworten (#32/#42):
    GLEIF sagt, wem ein Institut gehört, die EZB-Hierarchie, wer die
    beaufsichtigte Gruppe führt. Für „gehören die zusammen" zählt beides.
    """
    kopf = collections.defaultdict(set)
    for pfad, spalte in ((Path(gleif or GLEIF), "ultimate_parent_lei"),
                         (Path(ezb or EZB), "gruppenkopf_lei")):
        if not pfad.exists():
            continue
        with pfad.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("lei") and r.get(spalte):
                    kopf[r["lei"]].add(r[spalte])
    return dict(kopf)


def beziehung_von(a_lei, b_lei, konzerne):
    """`konzern`, `unabhaengig` oder `unbekannt`.

    `unbekannt` ist eine eigene Antwort und nicht `unabhaengig`: kennt einer
    der beiden Graphen das Institut gar nicht, wissen wir nichts über die
    Beziehung — und „unabhängig" zu schreiben wäre eine Aussage über Daten, die
    nicht vorliegen ("Fehlt != Null", Arbeitsprinzip 3).
    """
    ka, kb = konzerne.get(a_lei), konzerne.get(b_lei)
    if not ka or not kb:
        return "unbekannt"
    if ka & kb or a_lei in kb or b_lei in ka:
        return "konzern"
    return "unabhaengig"


def ueberlappung(a, b):
    """Anteil des Exposures, der bei beiden in denselben Ländern liegt.

    a, b: {Land: Anteil}, je Summe 1.

    Das Mass ist symmetrisch, liegt in [0, 1] und ist direkt lesbar. Es ist
    KEIN Kosinus: der Kosinus misst die Richtung des Vektors und ist gegen
    unterschiedliche Breite blind — ein Institut mit zwei Ländern und eines mit
    zweihundert können kosinus-ähnlich sein, wenn die zwei zufällig dominieren.
    Die Minimum-Summe bestraft genau das.
    """
    return sum(min(a.get(land, 0.0), b.get(land, 0.0)) for land in set(a) | set(b))


def anteilsvektor(exposure_je_land):
    """{Land: Betrag} -> {Land: Anteil}, oder None.

    None, wenn nichts Positives übrig bleibt. Negative und Null-Beträge fallen
    heraus: ein negatives Exposure ist eine Nettoposition, kein Gewicht, und in
    einen Anteilsvektor gehörte es nur mit einer Begründung, die wir nicht
    haben.
    """
    positiv = {k: v for k, v in exposure_je_land.items() if v and v > 0}
    summe = sum(positiv.values())
    if not summe:
        return None
    return {k: v / summe for k, v in positiv.items()}


def gemeinsame(a, b, top=1):
    """Die Länder mit dem grössten gemeinsamen Anteil — die Begründung.

    #27 verlangt sie ausdrücklich: „Eine unbegründete `ähnlich`-Behauptung ist
    genau die Art Black Box, die dieses Projekt vermeiden will."
    """
    paare = sorted(((min(a.get(k, 0.0), b.get(k, 0.0)), k) for k in set(a) & set(b)),
                   reverse=True)
    return [k for v, k in paare[:top] if v > 0]


def nachbarn(profile, top_k=TOP_K, min_ueberlappung=MIN_UEBERLAPPUNG):
    """{key: {Land: Anteil}} -> {key: [(überlappung, key), …]}, absteigend.

    Verglichen wird nur INNERHALB desselben Stichtags (drittes Element des
    Schlüssels). Sonst stünde neben einem Institut sein eigener
    Vorquartalsbericht als ähnlichstes — wahr und nutzlos.

    Ein Institut ist nie sein eigener Nachbar, auch nicht über einen anderen
    Konsolidierungskreis: (LEI, CON) und (LEI, IND) sind derselbe Melder, und
    „ähnlich zu sich selbst" ist keine Information.
    """
    je_stichtag = collections.defaultdict(list)
    for k in profile:
        je_stichtag[k[2]].append(k)

    aus = {}
    for stichtag in sorted(je_stichtag):
        keys = sorted(je_stichtag[stichtag])
        for a in keys:
            treffer = []
            for b in keys:
                if a[0] == b[0]:
                    continue                      # derselbe Melder
                u = ueberlappung(profile[a], profile[b])
                if u >= min_ueberlappung:
                    # Der Schlüssel im Sortierkriterium hält die Reihenfolge
                    # stabil, wenn zwei Nachbarn dieselbe Überlappung tragen.
                    treffer.append((-u, b))
            treffer.sort()
            if treffer:
                aus[a] = [(-u, b) for u, b in treffer[:top_k]]
    return aus


def lade(con):
    """{(lei, scope, refPeriod): ({Land: Anteil}, Metadaten)}.

    Nur ZEILEN MIT LAND. `67.01.A` trägt neben den Ländern drei Zeilen, die
    keine sind, und alle drei haben `open_axis_country IS NULL`:

        x1      die Gesamtzeile  — die Summe der übrigen noch einmal
        x28     „übrige Länder"  — der Residualbucket
        qx2014  ein einzelner Ausreisser bei einem Melder

    Solange `x1` mitlief, war das Mass kaputt, und zwar oben, wo es benutzt
    wird. `x1` ist definitionsgemäss halb so gross wie der ganze Report: bei
    den 127 betroffenen Profilen lag sein Anteil im Median bei **exakt 0,500**.
    Damit teilten sich zwei beliebige Institute schon über die Gesamtzeile die
    halbe Masse — eine Gemeinsamkeit, die keine ist.

    Der Median über alle Paare verschob sich dadurch kaum (0,034 auf 0,030);
    wer nur den geprüft hätte, hätte nichts bemerkt. Die Spitze der Verteilung
    kippte dagegen vollständig:

        0,970 -> 0,345      0,924 -> 0,262      0,626 -> 0,005

    Und die Spitze ist genau das, was in `peer_similarity.csv` steht. Eine
    ausgewiesene Überlappung von 0,92 mit der Lesart „92 % des Exposures beider
    Häuser liegt in denselben Ländern" war dann schlicht falsch.

    `x28` fliegt aus demselben Grund mit: zwei Häuser mit je 5 % in „übrige
    Länder" teilen kein Land, sondern eine Restgrösse. Elf Profile bestanden zu
    über 90 % aus diesen beiden Zeilen.
    """
    from determinism import ordered_query as ordered

    roh = collections.defaultdict(dict)
    meta = {}
    for lei, sc, rp, bank, land_meta, it, land, v in ordered(con, f"""
        SELECT lei, scope, refPeriod, max(bank_name), max(country),
               max(institution_type), cell_row, sum(fact_value_eur)
        FROM '{PARQUET}'
        WHERE template_id = '{TEMPLATE}' AND cell_col = '{SPALTE}'
          AND fact_value_eur IS NOT NULL
          AND cell_row IS NOT NULL AND cell_row <> ''
          AND open_axis_country IS NOT NULL
        GROUP BY lei, scope, refPeriod, cell_row
        ORDER BY lei, scope, refPeriod, cell_row
    """, "Länder-Exposure"):
        roh[(lei, sc, rp)][land] = v
        meta[(lei, sc, rp)] = (bank or "", land_meta or "", it or "")

    profile = {}
    for k, d in roh.items():
        vek = anteilsvektor(d)
        if vek and len(vek) >= MIN_LAENDER:
            profile[k] = vek
    return profile, meta


def build():
    import duckdb

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt — erst scripts/build_zweig_b.py")
        return []

    con = duckdb.connect()
    profile, meta = lade(con)
    nb = nachbarn(profile)
    konzerne = lade_konzerne()

    zeilen = []
    for a in sorted(nb):
        bank, land, it = meta[a]
        for rang, (u, b) in enumerate(nb[a], start=1):
            nbank, nland, nit = meta[b]
            g = gemeinsame(profile[a], profile[b], top=3)
            zeilen.append({
                "lei": a[0], "scope": a[1], "refPeriod": a[2], "bank_name": bank,
                "country": land, "institution_type": it,
                "n_laender": len(profile[a]), "rang": rang,
                "nachbar_lei": b[0], "nachbar_scope": b[1], "nachbar_name": nbank,
                "nachbar_country": nland, "nachbar_institution_type": nit,
                "nachbar_n_laender": len(profile[b]),
                "ueberlappung": f"{u:.4f}",
                "gemeinsame_laender": len(set(profile[a]) & set(profile[b])),
                "groesste_gemeinsamkeit": "|".join(g),
                "beziehung": beziehung_von(a[0], b[0], konzerne),
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    print(f"✓ {OUT}  ({len(zeilen)} Zeilen, {len(nb)} Reports mit Nachbarn)")
    for s in bericht(zeilen, profile):
        print("  " + s)
    return zeilen


def bericht(zeilen, profile):
    n_laender = sorted(len(v) for v in profile.values())
    aus = [f"Profile mit >= {MIN_LAENDER} Ländern: {len(profile)} · "
           f"Länder je Profil: Median {n_laender[len(n_laender)//2]} · "
           f"max {n_laender[-1]}"]
    if not zeilen:
        return aus + ["keine Nachbarschaften über der Schwelle"]

    erste = [z for z in zeilen if z["rang"] == "1" or z["rang"] == 1]
    u = sorted(float(z["ueberlappung"]) for z in erste)
    aus.append(f"Reports mit mindestens einem Nachbarn: {len(erste)} · "
               f"beste Überlappung: Median {u[len(u)//2]:.3f} · max {u[-1]:.3f}")

    # Die Gegenprobe. Findet das Verfahren Gruppenzugehörige wieder, ohne je
    # einen Konzerngraphen gesehen zu haben?
    bez = collections.Counter(z["beziehung"] for z in erste)
    aus.append("Beziehung des besten Nachbarn: " +
               "  ".join(f"{k}={v}" for k, v in sorted(bez.items())))
    aus.append("Die stärksten Nachbarschaften — der Beleg, dass das Mass greift:")
    for z in sorted(erste, key=lambda z: -float(z["ueberlappung"]))[:6]:
        aus.append(f"  {z['ueberlappung']}  {z['bank_name'][:28]:30s} -> "
                   f"{z['nachbar_name'][:28]:30s} {z['beziehung']:12s} "
                   f"({z['groesste_gemeinsamkeit'][:18]})")

    # Und der Ertrag: Nachbarn, die die formale Schichtung NICHT zusammenbringt.
    # Der eigentliche Ertrag: starke Ähnlichkeit OHNE Konzernbeziehung.
    fremd = sorted((z for z in erste if z["beziehung"] == "unabhaengig"),
                   key=lambda z: -float(z["ueberlappung"]))[:5]
    if fremd:
        aus.append("Stärkste Ähnlichkeit zwischen UNABHÄNGIGEN Instituten:")
        for z in fremd:
            aus.append(f"  {z['ueberlappung']}  {z['bank_name'][:28]:30s} -> "
                       f"{z['nachbar_name'][:28]:30s} "
                       f"({z['country'][:10]} / {z['nachbar_country'][:10]})")

    quer = [z for z in erste if z["country"] != z["nachbar_country"]]
    aus.append(f"Nachbarschaften über Ländergrenzen hinweg: {len(quer)} von "
               f"{len(erste)} — die formale Schichtung nach Grössenklasse und "
               f"Konsolidierungskreis bringt sie nicht zusammen.")
    return aus


if __name__ == "__main__":
    build()
