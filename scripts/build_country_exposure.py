"""Exposure gemessen an der Wirtschaft des Gastlandes (#14)

Ausgaben: processed/country_exposure.csv      je Report und Land
          processed/country_concentration.csv je Land

## Die Frage

#14: *„Ein Exposure von 5 Mrd EUR in Malta bedeutet etwas völlig anderes als in
Deutschland."* Genau das sieht heute niemand. `codebook/country_gdp.csv` liegt
seit `6d9aed3` im Repo und wird von nichts gelesen ausser dem Abrufskript und
der Doku; die Kontextspalte aus dem Titel des Issues ist damit nicht eingelöst.

Hier steht sie: je Report und Land das Exposure, das Host-BIP und der Quotient.

## Deskriptiv — und das ist keine Floskel

#14 schliesst die Regressorlesart ausdrücklich aus, mit zwei Gründen, die
weiterhin gelten: das BIP ist je Land konstant (effektive Stichprobe ~30, nicht
~450), und Länder mit hohem BIP haben strukturell andere Bankensysteme, sodass
ein Zusammenhang „hohes BIP ↔ höhere Quote" vermutlich ein Grössenklasseneffekt
wäre. `check_country_effect.py` misst das als Regressor und findet nichts; das
hier ist die andere Verwendung: eine Normierung, damit zwei Zahlen
vergleichbar werden, keine Behauptung über Ursachen.

## Vier Wege, hier eine falsche Zahl zu bauen

**1. Die Gesamtzeile als Land zählen.** `67.01.A` trägt `x1` (die Summe der
übrigen noch einmal), `x28` („übrige Länder") und einen Ausreisser `qx2014`.
Alle drei haben `open_axis_country IS NULL`, und genau daran werden sie
erkannt — nicht an einer Liste von Sonderfällen. Derselbe Fehler hat in
#13/#27 eine Weile das Ähnlichkeitsmass verdorben.

**2. Dollar gegen Euro stellen.** Das BIP kommt von der Weltbank in USD, das
Exposure liegt in EUR. Ohne Umrechnung wäre der Quotient um rund 17 % daneben —
sichtbar genug, um falsch zu sein, unsichtbar genug, um durchzugehen. Welcher
Kurs benutzt wurde, steht in `bip_fx_refdate` in der Zeile.

**3. Ein fehlendes BIP als Null lesen.** Für Offshore-Plätze (Jersey,
Guernsey, Britische Jungferninseln) und Taiwan veröffentlicht die Weltbank
keines. `bip_eur` und `exposure_je_bip` bleiben dann LEER. Null hiesse „keine
Wirtschaft", und ein Quotient darauf wäre unendlich (Arbeitsprinzip 3).

**4. Konzerne doppelt zählen.** Für die Aggregation je Land ist das der
gefährlichste: der CON-Report einer Gruppe enthält ihre Töchter bereits. Wer
die IND-Reports derselben Töchter dazuaddiert, zählt dasselbe Geschäft zweimal
und meldet eine Konzentration, die es nicht gibt. Die Aggregation lässt
IND-Reports weg, deren Mutter für denselben Stichtag CON gemeldet hat.

Dazu kommt der Skalenvorbehalt aus #83: ein Report, dessen absolute Beträge um
Grössenordnungen danebenliegen, verdirbt jede Summe, in die er eingeht.

## Wo die Normierung selbst kippt

Ganz oben misst die Quote nicht mehr, was sie soll. Die Marshallinseln
erreichen **5.265 % des BIP**, Luxemburg 780 %, die Kaimaninseln 640 %. Dahinter
steht kein überschuldetes Land, sondern ein Register: Schiffsfinanzierung
beziehungsweise Fondsdomizilierung. Das Exposure liegt dort rechtlich und
wirtschaftlich anderswo, und das BIP ist der falsche Nenner.

Das ist keine Fehlmessung, die sich wegfiltern liesse — es ist die Grenze der
Kennzahl, und sie ist am Wert selbst ablesbar: eine Quote weit über 100 %
bedeutet „Finanzplatz", nicht „Klumpenrisiko". Für die Fälle, um die es #14
geht — 5 Mrd in Malta gegen 5 Mrd in Deutschland —, trägt sie.

## Was die Aggregation NICHT ist

Keine Aussage über das gesamte Exposure gegenüber einem Land. Der Bestand
umfasst die Institute, die nach Säule 3 im P3DH veröffentlichen — nicht das
Bankensystem. Die Spalte heisst deshalb `exposure_eur` und nicht
`gesamtexposure`, und `melder` steht daneben.

Aufruf: python3 scripts/build_country_exposure.py
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
FOOTPRINT = ROOT / "processed" / "footprint.csv"
GDP = ROOT / "codebook" / "country_gdp.csv"
FX = ROOT / "processed" / "fx_rates.csv"
RELATIONS = ROOT / "processed" / "lei_relations.csv"

OUT_JE_REPORT = ROOT / "processed" / "country_exposure.csv"
OUT_JE_LAND = ROOT / "processed" / "country_concentration.csv"

TEMPLATE = "67.01.A"
SPALTE = "0060"              # Total exposure value

# Vorbehalte aus #83, die den ABSOLUTEN Betrag unbrauchbar machen. `residual`
# und `kein_heimatland` betreffen die Länderzuordnung und stören die Summe
# nicht — dieselbe Trennung wie in check_consolidation.brauchbar.
SKALENVORBEHALT = {"skala", "unter_trea"}

# Ab welchem Anteil im Residualbucket die Ländergeografie eines Reports als
# unvollständig gilt — dieselbe Grenze wie in `build_peer_clusters`. #19 nennt
# das als Vorbedingung: „Institute, die fast alles in den Residual-Bucket legen
# (Banco BPM: 101,4 Mrd), verzerren Länder-Aggregate nach unten."
X28_GRENZE = 0.25

FELDER_REPORT = ["refPeriod", "lei", "scope", "bank_name", "home_country",
                 "land", "land_name", "ist_heimatland", "rang",
                 "exposure_eur", "anteil_am_report", "bip_eur", "bip_jahr",
                 "bip_fx_refdate", "exposure_je_bip", "vorbehalt", "x28_anteil"]

FELDER_LAND = ["refPeriod", "land", "land_name", "melder", "melder_gesamt",
               "breite", "melder_unvollstaendig", "exposure_eur",
               "bip_eur", "bip_jahr", "exposure_je_bip", "groesster_melder",
               "groesster_heimat", "groesster_inlaendisch", "groesster_anteil"]


def lade_bip(pfad=None):
    """{iso2: (bip_usd, jahr, name)}.

    Der Join läuft über den ISO-Code, NICHT über den Namen: von 216
    gemeinsamen Codes tragen 32 bei der Weltbank einen anderen Namen als hier
    („Korea, Rep." gegen „Korea, Republic of"). Ein Namensabgleich verlöre sie,
    und zwar lautlos — er fände einfach weniger Länder.
    """
    pfad = Path(pfad or GDP)
    if not pfad.exists():
        return {}
    aus = {}
    with pfad.open(encoding="utf-8") as fh:
        for z in csv.DictReader(fh):
            if z.get("iso2") and z.get("gdp_usd"):
                aus[z["iso2"]] = (float(z["gdp_usd"]), z.get("year", ""),
                                  z.get("country", ""))
    return aus


def usd_kurs(refperiod, kurse):
    """(Kurs USD->EUR, benutztes Stichtagsdatum) oder (None, "").

    `kurse`: {refdate: rate_to_eur}.

    Zum jeweiligen Stichtag liegt nicht immer ein USD-Kurs vor — für
    2025-06-30 etwa keiner. Statt zu raten oder die Zeile fallenzulassen wird
    der NÄCHSTGELEGENE genommen und sein Datum in die Ausgabe geschrieben. Für
    ein Verhältnis, das über Grössenordnungen streut (Malta gegen
    Deutschland), sind ein paar Prozent Kursdrift ohne Belang — aber sie zu
    verschweigen wäre es nicht.
    """
    if not kurse:
        return None, ""
    if refperiod in kurse:
        return kurse[refperiod], refperiod
    nah = min(kurse, key=lambda d: (abs_tage(d, refperiod), d))
    return kurse[nah], nah


def abs_tage(a, b):
    """Abstand zweier ISO-Daten in Tagen — ohne datetime, rein lexikalisch
    zerlegt, damit die Funktion auch bei unvollständigen Daten nicht wirft."""
    def z(s):
        t = s.split("-")
        try:
            return int(t[0]) * 372 + int(t[1]) * 31 + int(t[2])
        except (IndexError, ValueError):
            return 0
    return abs(z(a) - z(b))


def lade_kurse(pfad=None, waehrung="USD"):
    pfad = Path(pfad or FX)
    if not pfad.exists():
        return {}
    with pfad.open(encoding="utf-8") as fh:
        return {z["refdate"]: float(z["rate_to_eur"])
                for z in csv.DictReader(fh)
                if z.get("currency") == waehrung and z.get("rate_to_eur")}


def lade_vorbehalte(pfad=None):
    """{(lei, scope, refPeriod): vorbehalt} aus footprint.csv (#83)."""
    pfad = Path(pfad or FOOTPRINT)
    if not pfad.exists():
        return {}
    with pfad.open(encoding="utf-8") as fh:
        return {(z["lei"], z["scope"], z["refPeriod"]): z.get("vorbehalt", "")
                for z in csv.DictReader(fh)}


def skaliert(vorbehalt):
    """Ist der absolute Betrag dieses Reports unbrauchbar? (#83)"""
    return bool(set((vorbehalt or "").split("|")) & SKALENVORBEHALT)


def konsolidierte_muetter(pfad=None):
    """{kind_lei: {mutter_lei}} — belegte Mutterbeziehungen.

    Nur für die Entdopplung der Aggregation. Ein fehlender Eintrag heisst
    nicht „eigenständig" (Arbeitsprinzip 3), aber er heisst hier auch nichts
    anderes: ohne belegte Mutter gibt es nichts zu entdoppeln.
    """
    pfad = Path(pfad or RELATIONS)
    if not pfad.exists():
        return {}
    aus = collections.defaultdict(set)
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            for feld in ("direct_parent_lei", "ultimate_parent_lei"):
                p = (r.get(feld) or "").strip()
                if p and p != r["lei"]:
                    aus[r["lei"]].add(p)
    return dict(aus)


def doppelt_gezaehlt(lei, scope, refperiod, muetter, con_melder):
    """Steckt dieser Report schon im CON-Report seiner Mutter?

    Der teuerste Fehler dieser Auswertung. Ein CON-Report enthält die Töchter
    bereits; wer den IND-Report derselben Tochter dazuaddiert, zählt dasselbe
    Geschäft zweimal — und meldet eine Länderkonzentration, die es nicht gibt.
    """
    if scope != "IND":
        return False
    return any((m, refperiod) in con_melder for m in muetter.get(lei, ()))


def x28_anteile(con, parquet=None):
    """{(lei, scope, refPeriod): Anteil im Residualbucket}.

    CCyB1 erlaubt, unwesentliche Länder in `x28` („übrige Länder")
    zusammenzufassen. Dieser Teil des Buches ist keinem Land zuzuordnen — er
    fehlt also in JEDER Ländersumme, und zwar nach unten.

    Gemessen liegen zum 31.12.2025 **736,5 Mrd EUR** in `x28`, das sind 3,4 %
    der länderzuordenbaren Masse. Das ist klein genug, um die Aggregate
    brauchbar zu machen, und gross genug, um es nicht zu verschweigen.
    """
    pfad = parquet or PARQUET
    aus = {}
    for lei, sc, rp, x28, land in con.execute(f"""
        SELECT lei, scope, refPeriod,
               sum(CASE WHEN open_axis_country IS NULL AND cell_row = 'x28'
                        THEN fact_value_eur ELSE 0 END),
               sum(CASE WHEN open_axis_country IS NOT NULL AND fact_value_eur > 0
                        THEN fact_value_eur ELSE 0 END)
        FROM '{pfad}'
        WHERE template_id = '{TEMPLATE}' AND cell_col = '{SPALTE}'
          AND fact_value_eur IS NOT NULL
        GROUP BY lei, scope, refPeriod
        ORDER BY lei, scope, refPeriod
    """).fetchall():
        ganz = (x28 or 0) + (land or 0)
        if ganz > 0:
            aus[(lei, sc, rp)] = (x28 or 0) / ganz
    return aus


def je_report(rohzeilen, bip, kurs, kurs_datum, vorbehalte, x28=None):
    """Die Zeilen je (Report, Land) — die Kontextspalte aus #14.

    `rohzeilen`: [(lei, scope, refPeriod, bank, heimat, iso2, name, betrag)]
    """
    x28 = x28 or {}
    je = collections.defaultdict(list)
    for z in rohzeilen:
        je[(z[2], z[0], z[1])].append(z)

    aus = []
    for (rp, lei, scope), zeilen in je.items():
        summe = sum(z[7] for z in zeilen if z[7] > 0)
        vb = vorbehalte.get((lei, scope, rp), "")
        # Absteigend nach Betrag, bei Gleichstand nach Land — sonst wechselte
        # der Rang zwischen zwei Läufen.
        for rang, z in enumerate(sorted(zeilen, key=lambda z: (-z[7], z[5])), 1):
            iso, name, betrag = z[5], z[6], z[7]
            b = bip.get(iso)
            bip_eur = b[0] * kurs if (b and kurs) else None
            aus.append({
                "refPeriod": rp, "lei": lei, "scope": scope,
                "bank_name": z[3], "home_country": z[4],
                "land": iso, "land_name": name,
                "ist_heimatland": "ja" if name and name == z[4] else "nein",
                "rang": rang,
                "exposure_eur": f"{betrag:.2f}",
                "anteil_am_report": f"{betrag / summe:.6f}" if summe > 0 else "",
                # Leer, nicht 0: für Jersey, Guernsey, die Britischen
                # Jungferninseln und Taiwan gibt es kein Weltbank-BIP, und
                # eine Null behauptete eine Wirtschaft der Grösse null.
                "bip_eur": f"{bip_eur:.0f}" if bip_eur else "",
                "bip_jahr": b[1] if b else "",
                "bip_fx_refdate": kurs_datum if bip_eur else "",
                "exposure_je_bip": (f"{betrag / bip_eur:.6f}"
                                    if bip_eur and bip_eur > 0 else ""),
                "vorbehalt": vb,
                "x28_anteil": (f"{x28[(lei, scope, rp)]:.4f}"
                               if (lei, scope, rp) in x28 else "")})
    aus.sort(key=lambda z: (z["refPeriod"], z["lei"], z["scope"], int(z["rang"]),
                            z["land"]))
    return aus


def je_land(zeilen, bip, kurs, kurs_datum, muetter, con_melder):
    """Aggregation je Land — entdoppelt und ohne Skalenvorbehalte.

    Drei Spalten tragen die Vorbehalte, die #19 als Vorbedingung nennt:

    `melder_gesamt` / `breite`
        Wie viele Institute meldeten zu diesem Stichtag überhaupt Exposure,
        und welcher Anteil davon ist in diesem Land engagiert. Ohne den Nenner
        ist `melder` nicht lesbar: 55 Melder sind viel oder wenig, je nachdem,
        ob 60 oder 600 in Frage kamen. #19 nennt das ausdrücklich als eigene
        Anwendung — „Breite, nicht nur Volumen".

    `melder_unvollstaendig`
        Wie viele der beitragenden Häuser über `X28_GRENZE` im Residualbucket
        führen. Deren Ländergeografie ist unvollständig, und die Summe ist
        deshalb nach UNTEN verzerrt — nie nach oben.
    """
    eimer = collections.defaultdict(list)
    gesamt = collections.defaultdict(set)
    for z in zeilen:
        if skaliert(z["vorbehalt"]):
            continue
        if doppelt_gezaehlt(z["lei"], z["scope"], z["refPeriod"],
                            muetter, con_melder):
            continue
        eimer[(z["refPeriod"], z["land"])].append(z)
        gesamt[z["refPeriod"]].add(z["lei"])

    aus = []
    for (rp, iso), zs in eimer.items():
        summe = sum(float(z["exposure_eur"]) for z in zs)
        gross = max(zs, key=lambda z: (float(z["exposure_eur"]), z["lei"]))
        b = bip.get(iso)
        bip_eur = b[0] * kurs if (b and kurs) else None
        melder = {z["lei"] for z in zs}
        alle = len(gesamt[rp])
        unvoll = {z["lei"] for z in zs
                  if z["x28_anteil"] and float(z["x28_anteil"]) > X28_GRENZE}
        aus.append({
            "refPeriod": rp, "land": iso, "land_name": zs[0]["land_name"],
            "melder": len(melder),
            "melder_gesamt": alle,
            "breite": f"{len(melder) / alle:.4f}" if alle else "",
            "melder_unvollstaendig": len(unvoll),
            "exposure_eur": f"{summe:.2f}",
            "bip_eur": f"{bip_eur:.0f}" if bip_eur else "",
            "bip_jahr": b[1] if b else "",
            "exposure_je_bip": (f"{summe / bip_eur:.6f}"
                                if bip_eur and bip_eur > 0 else ""),
            "groesster_melder": gross["bank_name"],
            # Ohne diese beiden Spalten ist eine hohe Konzentration nicht zu
            # deuten. Islands 84,9 % liegen bei Íslandsbanki -- einer
            # islaendischen Bank im eigenen Land, also der Normalfall. Brasiliens
            # 80,1 % liegen bei Santander, und DAS ist ein Klumpenrisiko
            # gegenueber einem Drittstaat, wie #19 es meint.
            "groesster_heimat": gross.get("home_country", ""),
            "groesster_inlaendisch":
                "ja" if gross.get("home_country") and
                gross["home_country"] == gross["land_name"] else "nein",
            "groesster_anteil": (f"{float(gross['exposure_eur']) / summe:.4f}"
                                 if summe > 0 else "")})
    aus.sort(key=lambda z: (z["refPeriod"], z["land"]))
    return aus


def build():
    import duckdb
    from determinism import ordered_query as ordered

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt — erst scripts/build_zweig_b.py")
        return [], []

    bip = lade_bip()
    kurse = lade_kurse()
    vorbehalte = lade_vorbehalte()
    muetter = konsolidierte_muetter()
    if not bip:
        print("ERROR: codebook/country_gdp.csv fehlt — erst "
              "scripts/fetch_country_gdp.py")
        return [], []

    con = duckdb.connect()
    roh = list(ordered(con, f"""
        SELECT lei, scope, refPeriod, max(bank_name), max(country),
               cell_row, max(open_axis_country), sum(fact_value_eur)
        FROM '{PARQUET}'
        WHERE template_id = '{TEMPLATE}' AND cell_col = '{SPALTE}'
          AND fact_value_eur IS NOT NULL
          AND open_axis_country IS NOT NULL
        GROUP BY lei, scope, refPeriod, cell_row
        ORDER BY lei, scope, refPeriod, cell_row
    """, "Exposure je Land"))

    stichtage = {z[2] for z in roh}
    kurs, kurs_datum = usd_kurs(sorted(stichtage)[-1] if stichtage else "", kurse)
    if not kurs:
        print("WARNUNG: kein USD-Kurs — BIP bleibt unumgerechnet, die Spalten "
              "bleiben leer. Das ist kein Nullwert, sondern eine Lücke.")

    zeilen = je_report(roh, bip, kurs, kurs_datum, vorbehalte,
                       x28_anteile(con))
    con_melder = {(z["lei"], z["refPeriod"]) for z in zeilen
                  if z["scope"] == "CON"}
    laender = je_land(zeilen, bip, kurs, kurs_datum, muetter, con_melder)

    for pfad, felder, daten in ((OUT_JE_REPORT, FELDER_REPORT, zeilen),
                                (OUT_JE_LAND, FELDER_LAND, laender)):
        pfad.parent.mkdir(parents=True, exist_ok=True)
        with pfad.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, felder)
            w.writeheader()
            w.writerows(daten)
        print(f"✓ {pfad}  ({len(daten)} Zeilen)")

    for s in bericht(zeilen, laender, bip, kurs, kurs_datum):
        print("  " + s)
    return zeilen, laender


def bericht(zeilen, laender, bip, kurs, kurs_datum):
    if not zeilen:
        return ["Keine Länderzeilen — die Auswertung GREIFT nicht, sie findet "
                "nur nichts."]
    ohne = {z["land"] for z in zeilen if not z["bip_eur"]}
    mit = sum(float(z["exposure_eur"]) for z in zeilen if z["bip_eur"])
    ges = sum(float(z["exposure_eur"]) for z in zeilen)
    aus = [f"Zeilen je Report und Land: {len(zeilen)} · Länder aggregiert: "
           f"{len(laender)}",
           f"USD->EUR {kurs:.5f} (Kurs vom {kurs_datum})" if kurs
           else "ohne Kurs",
           f"BIP-Abdeckung nach Exposure: {mit / ges:.4%} · "
           f"{len(ohne)} Länder ohne Weltbank-BIP "
           f"({', '.join(sorted(ohne)[:8])})"]

    # Die Zahl, um die es #14 geht: dasselbe Exposure wiegt je nach Gastland
    # völlig verschieden. Nur EIN Stichtag, sonst stünde jedes Land mehrfach da
    # und die Liste zeigte Quartale statt Länder.
    #
    # Und zwar der mit den MEISTEN Meldern, nicht der jüngste. Der jüngste war
    # der erste Versuch und griff daneben: im Bestand liegt ein einzelner
    # Frühmelder auf 2026-03-31, und die Liste zeigte prompt dessen sechs
    # Länder mit 0,0 % — eine Auswahlregel, die vernünftig klingt und lautlos
    # im Sonderfall landet.
    melder_je_stichtag = collections.Counter()
    for z in laender:
        melder_je_stichtag[z["refPeriod"]] += z["melder"]
    jung = max(sorted(melder_je_stichtag), key=melder_je_stichtag.get)
    aktuell = [z for z in laender if z["refPeriod"] == jung]
    aus.append(f"Stichtag {jung} (der besetzteste im Bestand) — höchstes "
               f"gemeldetes Exposure im Verhältnis zum Host-BIP:")
    for z in sorted((z for z in aktuell if z["exposure_je_bip"]),
                    key=lambda z: -float(z["exposure_je_bip"]))[:6]:
        aus.append(f"    {z['land']} {z['land_name'][:22]:24s} "
                   f"{float(z['exposure_je_bip']) * 100:8.1f} % des BIP · "
                   f"{z['melder']:3d} Melder · "
                   f"{float(z['exposure_eur']) / 1e9:9.1f} Mrd EUR")
    aus.append("Dieselben Länder nach absolutem Exposure — die Reihenfolge "
               "ist eine andere, und das ist der ganze Punkt des Issues:")
    for z in sorted(aktuell, key=lambda z: -float(z["exposure_eur"]))[:4]:
        quote = (f"{float(z['exposure_je_bip']) * 100:.1f} %"
                 if z["exposure_je_bip"] else "kein BIP")
        aus.append(f"    {z['land']} {z['land_name'][:22]:24s} "
                   f"{float(z['exposure_eur']) / 1e9:9.1f} Mrd EUR · "
                   f"{quote} des BIP")
    aus.append("Die Spitze der Quote misst einen Registerplatz, keine "
               "Volkswirtschaft: hinter den Marshallinseln steht das "
               "Schiffsregister, hinter Luxemburg und den Kaimaninseln die "
               "Fondsdomizilierung. Das BIP ist dort der falsche Nenner — "
               "sichtbar daran, dass die Quote 100 % weit überschreitet.")
    aus.append("Deskriptiv (#14): eine Normierung, damit zwei Zahlen "
               "vergleichbar werden — keine Aussage über Ursachen. Als "
               "Regressor taugt das BIP nicht, und check_country_effect.py "
               "misst genau das.")
    aus.extend(bericht_aggregat(aktuell, jung))
    return aus


def bericht_aggregat(aktuell, stichtag):
    """Die Fragen aus #19 — Breite, Konzentration, Abdeckung."""
    if not aktuell:
        return []
    alle = max(int(z["melder_gesamt"]) for z in aktuell)
    gross = [z for z in aktuell if float(z["exposure_eur"]) > 5e8
             and z["groesster_anteil"]]
    aus = ["", f"#19 — Länder-Aggregate, Stichtag {stichtag}:",
           f"  Beitragende Melder: {alle} (entdoppelt, ohne Skalenvorbehalt). "
           f"Das ist NICHT das EU-Bankensystem, sondern wer im P3DH "
           f"veröffentlicht — die Summen sind entsprechend zu lesen."]
    unvoll = [z for z in aktuell if int(z["melder_unvollstaendig"]) > 0]
    aus.append(f"  {len(unvoll)} von {len(aktuell)} Ländersummen beruhen auf "
               f"mindestens einem Profil mit über {X28_GRENZE:.0%} im "
               f"Residualbucket — sie sind nach UNTEN verzerrt, nie nach oben.")
    if not gross:
        return aus

    # Der eigentliche Befund: Breite und Konzentration sind entkoppelt.
    fremd = [z for z in gross if z["groesster_inlaendisch"] == "nein"]
    aus.append(f"  Klumpenrisiken: von {len(gross)} Ländern mit über 0,5 Mrd "
               f"Exposure tragen {len(fremd)} ihre grösste Position bei einem "
               f"AUSLÄNDISCHEN Institut. Nur die sind Drittstaatenrisiken im "
               f"Sinne des Issues:")
    for z in sorted(fremd, key=lambda z: -float(z["groesster_anteil"]))[:5]:
        aus.append(f"    {z['land']} {z['land_name'][:20]:22s} "
                   f"{float(z['groesster_anteil']):5.1%} bei "
                   f"{z['groesster_melder'][:26]:28s} · {z['melder']:>3} Melder "
                   f"· {float(z['exposure_eur']) / 1e9:7.1f} Mrd")
    aus.append("  Viele Melder heissen NICHT gestreut: Brasilien hat 82 Melder "
               "und trotzdem 80 % bei einem Haus. Die Breite (`breite`) und die "
               "Konzentration (`groesster_anteil`) sind zwei verschiedene "
               "Aussagen, und nur zusammen ergeben sie eine.")
    return aus


if __name__ == "__main__":
    build()
