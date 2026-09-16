"""Welche Banken hängen an denselben Ländern? (#11, #13)

Ausgabe: processed/peer_clusters.csv

## Was hier dazukommt

`peer_similarity.csv` (#13/#27) liefert je Report die **fünf ähnlichsten**
Institute. Das beantwortet „wem ähnelt dieses Haus" — nicht die Frage aus dem
Titel von #11 und #13: **welche Gruppen** teilen einen Fussabdruck.

Der Unterschied ist nicht kosmetisch. Eine Nachbarschaftsliste ist lokal; sie
sagt nichts darüber, ob drei Häuser einen gemeinsamen Block bilden oder nur
paarweise aneinanderhängen. Genau das ist aber die systemische Frage: eine
gemeinsame Länderexposition ist ein Übertragungskanal, und ein Kanal hat mehr
als zwei Enden.

## Drei Wege, hier etwas zu finden, das keines ist

**1. Ketten auf einem k-NN-Graphen.** Der naheliegende Weg wäre,
Zusammenhangskomponenten über die bestehenden Top-5-Kanten zu bilden. Das geht
schief: A ist ähnlich zu B, B zu C — und A und C können völlig verschieden
sein. Die Gruppe sähe aus wie ein Block und wäre eine Kette. Deshalb wird die
Ähnlichkeit hier **vollständig** gerechnet (343 Profile, rund 58.000 Paare —
das kostet nichts) und je Gruppe die **Kohäsion** ausgewiesen: die KLEINSTE
paarweise Überlappung innerhalb der Gruppe. Eine gekettete Gruppe ist daran
sofort zu erkennen, statt sich als Block auszugeben.

**2. Ein Haus, das sich selbst ähnelt.** Die Beobachtungseinheit ist
(LEI, scope, refPeriod) — dieselbe Bank steht mit jedem Quartal erneut da, und
ihr Fussabdruck ändert sich zwischen zwei Quartalen kaum. Beim ersten Lauf
waren **37 von 69 „Gruppen" ein einziges Institut über mehrere Quartale**. Das
ist keine Peer-Gruppe, das ist eine Identität. Deshalb `MIN_INSTITUTE`; heute
bleiben von 63 Komponenten 26 Gruppen übrig.

**3. Ein Konzern, den man wiederfindet.** OTP Luxembourg und OTP banka d.d.
(Slowenien) landen zuverlässig in derselben Gruppe. Das ist grenzüberschreitend
und trotzdem keine Neuigkeit: es ist dieselbe Bankengruppe. Die Spalte
`traegerschaft` trennt das ab — ein wiedergefundener Konzern ist eine
Gültigkeitsprobe des Verfahrens, kein Befund.

## „Kein Mutterunternehmen gemeldet" heisst nicht „eigenständig"

Arbeitsprinzip 3 gilt auch hier. GLEIF unterscheidet aber sauber: bei
`NO_KNOWN_PERSON`, `NON_CONSOLIDATING` und `NATURAL_PERSONS` ist positiv
erklärt, dass es keine konsolidierende Mutter gibt — das ist eine Auskunft. Bei
`NO_LEI`, `NON_PUBLIC` oder gar keinem Eintrag gibt es eine Mutter, wir kennen
sie nur nicht — das ist keine. Nur die erste Sorte zählt hier als Beleg für
eigene Trägerschaft; die zweite macht die Gruppe `ungeklaert`.

## Warum Zusammenhangskomponenten und kein k-Means

k-Means bräuchte ein k, das niemand kennt, und würde jeden Report in eine
Gruppe zwingen — auch die, die zu nichts gehören. Eine Schwelle sagt dagegen
genau, was gemeint ist: „mindestens so ähnlich". Wer zu niemandem passt, bildet
keine Gruppe, und das ist eine Aussage.

## Der Befund, den das Issue vorhersagt — und der ausbleibt

#13: *„Cluster, die nicht mit dem Heimatland zusammenfallen müssen. Genau das
ist der Erkenntnisgewinn: eine österreichische und eine italienische Bank können
denselben CEE-Footprint haben."*

**Gemessen trägt das nicht.** Von 26 Gruppen ist genau EINE
grenzüberschreitend, und das ist OTP Luxembourg mit OTP banka d.d. — derselbe
Konzern. Null Gruppen mit belegt verschiedenen Trägern über Ländergrenzen.

Dass die Erwartung hier steht, obwohl sie widerlegt ist, ist Absicht: sie war
der Grund, das zu bauen, und das Ergebnis ist eine Antwort auf sie.

Ein Zwischenstand sagte das Gegenteil — sechs Häuser aus Malta, Griechenland,
Finnland und Italien schienen einen Fussabdruck zu teilen. Das war ein
Messfehler: die „gemeinsamen Länder" waren DE, FR, IE (die neun von zehn
Profilen tragen) und `x28`, der Residualbucket. Mit der Korrektur in
`build_peer_similarity.lade` löste die Gruppe sich auf. Der Befund, der nach
Erkenntnis aussah, war die Gesamtzeile.

Aufruf: python3 scripts/build_peer_clusters.py
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

RELATIONS = ROOT / "processed" / "lei_relations.csv"
OUT = ROOT / "processed" / "peer_clusters.csv"

# Ab welcher Überlappung zwei Reports als verbunden gelten. Gemessen über die
# Schwellen 0,70 bis 0,99: darunter kippt die Struktur (bei 0,70 wächst die
# grösste Gruppe sprunghaft von 16 auf 48 — das ist kein Block mehr, sondern
# eine Kette), darüber zerfällt sie in Paare.
SCHWELLE = 0.90

# Unter zwei VERSCHIEDENEN Instituten ist es keine Gruppe, sondern ein Haus
# über mehrere Quartale. Ohne diese Schwelle bestand die Ausgabe zu über der
# Hälfte aus solchen Selbstähnlichkeiten.
MIN_INSTITUTE = 2

# GLEIF-Gründe, die eine eigene Trägerschaft BELEGEN: hier ist erklärt, dass es
# keine konsolidierende Mutter gibt. Alles andere („kein Eintrag", `NO_LEI`,
# `NON_PUBLIC`) heisst nur, dass wir die Mutter nicht kennen — das ist kein
# Beleg für Eigenständigkeit (Arbeitsprinzip 3).
BELEGT_EIGEN = {"NO_KNOWN_PERSON", "NON_CONSOLIDATING", "NATURAL_PERSONS"}

# Ab welchem Anteil im Residualbucket der Vektor als unvollstaendig gilt. #13
# verlangt die Markierung ausdruecklich: „Institute mit hohem `x28`-Anteil
# ausschliessen oder markieren: deren Vektor ist unvollständig." Markieren
# statt ausschliessen, weil der Rest des Profils gueltig bleibt — nur eben
# nicht das ganze Buch. Ein Viertel ist die Grenze, ab der die Zuordnung mehr
# verschweigt als sie zeigt.
X28_GRENZE = 0.25

FELDER = ["gruppe", "groesse", "institute", "kohaesion", "traegerschaft",
          "traeger", "laender_gemeinsam", "laender", "heimatlaender",
          "grenzueberschreitend", "lei", "scope", "refPeriod", "bank_name",
          "country", "institution_type", "n_laender", "x28_anteil",
          "vektor_unvollstaendig"]


def komponenten(knoten, kanten):
    """Zusammenhangskomponenten — deterministisch sortiert.

    `kanten`: Menge von Paaren (a, b). Beides muss festliegen, sonst wechselten
    die Gruppennummern zwischen zwei Läufen und ein Diff der Ausgabe wäre
    wertlos:

    * die Mitglieder, über `sorted(gruppe)` — der Stapel läuft über
      Mengendifferenzen, deren Reihenfolge nicht zugesichert ist;
    * die Gruppen, über den Schlusssortierschritt nach (Grösse, erstem
      Mitglied).

    `sorted(knoten)` steuert nur, welche Komponente zuerst GEFUNDEN wird; für
    die Ausgabe ist das nach dem Schlusssortierschritt gleichgültig. Es steht
    da, damit die Funktion auch ohne ihn eine feste Reihenfolge liefert.
    """
    nach = collections.defaultdict(set)
    for a, b in kanten:
        nach[a].add(b)
        nach[b].add(a)
    gesehen, aus = set(), []
    for start in sorted(knoten):
        if start in gesehen or start not in nach:
            continue
        stapel, gruppe = [start], set()
        while stapel:
            x = stapel.pop()
            if x in gruppe:
                continue
            gruppe.add(x)
            stapel.extend(nach[x] - gruppe)
        gesehen |= gruppe
        aus.append(sorted(gruppe))
    aus.sort(key=lambda g: (-len(g), g[0]))
    return aus


def kohaesion(gruppe, sim):
    """Die KLEINSTE paarweise Überlappung in der Gruppe.

    Die Zahl, die eine Kette von einem Block unterscheidet. Liegt sie deutlich
    unter der Schwelle, hängen die Mitglieder nur über Zwischenglieder
    zusammen — die Gruppe ist dann eine Aussage über den Weg, nicht über die
    Ähnlichkeit ihrer Enden.
    """
    werte = [sim.get(tuple(sorted((a, b))), 0.0)
             for i, a in enumerate(gruppe) for b in gruppe[i + 1:]]
    return min(werte) if werte else 1.0


def gemeinsame_laender(gruppe, profile):
    """Die Länder, in denen JEDES Mitglied der Gruppe Exposure meldet."""
    mengen = [set(profile[k]) for k in gruppe if k in profile]
    if not mengen:
        return set()
    return set.intersection(*mengen)


def lade_traeger(pfad=None):
    """{lei: (art, schluessel)} — wem gehört dieses Institut?

    `art` ist `konzern` (oberste Mutter bekannt), `eigen` (GLEIF erklärt, dass
    es keine gibt) oder `unbekannt`. Der Unterschied zwischen den letzten
    beiden ist der ganze Punkt: nur `eigen` ist eine Auskunft.
    """
    pfad = Path(pfad or RELATIONS)
    if not pfad.exists():
        return {}
    aus = {}
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            lei = r["lei"]
            mutter = (r.get("ultimate_parent_lei") or "").strip()
            grund = (r.get("ultimate_parent_reason") or "").strip()
            if mutter and mutter != lei:
                aus[lei] = ("konzern", mutter)
            elif grund in BELEGT_EIGEN:
                aus[lei] = ("eigen", lei)
            else:
                aus[lei] = ("unbekannt", lei)
    return aus


def traegerschaft(leis, traeger):
    """(urteil, anzahl_belegter_traeger) für eine Gruppe.

    `konzern`      alle Mitglieder gehören belegt derselben Gruppe — das
                   Verfahren hat eine bekannte Struktur wiedergefunden. Eine
                   Gültigkeitsprobe, kein Befund.
    `unabhaengig`  mindestens zwei Mitglieder gehören belegt VERSCHIEDENEN
                   Trägern. Nur hier trägt die These aus #13.
    `ungeklaert`   zu wenig belegt, um das eine vom anderen zu trennen. Nicht
                   dasselbe wie `konzern`, auch wenn es bequemer wäre.
    """
    belegt = {s for lei in leis
              for art, s in [traeger.get(lei, ("unbekannt", lei))]
              if art != "unbekannt"}
    offen = [lei for lei in leis
             if traeger.get(lei, ("unbekannt", lei))[0] == "unbekannt"]
    if len(belegt) >= 2:
        return "unabhaengig", len(belegt)
    if len(belegt) == 1 and not offen:
        return "konzern", 1
    return "ungeklaert", len(belegt)


def lade_x28(con, parquet=None):
    """{(lei, scope, refPeriod): Anteil im Residualbucket}.

    CCyB1 erlaubt, unwesentliche Länder in `x28` („übrige Länder")
    zusammenzufassen. Für die Ähnlichkeit ist dieser Teil des Buches blind: er
    fällt aus dem Vektor, und der Rest wird auf 1 normiert. Ein Haus mit 53 %
    in `x28` wird also über 47 % seines Exposures zugeordnet — das ist keine
    Fehlmessung, aber es muss danebenstehen.
    """
    import build_peer_similarity as ps

    pfad = parquet or ps.PARQUET
    aus = {}
    for lei, sc, rp, x28, land in con.execute(f"""
        SELECT lei, scope, refPeriod,
               sum(CASE WHEN open_axis_country IS NULL AND cell_row = 'x28'
                        THEN fact_value_eur ELSE 0 END),
               sum(CASE WHEN open_axis_country IS NOT NULL AND fact_value_eur > 0
                        THEN fact_value_eur ELSE 0 END)
        FROM '{pfad}'
        WHERE template_id = '{ps.TEMPLATE}' AND cell_col = '{ps.SPALTE}'
          AND fact_value_eur IS NOT NULL
        GROUP BY lei, scope, refPeriod
        ORDER BY lei, scope, refPeriod
    """).fetchall():
        ganz = (x28 or 0) + (land or 0)
        if ganz > 0:
            aus[(lei, sc, rp)] = (x28 or 0) / ganz
    return aus


def build():
    import build_peer_similarity as ps
    import duckdb

    con = duckdb.connect()
    profile, meta = ps.lade(con)
    schluessel = sorted(profile)
    traeger = lade_traeger()
    x28 = lade_x28(con)
    print(f"Profile mit mindestens {ps.MIN_LAENDER} Ländern: {len(schluessel)}")

    # Vollständige Ähnlichkeit. 343 Profile sind rund 58.000 Paare — der
    # Aufwand ist belanglos, und nur so ist die Kohäsion berechenbar.
    vektor = {k: ps.anteilsvektor(profile[k]) for k in schluessel}
    sim, kanten = {}, set()
    for i, a in enumerate(schluessel):
        for b in schluessel[i + 1:]:
            u = ps.ueberlappung(vektor[a], vektor[b])
            if u <= 0:
                continue
            sim[(a, b)] = u
            if u >= SCHWELLE:
                kanten.add((a, b))
    print(f"  Paare mit Überlappung > 0: {len(sim)} · "
          f"Kanten ab {SCHWELLE}: {len(kanten)}")

    roh = komponenten(schluessel, kanten)
    gruppen = [g for g in roh if len({k[0] for k in g}) >= MIN_INSTITUTE]
    print(f"  Komponenten: {len(roh)} · davon mit mindestens "
          f"{MIN_INSTITUTE} Instituten: {len(gruppen)} "
          f"({len(roh) - len(gruppen)} verworfen — ein Haus über mehrere "
          f"Quartale ist keine Gruppe)")

    zeilen = []
    for nr, gruppe in enumerate(gruppen, 1):
        koh = kohaesion(gruppe, sim)
        gem = gemeinsame_laender(gruppe, profile)
        heimat = sorted({meta[k][1] for k in gruppe if k in meta})
        leis = {k[0] for k in gruppe}
        urteil, anzahl = traegerschaft(leis, traeger)
        for k in gruppe:
            lei, scope, rp = k
            name, land, itype = meta.get(k, ("", "", ""))
            zeilen.append({
                "gruppe": nr, "groesse": len(gruppe), "institute": len(leis),
                "kohaesion": f"{koh:.4f}",
                "traegerschaft": urteil, "traeger": anzahl,
                "laender_gemeinsam": len(gem),
                "laender": "|".join(sorted(gem)[:10]),
                "heimatlaender": "|".join(heimat),
                "grenzueberschreitend": "ja" if len(heimat) > 1 else "nein",
                "lei": lei, "scope": scope, "refPeriod": rp,
                "bank_name": name, "country": land, "institution_type": itype,
                "n_laender": len(profile[k]),
                "x28_anteil": f"{x28[k]:.4f}" if k in x28 else "",
                "vektor_unvollstaendig":
                    "ja" if x28.get(k, 0.0) > X28_GRENZE else "nein"})

    zeilen.sort(key=lambda z: (z["gruppe"], z["lei"], z["scope"], z["refPeriod"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)
    print(f"✓ {OUT}  ({len(zeilen)} Zeilen in {len(gruppen)} Gruppen)")
    for s in bericht(gruppen, zeilen):
        print("  " + s)
    return zeilen


def bericht(gruppen, zeilen):
    if not gruppen:
        return ["Keine Gruppe oberhalb der Schwelle — die Struktur trägt nicht."]
    je_gruppe = {}
    for z in zeilen:
        je_gruppe.setdefault(z["gruppe"], []).append(z)
    aus = [f"Gruppen: {len(gruppen)} · Reports darin: {len(zeilen)} · "
           f"grösste {len(gruppen[0])} Reports",
           "Institute je Gruppe: " + "  ".join(
               f"{n}={c}" for n, c in sorted(collections.Counter(
                   zs[0]["institute"] for zs in je_gruppe.values()).items()))]
    koh = sorted(float(zs[0]["kohaesion"]) for zs in je_gruppe.values())
    aus.append(f"Kohäsion (kleinste Überlappung IN der Gruppe): "
               f"min {koh[0]:.3f} · Median {koh[len(koh) // 2]:.3f}")
    schwach = [g for g, zs in je_gruppe.items()
               if float(zs[0]["kohaesion"]) < SCHWELLE - 0.1]
    if schwach:
        aus.append(f"  ⚠ {len(schwach)} Gruppe(n) mit Kohäsion deutlich unter "
                   f"der Schwelle — dort hängen Mitglieder über Zwischenglieder "
                   f"zusammen, nicht direkt.")
    t = collections.Counter(zs[0]["traegerschaft"] for zs in je_gruppe.values())
    aus.append("Trägerschaft: " + "  ".join(f"{k}={v}" for k, v in t.most_common()))

    # Der methodische Punkt, den #13 ausdrücklich nennt.
    unvoll = [z for z in zeilen if z["vektor_unvollstaendig"] == "ja"]
    if unvoll:
        namen = sorted({z["bank_name"] for z in unvoll})
        aus.append(f"⚠ {len(unvoll)} Zeile(n) mit über "
                   f"{X28_GRENZE:.0%} im Residualbucket `x28` — die Zuordnung "
                   f"stützt sich dort auf einen Teil des Buches: "
                   f"{', '.join(n[:30] for n in namen[:3])}")

    grenz = [g for g, zs in je_gruppe.items()
             if zs[0]["grenzueberschreitend"] == "ja"]
    these = [g for g in grenz if je_gruppe[g][0]["traegerschaft"] == "unabhaengig"]
    konzern = [g for g in grenz if je_gruppe[g][0]["traegerschaft"] == "konzern"]
    aus.append(f"→ Grenzüberschreitend: {len(grenz)} von {len(gruppen)} "
               f"Gruppen. Davon {len(these)} mit belegt verschiedenen Trägern "
               f"— NUR die stützen die These aus #13, dass ein gemeinsamer "
               f"Fussabdruck nicht mit dem Heimatland zusammenfällt.")
    if konzern:
        namen = sorted({z["bank_name"] for g in konzern for z in je_gruppe[g]})
        aus.append(f"  {len(konzern)} davon sind ein wiedergefundener Konzern "
                   f"({', '.join(n[:28] for n in namen[:3])}) — "
                   f"grenzüberschreitend, aber keine Neuigkeit. Dass das "
                   f"Verfahren sie findet, ist eine Gültigkeitsprobe.")
    if not these:
        aus.append("  → Kein einziger grenzüberschreitender Cluster mit belegt "
                   "verschiedenen Trägern. Die These aus #13 trägt auf diesen "
                   "Daten NICHT: die Gruppen fallen mit dem Heimatland "
                   "zusammen.")
    for g in sorted(these, key=lambda g: -je_gruppe[g][0]["institute"])[:3]:
        zs = je_gruppe[g]
        aus.append(f"    Gruppe {g}: {zs[0]['institute']} Institute aus "
                   f"{zs[0]['heimatlaender']} · "
                   f"{zs[0]['laender_gemeinsam']} gemeinsame Länder · "
                   f"Kohäsion {zs[0]['kohaesion']}")
        gesehen = set()
        for z in zs:
            if z["lei"] in gesehen:
                continue
            gesehen.add(z["lei"])
            if len(gesehen) > 6:
                break
            aus.append(f"      {z['bank_name'][:38]:40s} {z['country']}")
    return aus


if __name__ == "__main__":
    build()
