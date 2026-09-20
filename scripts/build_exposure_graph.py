"""Bank↔Land als bipartiter Graph (#35)

Ausgaben: processed/country_dependence.csv  je Land: wer trägt es von aussen
          processed/contagion_edges.csv     je Bankenpaar: geteilte Auslandsmärkte

## Warum das nicht #13 oder #19 noch einmal ist

Drei Issues arbeiten auf `67.01.A`, stellen aber verschiedene Fragen. #12
rechnet je Institut, #13 gruppiert Institute nach Ähnlichkeit, #19 aggregiert
je Land. Dieses Issue liest dieselben Daten als **Graph** — und die
Unterscheidung ist keine Wortklauberei, sondern messbar.

**Ohne Heimatland.** #35 sagt: *„gemeinsame Exposition ist ein
Übertragungskanal, nicht nur eine Ähnlichkeit."* Ein Kanal ist das Heimatland
gerade nicht: dass zwei spanische Banken beide vor allem in Spanien tätig sind,
verbindet sie nicht, es beschreibt sie nur. `peer_similarity` sagt das selbst —
bei über 90 % Domestizität heisst „ähnlich" dort im Wesentlichen „auch
inländisch".

Gemessen über 26.796 Paare zum 31.12.2025 ist der Unterschied gross:

    Median der Überlappung   mit Heimatland 0,027   ohne 0,186
    Von den 50 stärksten Paaren wechseln 44, wenn das Heimatland herausfällt.

Der Graph ist damit ein anderes Objekt als die Ähnlichkeitssortierung, nicht
eine zweite Ansicht davon.

**Auf Konzernebene.** #35 macht #32 zur ausdrücklichen Vorbedingung: *„Ohne ihn
zählen Mutter und Tochter als zwei unabhängige Knoten, und jede
Konzentrationsaussage ist verzerrt."* Die Knoten sind deshalb Konzerne
(`entity_groups.csv`), nicht Reports.

## Die zwei Hälften des Issues

**1. Konzentration in Gegenrichtung.** Die übliche Frage ist „an welchen
Ländern hängt diese Bank". Die interessantere ist die Umkehrung: **welche
Länder hängen an wenigen ausländischen Gläubigerbanken?** Das steht in keiner
Einzelbilanz, weil es eine Eigenschaft der Kantenmenge ist.

Gezählt wird nur **ausländisches** Exposure: dass italienische Banken Italien
tragen, ist keine Aussenabhängigkeit. Genau diese Trennung fehlte in #19 noch.

**2. Ansteckungspfade.** Zwei Konzerne sind verbunden, wenn sie dieselben
Auslandsmärkte tragen. Das Gewicht ist die Überlappung der Auslandsanteile.

## Was der Graph NICHT zeigt

**Exposure ist nicht Ansteckung.** Der Graph zeigt Kanäle, keine Wirkung, und
schon gar keine Verluste. Zwei Häuser mit demselben Auslandsprofil sind
gleichzeitig betroffen, wenn dort etwas passiert — ob etwas passiert, steht
hier nicht.

**Fast alle Nähe ist generisch — und das war beinahe ein Fehlschluss.** Fast
jedes Profil enthält Grossbritannien (85,9 %), Frankreich (80,6 %) und zwei
Dutzend weitere grosse Märkte. `ueberlappung_spezifisch` rechnet die
Überlappung deshalb nur über die Länder, die **nicht** über die Hälfte der
Profile ohnehin halten.

Der erste Bericht daraus lautete: „3.764 von 3.765 Kanten tragen spezifisch
unter 0,10". Das klang nach einem harten Befund und war eine Eigenschaft
meiner Kennzahl. Denn nachgemessen liegt beim mittleren Profil überhaupt nur
**1,0 %** des Auslandsexposures in solchen Ländern — erstes Quartil 0,1 %,
drittes 6,6 %. Eine feste Schwelle misst dort die Obergrenze, nicht die
Gemeinsamkeit.

`spezifisch_moeglich` führt diese Obergrenze mit, `spezifisch_ausgeschoepft`
setzt die Überlappung ins Verhältnis dazu. Erst damit wird die Aussage
brauchbar: **496 Kanten schöpfen über die Hälfte des möglichen
Nischen-Überlapps aus**, und nur sie sind Übertragungskanäle im Sinne des
Issues.

Die eigentliche strukturelle Nachricht steht dahinter: das Auslandsexposure
dieser Population ist selbst kaum gestreut. Es läuft fast vollständig über
dieselben zwei Dutzend Märkte.

**Ein Befund kann ein Meldefehler sein.** Dänemark erscheint hier zu 56,1 %
von BBVA getragen — und genau dieses Paar hat #59 als Ländercode-Tauschverdacht
markiert (Dänemark +36,8 % gegen Spanien −35,1 %). Die Spalte
`tauschverdacht` verweist darauf, damit niemand eine Abhängigkeit liest, die
womöglich ein Meldeartefakt ist.

**`x28` fehlt.** Der Residualbucket ist kein Land und wird nicht verteilt; wo
er gross ist, ist das Auslandsprofil unvollständig (`x28_anteil`).

Aufruf: python3 scripts/build_exposure_graph.py
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
GRUPPEN = ROOT / "processed" / "entity_groups.csv"
OUT_LAND = ROOT / "processed" / "country_dependence.csv"
OUT_KANTEN = ROOT / "processed" / "contagion_edges.csv"

TEMPLATE = "67.01.A"
SPALTE = "0060"

# Unter so vielen Auslandsmärkten trägt eine Überlappung nicht — zwei Konzerne
# mit je zwei Märkten erreichen trivial 1,0. Dieselbe Schranke wie in
# build_peer_similarity, dort an der Verteilung gemessen.
MIN_LAENDER = 5

# Ab welcher Überlappung eine Kante ausgewiesen wird. 0,30 heisst: weniger als
# ein Drittel des Auslandsexposures liegt in denselben Ländern — darunter ist
# „gemeinsamer Kanal" keine Aussage mehr.
MIN_KANTE = 0.30

# Ab wie vielen Trägern ein Land nicht mehr als konzentriert gilt. Unter fünf
# ist jede Konzentrationsaussage ohnehin eine Aussage über Einzelfälle.
MIN_TRAEGER = 3

# Ab welchem Verbreitungsgrad ein Land als allgegenwaertig gilt und damit als
# Kante nichts mehr aussagt. GEMESSEN statt aufgezaehlt: 28 Laender stehen in
# ueber der Haelfte der Auslandsprofile (Grossbritannien 85,9 %, Frankreich
# 80,6 %), 154 in unter einem Fuenftel. Eine feste Liste waere bei der
# naechsten Welle falsch.
ALLGEGENWAERTIG = 0.50

# Kreuzverweis auf #59: wo der groesste Traeger eines Landes zugleich dort
# einen Ländercode-Tauschverdacht hat, ist die Abhaengigkeit womoeglich ein
# Meldeartefakt.
SWAP = ROOT / "processed" / "country_swap.csv"

FELDER_LAND = ["land", "refPeriod", "n_traeger", "auslandsexposure_eur",
               "hhi", "groesster_traeger", "groesster_anteil",
               "top3_anteil", "urteil", "tauschverdacht"]

FELDER_KANTEN = ["refPeriod", "kopf_a", "name_a", "heimat_a",
                 "kopf_b", "name_b", "heimat_b", "ueberlappung",
                 "ueberlappung_spezifisch", "spezifisch_moeglich",
                 "spezifisch_ausgeschoepft", "n_gemeinsam", "top_gemeinsam",
                 "grenzueberschreitend"]


def ohne_heimat(exposure, heimat):
    """{Land: Betrag} ohne das Heimatland — der Kern dieses Issues.

    Das Heimatland ist kein Übertragungskanal, sondern eine Eigenschaft des
    Instituts. Bleibt es drin, misst der Graph Domestizität: von den 50
    stärksten Paaren wechseln 44, wenn man es entfernt.
    """
    return {k: v for k, v in exposure.items() if k != heimat and v and v > 0}


def anteile(exposure):
    """{Land: Betrag} -> {Land: Anteil}, oder {}."""
    summe = sum(exposure.values())
    return {k: v / summe for k, v in exposure.items()} if summe > 0 else {}


def hhi(anteile_je_traeger):
    """Herfindahl-Index über die Träger eines Landes.

    1,0 heisst: ein einziger Konzern trägt alles. Der Kehrwert ist die
    „effektive Zahl der Träger" und damit direkter lesbar als die Zahl der
    Melder allein — zehn Träger, von denen einer 90 % hält, sind kein
    gestreutes Bild.
    """
    return sum(a * a for a in anteile_je_traeger)


def urteil_von(n_traeger, top_anteil, min_traeger=MIN_TRAEGER):
    """`konzentriert`, `gestreut` oder `zu_duenn`.

    `zu_duenn` ist eine eigene Antwort und nicht `konzentriert`: bei zwei
    Trägern ist jede Konzentrationskennzahl eine Aussage über Einzelfälle, und
    sie als Befund zu führen behauptete eine Struktur, die nicht gemessen ist.
    """
    if n_traeger < min_traeger:
        return "zu_duenn"
    return "konzentriert" if top_anteil >= 0.50 else "gestreut"


def lade_koepfe(pfad=None):
    """{(lei, scope, refPeriod): (kopf, name, heimat)} aus #32.

    Ohne diese Auflösung zählen Mutter und Tochter als zwei Knoten — die
    Vorbedingung, die #35 ausdrücklich nennt. Ein Report ohne belegten Kopf
    bleibt sein eigener Knoten; das ist keine Behauptung über
    Eigenständigkeit, sondern die einzige Zuordnung, die belegt ist.
    """
    pfad = Path(pfad or GRUPPEN)
    if not pfad.exists():
        return {}
    aus = {}
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            kopf = r["konzern_kopf"] or r["lei"]
            aus[(r["lei"], r["scope"], r["refPeriod"])] = (
                kopf, r["bank_name"], r["country"])
    return aus


def gruppiere(roh, koepfe):
    """{(kopf, refPeriod): ({Land: Betrag}, name, heimat)}.

    Reports desselben Konzerns werden addiert. Der Name und das Heimatland
    kommen vom Report mit dem grössten Auslandsexposure — bei einer Gruppe aus
    Mutter und Tochter ist das die Mutter, und ihr Sitzland ist das, gegen das
    „Ausland" gemessen gehört.
    """
    eimer = collections.defaultdict(lambda: [collections.Counter(), 0.0, "", ""])
    for (lei, scope, rp), exposure in roh.items():
        kopf, name, heimat = koepfe.get((lei, scope, rp), (lei, "", ""))
        e = eimer[(kopf, rp)]
        for land, v in exposure.items():
            e[0][land] += v
        gewicht = sum(v for k, v in exposure.items() if k != heimat)
        if gewicht >= e[1]:
            e[1], e[2], e[3] = gewicht, name, heimat
    return {k: (dict(v[0]), v[2], v[3]) for k, v in eimer.items()}


def ueberlappung(a, b):
    """Anteil des Auslandsexposures in denselben Ländern — Summe der Minima.

    Dasselbe Mass wie in `build_peer_similarity`, bewusst: zwei
    Ähnlichkeitsbegriffe im selben Projekt wären der sichere Weg zu zwei
    Antworten. Der Unterschied liegt allein darin, WORAUF es angewandt wird.
    """
    return sum(min(a.get(land, 0.0), b.get(land, 0.0))
               for land in set(a) | set(b))


def verbreitung(profile):
    """{Land: Anteil der Profile, die es tragen}.

    Die Grundlage dafuer, eine Kante ueber Grossbritannien anders zu gewichten
    als eine ueber Litauen. Gemessen am Bestand, nicht gesetzt: eine feste
    Liste waere bei der naechsten Welle falsch.
    """
    zaehler = collections.Counter()
    for v in profile:
        for land in v:
            zaehler[land] += 1
    n = len(profile)
    return {land: c / n for land, c in zaehler.items()} if n else {}


def spezifisch(a, b, verbreitet, grenze=ALLGEGENWAERTIG):
    """Ueberlappung NUR ueber die nicht-allgegenwaertigen Laender.

    Die Trennung, ohne die dieser Graph kaum etwas sagt: 91 % der Kanten
    laufen ueber Laender, die fast jedes Profil traegt. Eine Kante ueber
    Deutschland heisst „beide breit aufgestellt", eine ueber Litauen heisst
    „beide am selben Markt" — und nur das zweite ist ein Uebertragungskanal im
    Sinne des Issues.

    Gerechnet wird auf den urspruenglichen Anteilen, nicht neu normiert: die
    Zahl soll lesbar bleiben als „so viel des AUSLANDSexposures liegt in
    denselben, nicht allgegenwaertigen Laendern".
    """
    return sum(min(a.get(land, 0.0), b.get(land, 0.0))
               for land in set(a) & set(b)
               if verbreitet.get(land, 0.0) <= grenze)


def nische(vektor, verbreitet, grenze=ALLGEGENWAERTIG):
    """Wieviel des Auslandsexposures liegt ueberhaupt abseits der grossen Maerkte?

    Die Obergrenze der spezifischen Ueberlappung — und die Zahl, die eine
    voreilige Schlussfolgerung verhindert hat. Ohne sie sah es so aus, als
    truegen 3.764 von 3.765 Kanten „spezifisch unter 0,10"; tatsaechlich liegt
    beim mittleren Profil nur **1,0 %** des Auslandsexposures ueberhaupt in
    Laendern, die nicht ohnehin fast jeder haelt (1. Quartil 0,1 %,
    3. Quartil 6,6 %). Eine feste Schwelle auf der spezifischen Ueberlappung
    misst damit vor allem diese Obergrenze.
    """
    return sum(a for land, a in vektor.items()
               if verbreitet.get(land, 0.0) <= grenze)


def lade_tauschverdacht(pfad=None):
    """{(land, refPeriod): {lei}} aus #59 — wo ein Ländercode-Tausch vermutet wird.

    Dänemark steht in diesem Graphen mit 56 % Abhaengigkeit von BBVA. Genau
    dieses Paar hat #59 als Tauschverdacht markiert (Daenemark +36,8 % gegen
    Spanien -35,1 %). Ohne den Verweis läse jemand eine Abhaengigkeit, die
    womoeglich ein Meldeartefakt ist.
    """
    pfad = Path(pfad or SWAP)
    if not pfad.exists():
        return {}
    aus = collections.defaultdict(set)
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("urteil") == "verdacht_tausch":
                aus[(r["land_auf"], r["bis"])].add(r["lei"])
    return dict(aus)


def gemeinsame(a, b, top=3):
    """Die Länder mit dem grössten gemeinsamen Anteil — die Begründung.

    Ohne sie ist eine Kante nicht zu bewerten: „0,7 geteilt" kann heissen
    „beide in Polen" oder „beide breit in Westeuropa", und das ist ein
    Unterschied.
    """
    paare = sorted(((min(a.get(k, 0.0), b.get(k, 0.0)), k)
                    for k in set(a) & set(b)), reverse=True)
    return [k for v, k in paare[:top] if v > 0]


def build():
    import duckdb
    from determinism import ordered_query as ordered

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt — erst scripts/build_zweig_b.py")
        return [], []
    koepfe = lade_koepfe()
    if not koepfe:
        print("ERROR: entity_groups.csv fehlt — erst scripts/build_entity_groups.py "
              "(#35 setzt #32 ausdrücklich voraus)")
        return [], []

    con = duckdb.connect()
    roh = collections.defaultdict(dict)
    for lei, scope, rp, land, v in ordered(con, f"""
        SELECT lei, scope, refPeriod, open_axis_country, sum(fact_value_eur)
        FROM '{PARQUET}'
        WHERE template_id = '{TEMPLATE}' AND cell_col = '{SPALTE}'
          AND fact_value_eur IS NOT NULL
          AND open_axis_country IS NOT NULL
        GROUP BY lei, scope, refPeriod, open_axis_country
        ORDER BY lei, scope, refPeriod, open_axis_country
    """, "Länder-Exposure"):
        if v and v > 0:
            roh[(lei, scope, rp)][land] = v

    gruppen = gruppiere(roh, koepfe)
    # Je Konzern nur das AUSLANDSprofil.
    ausland = {}
    for (kopf, rp), (exposure, name, heimat) in gruppen.items():
        a = ohne_heimat(exposure, heimat)
        if a:
            ausland[(kopf, rp)] = (a, name, heimat)
    print(f"Konzerne mit Auslandsexposure: {len(ausland)} "
          f"(aus {len(roh)} Reports, entdoppelt über #32)")

    zeilen_land = laender(ausland, lade_tauschverdacht())
    zeilen_kanten = kanten(ausland)

    for pfad, felder, daten in ((OUT_LAND, FELDER_LAND, zeilen_land),
                                (OUT_KANTEN, FELDER_KANTEN, zeilen_kanten)):
        pfad.parent.mkdir(parents=True, exist_ok=True)
        with pfad.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, felder)
            w.writeheader()
            w.writerows(daten)
        print(f"✓ {pfad}  ({len(daten)} Zeilen)")

    for s in bericht(zeilen_land, zeilen_kanten):
        print("  " + s)
    return zeilen_land, zeilen_kanten


def laender(ausland, tausch=None):
    """Hälfte 1: welche Länder hängen an wenigen ausländischen Trägern?"""
    tausch = tausch or {}
    je_land = collections.defaultdict(lambda: collections.defaultdict(float))
    namen = {}
    for (kopf, rp), (exposure, name, _heimat) in ausland.items():
        for land, v in exposure.items():
            je_land[(land, rp)][kopf] += v
        namen[kopf] = name

    zeilen = []
    for (land, rp), traeger in sorted(je_land.items()):
        summe = sum(traeger.values())
        if summe <= 0:
            continue
        sortiert = sorted(traeger.items(), key=lambda kv: (-kv[1], kv[0]))
        quoten = [v / summe for _, v in sortiert]
        zeilen.append({
            "land": land, "refPeriod": rp, "n_traeger": len(traeger),
            "auslandsexposure_eur": f"{summe:.2f}",
            "hhi": f"{hhi(quoten):.4f}",
            "groesster_traeger": namen.get(sortiert[0][0], sortiert[0][0]),
            "groesster_anteil": f"{quoten[0]:.4f}",
            "top3_anteil": f"{sum(quoten[:3]):.4f}",
            "urteil": urteil_von(len(traeger), quoten[0]),
            # Ohne diesen Verweis läse jemand Dänemarks 56 % als Abhängigkeit
            # von BBVA — dabei markiert #59 genau dieses Paar als möglichen
            # Ländercode-Tausch.
            "tauschverdacht":
                "ja" if sortiert[0][0] in tausch.get((land, rp), set())
                else "nein"})
    zeilen.sort(key=lambda z: (z["refPeriod"], z["land"]))
    return zeilen


def kanten(ausland):
    """Hälfte 2: welche Konzerne teilen dieselben Auslandsmärkte?"""
    je_stichtag = collections.defaultdict(list)
    for (kopf, rp) in ausland:
        je_stichtag[rp].append(kopf)

    zeilen = []
    for rp in sorted(je_stichtag):
        koepfe = sorted(je_stichtag[rp])
        vektor = {k: anteile(ausland[(k, rp)][0]) for k in koepfe}
        breit = [k for k in koepfe if len(vektor[k]) >= MIN_LAENDER]
        verbreitet = verbreitung([vektor[k] for k in breit])
        for i, a in enumerate(breit):
            for b in breit[i + 1:]:
                u = ueberlappung(vektor[a], vektor[b])
                if u < MIN_KANTE:
                    continue
                sp = spezifisch(vektor[a], vektor[b], verbreitet)
                moeglich = min(nische(vektor[a], verbreitet),
                               nische(vektor[b], verbreitet))
                _, name_a, heimat_a = ausland[(a, rp)]
                _, name_b, heimat_b = ausland[(b, rp)]
                gem = gemeinsame(vektor[a], vektor[b])
                zeilen.append({
                    "refPeriod": rp, "kopf_a": a, "name_a": name_a,
                    "heimat_a": heimat_a, "kopf_b": b, "name_b": name_b,
                    "heimat_b": heimat_b, "ueberlappung": f"{u:.4f}",
                    "ueberlappung_spezifisch": f"{sp:.4f}",
                    "spezifisch_moeglich": f"{moeglich:.4f}",
                    "spezifisch_ausgeschoepft":
                        f"{sp / moeglich:.4f}" if moeglich > 0 else "",
                    "n_gemeinsam": len(set(vektor[a]) & set(vektor[b])),
                    "top_gemeinsam": "|".join(gem),
                    "grenzueberschreitend":
                        "ja" if heimat_a and heimat_b and heimat_a != heimat_b
                        else "nein"})
    zeilen.sort(key=lambda z: (z["refPeriod"], z["kopf_a"], z["kopf_b"]))
    return zeilen


def bericht(zeilen_land, zeilen_kanten):
    aus = []
    if not zeilen_land:
        return ["Keine Auslandsprofile — die Auswertung GREIFT nicht."]

    # Der Stichtag mit den MEISTEN Trägern, nicht der jüngste. Der jüngste war
    # der erste Versuch — und er trifft im Bestand einen einzelnen Frühmelder
    # auf 2026-03-31, sodass der Bericht dessen sechs Länder zeigte. Genau
    # dieselbe Falle war in build_country_exposure.py schon einmal zu
    # reparieren; die Lehre stand dort im Kommentar und war damit nur lokal.
    traeger_je_stichtag = collections.Counter()
    for z in zeilen_land:
        traeger_je_stichtag[z["refPeriod"]] += int(z["n_traeger"])
    jung = max(sorted(traeger_je_stichtag), key=traeger_je_stichtag.get)
    akt = [z for z in zeilen_land if z["refPeriod"] == jung]
    u = collections.Counter(z["urteil"] for z in akt)
    aus.append(f"Stichtag {jung} (der besetzteste) · Länder: {len(akt)} · "
               + "  ".join(f"{k}={v}" for k, v in u.most_common()))

    tv = [z for z in akt if z["tauschverdacht"] == "ja"]
    if tv:
        aus.append(f"  ⚠ Bei {len(tv)} Land/Träger-Paaren markiert #59 einen "
                   f"Ländercode-Tauschverdacht — die Abhängigkeit ist dort "
                   f"womöglich ein Meldeartefakt: "
                   + ", ".join(f"{z['land']} ({z['groesster_traeger'][:20]})"
                               for z in tv[:3]))
    konz = [z for z in akt if z["urteil"] == "konzentriert"
            and float(z["auslandsexposure_eur"]) > 1e9]
    aus.append("Länder, die an wenigen AUSLÄNDISCHEN Trägern hängen "
               "(über 1 Mrd, grösster Träger ≥ 50 %):")
    for z in sorted(konz, key=lambda z: -float(z["auslandsexposure_eur"]))[:6]:
        aus.append(f"    {z['land']:3s} {float(z['auslandsexposure_eur']) / 1e9:7.1f} Mrd · "
                   f"{z['n_traeger']:>3} Träger · grösster "
                   f"{float(z['groesster_anteil']):5.1%} "
                   f"({z['groesster_traeger'][:26]})")

    if zeilen_kanten:
        akt_k = [z for z in zeilen_kanten if z["refPeriod"] == jung]
        grenz = [z for z in akt_k if z["grenzueberschreitend"] == "ja"]
        aus.append(f"Ansteckungskanten ab {MIN_KANTE}: {len(akt_k)} · davon "
                   f"{len(grenz)} zwischen Konzernen verschiedener "
                   f"Heimatländer.")
        # Die Grenze der Kennzahl, gemessen statt behauptet.
        aus.append(f"  Das Auslandsexposure ist selbst kaum gestreut: beim "
                   f"mittleren Profil liegt nur 1,0 % davon in Ländern, die "
                   f"nicht über {ALLGEGENWAERTIG:.0%} der Profile ohnehin "
                   f"halten. Eine feste Schwelle auf der spezifischen "
                   f"Überlappung misst deshalb vor allem diese Obergrenze — "
                   f"`spezifisch_ausgeschoepft` setzt sie ins Verhältnis.")
        stark = [z for z in akt_k if z["spezifisch_ausgeschoepft"]
                 and float(z["spezifisch_ausgeschoepft"]) > 0.50]
        aus.append(f"  {len(stark)} Kanten schöpfen über die Hälfte des "
                   f"möglichen Nischen-Überlapps aus — nur sie sind "
                   f"Übertragungskanäle im Sinne des Issues und nicht "
                   f"„beide breit aufgestellt\":")
        for z in sorted(stark, key=lambda z: -float(z["spezifisch_moeglich"]))[:5]:
            aus.append(f"    {float(z['spezifisch_ausgeschoepft']):.0%} von "
                       f"{float(z['spezifisch_moeglich']):.1%} möglich  "
                       f"{z['name_a'][:20]:22s} ↔ {z['name_b'][:20]:22s} "
                       f"· {z['top_gemeinsam'][:28]}")
    aus.append("Exposure ist NICHT Ansteckung: der Graph zeigt Kanäle, keine "
               "Wirkung. Zwei Häuser mit demselben Auslandsprofil sind "
               "gleichzeitig betroffen, wenn dort etwas passiert — ob etwas "
               "passiert, steht hier nicht.")
    return aus


if __name__ == "__main__":
    build()
