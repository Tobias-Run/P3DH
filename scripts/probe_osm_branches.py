"""Machbarkeitsprüfung: OSM-Filialen gegen gemeldete Institute (#41, Schritt 1).

Ausgabe: interim/osm_probe.csv        (je Institut ein Treffer-Urteil)
         interim/osm_country.csv      (Mapping-Dichte je Land)

## Was das hier ist — und was nicht

Das Issue verlangt ausdrücklich die **Messung vor der Analyse**: „Zuerst die
Trefferquote messen … Eine Trefferquote unter ~50 % ist ein legitimer
Abbruchgrund." Dieses Skript misst. Es leitet **keine** Kennzahl ab und trifft
keine Aussage über Geschäftsmodelle.

Der Grund für diese Reihenfolge steht im Issue: anders als GLEIF (#32) oder der
EZB-Abgleich (#42) läuft die Verknüpfung hier über den **Namen**, nicht über die
LEI. Ob das trägt, ist eine empirische Frage — und eine, die man beantworten
muss, bevor man eine Auswertung darauf baut.

## Die Annahme des Issues ist schon im ersten Zug zu eng

Das Issue nennt `operator` als Verknüpfungspunkt. Gemessen trägt das Tag nur
rund ein Drittel der Bank-POIs, `name` dagegen über 90 %:

    MT   88 POIs   operator 36 %   name 94 %
    LV  110 POIs   operator 31 %   name 95 %
    EE   87 POIs   operator 32 %   name 91 %

Wer nur `operator` abgleicht, misst die Tagging-Disziplin und nennt es
Trefferquote. Geprüft werden deshalb `operator`, `name` und `brand`.

## Das Ergebnis: die Abbruchschwelle des Issues ist erreicht

Sechs Länder (MT, LV, EE, HR, PT, GR), 47 Institute, 5.471 Bank-POIs.

    Treffer          23
    kein Treffer      7
    Name zu kurz     15
    Verbundmarke      2

    Trefferquote unter den BEWERTBAREN   76,7 %   (23 von 30)
    Trefferquote über ALLE Institute     48,9 %   (23 von 47)

**Massgeblich ist die zweite.** Ein Verfahren, das bei einem Drittel der
Institute gar nicht erst greift, hat keine Abdeckung von 77 % — es hat eine von
49 %, und damit liegt es unter der Schwelle, die das Issue selbst als
Abbruchgrund nennt.

Die Lücke sind kurze Namen. `OTP`, `APS`, `MDB`, `SEB`, `LHV`, `BNF` sind als
Zeichenkette nicht sicher zuzuordnen — `seb` steckt in `Liepājas SEBiznesa
centrs` genauso wie in der Bank. Das ist keine Frage besserer Normalisierung,
sondern fehlender Information: ein dreibuchstabiges Akronym IST mehrdeutig.

## Wie ein „Treffer" definiert ist

Konservativ, und die Regel steht in `passt()`:

1. Beide Seiten werden auf einen **Kern** reduziert — Kleinschreibung,
   Rechtsformen weg (plc, S.A., N.V., AG, …), Interpunktion weg. Aus
   `Bank of Valletta Plc` wird `bank of valletta`.
2. Ein Treffer ist eine **Enthaltung in einer Richtung** plus eine
   Mindestlänge. `bank of valletta` in `bank of valletta - head office` ist ein
   Treffer; `bank` in irgendetwas ist keiner.

Die Mindestlänge ist der ganze Punkt. Ohne sie trifft „Bank" alles, und die
Quote sähe grossartig aus.

3. Generische Wörter — Rechtsformen, Ländernamen, Artikel — fallen auf BEIDEN
   Seiten weg. Der Fall, der das erzwungen hat: `Banco de Portugal`, die
   portugiesische **Zentralbank**, schrumpfte auf `banco de` und war damit in
   `banco de investimento global` enthalten. 36 Zentralbank-POIs zählten als
   Filialen einer Investmentbank. Nach der Korrektur fiel die Gesamtquote um
   gut zehn Punkte — der Fix hat die Zahl gesenkt, nicht gehoben, und das ist
   die Probe darauf, dass hier nicht auf ein Ergebnis hin optimiert wurde.

## Was diese Prüfung NICHT leisten kann

**Verbundstrukturen.** Sparkassen, Raiffeisen, Crédit Agricole und Volksbanken
teilen sich eine Marke über rechtlich eigenständige Institute hinweg. Ein
Treffer auf „Sparkasse" sagt nichts darüber, WELCHE Sparkasse. Solche Fälle
werden als `verbundmarke` geführt und zählen nicht als Treffer.

**Mapping-Dichte.** Ein Ländervergleich der Filialzahlen misst zuerst, wie gut
das Land gemappt ist. Deshalb steht die Zahl aller Bank-POIs je Land als
Bezugsgrösse daneben — ohne sie ist jede Filialzahl bedeutungslos.

Aufruf: python3 scripts/probe_osm_branches.py [LAND …]
        (ohne Argumente: die voreingestellte Länderstichprobe)
"""

from pathlib import Path
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
OUT = ROOT / "interim" / "osm_probe.csv"
OUT_LAND = ROOT / "interim" / "osm_country.csv"
# Roh-POIs je Land. Gitignoriert und gross, aber der Grund, warum diese
# Messung zweimal dasselbe Ergebnis liefert.
CACHE = ROOT / "interim" / "osm_cache"

ENDPOINT = "https://overpass-api.de/api/interpreter"
UA = "P3DH-feasibility-probe/1.0 (github.com/Tobias-Run/P3DH)"

# Länderstichprobe: bewusst über die Mapping-Dichte gestreut, von dicht
# gemappten (NL) bis dünn (MT, LV, EE). Ein Test nur in Deutschland und den
# Niederlanden beantwortete die Frage des Issues nicht — dort ist OSM dicht,
# und genau daran hängt die Verallgemeinerbarkeit.
LAENDER = {"MT": "Malta", "LV": "Latvia", "EE": "Estonia",
           "NL": "Netherlands", "PT": "Portugal", "HR": "Croatia",
           "GR": "Greece"}

# Rechtsformen und Zusätze, die auf beiden Seiten verschwinden. Sie tragen keine
# Identität: `Bank of Valletta Plc` und `Bank of Valletta` sind dasselbe Haus.
RECHTSFORM = re.compile(
    r"\b(p\.?l\.?c|s\.?a\.?s?|n\.?v\.?|b\.?v\.?|a\.?g|a\.?s|d\.?d|ltd|limited|"
    r"gmbh|inc|corp|holdings?|group|groep|grupo|bank(en|a|as|i)?|banca|banque|"
    r"banco|pank|spa|s\.?p\.?a|oyj|abp|a/s|asa|se|ag|kgaa|e\.?g|co|company|"
    r"aktiengesellschaft|aktiebolaget|akciju|sabiedrība|sabiedriba|"
    r"societe|société|anonyme|sgps)\b", re.I)

# Funktionswörter. Sie überleben das Streichen der Rechtsformen und bilden dann
# Scheinkerne aus reiner Grammatik.
#
# Der Fall, der das erzwungen hat: `Banco de Portugal` — die portugiesische
# ZENTRALBANK — schrumpft auf `banco de`, und das ist in
# `banco de investimento global` enthalten. 36 Zentralbank-POIs zählten damit
# als Filialen einer Investmentbank. Eine Längenschranke hätte das auch
# gefangen, aber zugleich echte Treffer zerstört (`Citadele` gegen `Akciju
# sabiedrība Citadele banka`); generische Wörter zu entfernen trifft die
# Ursache statt des Symptoms.
FUELLWORT = re.compile(r"\b(de|da|do|des|du|di|del|della|of|the|and|und|och|"
                       r"et|y|e|la|le|les|el|il|een|het|en)\b", re.I)

# Marken, die sich rechtlich eigenständige Institute TEILEN. Ein Treffer darauf
# ist keine Zuordnung, sondern eine Verwechslung — dasselbe Problem, das #32
# schwierig macht.
VERBUND = ("sparkasse", "raiffeisen", "volksbank", "credit agricole",
           "crédit agricole", "caisse", "cassa rurale", "banca popolare",
           "crédit mutuel", "credit mutuel", "bcc", "cajamar")

# Unter dieser Länge ist ein Namenskern kein Identifikator mehr. `bank` trifft
# alles; ohne diese Schranke sähe die Trefferquote grossartig aus und hiesse
# nichts.
#
# Die Schwelle stand zuerst bei 8 und war damit zu streng — sie warf `addiko`,
# `luminor`, `bigbank`, `signet` und `inbank` heraus, also durchaus
# unterscheidbare Namen, und erklärte 16 von 43 Instituten für unprüfbar. Bei 5
# bleiben genau die dreibuchstabigen Akronyme draussen (`otp`, `aps`, `mdb`,
# `seb`, `lhv`), und für die ist eine Enthaltungsprüfung tatsächlich nicht
# sicher: `seb` steckt in `Liepājas SEBiznesa centrs` genauso wie in der Bank.
MIN_KERN = 5

# Ländernamen tragen innerhalb ihres eigenen Landes keine Unterscheidung — genau
# wie das Wort „Bank". `HSBC Bank Malta p.l.c.` heisst in OSM schlicht `HSBC`,
# und `hsbc malta` ist darin nicht enthalten. Da ohnehin LÄNDERWEISE gesucht
# wird, ist das Streichen hier kein Zugeständnis, sondern die Beseitigung einer
# Information, die auf beiden Seiten konstant ist.
LANDESWORT = re.compile(
    r"\b(malta|latvija|latvia|eesti|estonia|hrvatska|croatia|portugal|"
    r"nederland|netherlands|holland|ellada|greece|deutschland|germany|"
    r"españa|espana|spain|italia|italy|france|polska|poland|"
    r"österreich|osterreich|austria|suomi|finland|sverige|sweden|"
    r"danmark|denmark|norge|norway|belgië|belgie|belgium|luxembourg)\b", re.I)

FELDER = ["land", "lei", "bank_name", "kern", "urteil", "n_treffer",
          "beispiel_osm", "feld"]
FELDER_LAND = ["iso", "land", "status", "n_poi", "n_operator", "n_name",
               "n_brand", "n_institute", "n_getroffen", "trefferquote"]


def kern(name):
    """Namenskern: kleingeschrieben, ohne Rechtsform, ohne Interpunktion.

    `Bank of Valletta Plc` -> `of valletta`, `HSBC Bank Malta p.l.c.` ->
    `hsbc malta`. Dass dabei auch das Wort „Bank" fällt, ist Absicht: es steht
    in fast jedem Namen auf beiden Seiten und trägt keine Unterscheidung.
    """
    s = (name or "").lower()
    # Reihenfolge ist entscheidend und war zuerst falsch herum: wer zuerst die
    # Interpunktion entfernt, macht aus `p.l.c.` ein `p l c`, und die
    # Rechtsform-Regex greift nicht mehr. Deshalb zweimal — einmal auf der
    # punktierten Form, einmal auf der bereinigten.
    s = RECHTSFORM.sub(" ", s)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = RECHTSFORM.sub(" ", s)
    s = LANDESWORT.sub(" ", s)
    s = FUELLWORT.sub(" ", s)
    # Einzelbuchstaben sind Reste zerlegter Abkürzungen (`p l c`), keine Namen.
    s = re.sub(r"\b\w\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ist_verbund(name):
    n = (name or "").lower()
    return any(v in n for v in VERBUND)


def passt(k_inst, k_osm):
    """Enthaltung in einer Richtung, bei ausreichender Länge.

    Bewusst keine Fuzzy-Distanz: eine Ähnlichkeitsschwelle wäre ein zweiter
    freier Parameter, und diese Prüfung soll eine Untergrenze liefern, keine
    optimierte Quote.
    """
    if not k_inst or not k_osm or len(k_inst) < MIN_KERN:
        return False
    return k_inst in k_osm or (len(k_osm) >= MIN_KERN and k_osm in k_inst)


def hole(query, versuche=5, timeout=240):
    """Overpass mit Wiederholung — der Agent-Proxy bricht Tunnel sporadisch ab."""
    letzte = None
    for i in range(versuche):
        try:
            req = urllib.request.Request(
                ENDPOINT, data=urllib.parse.urlencode({"data": query}).encode(),
                headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:                       # noqa: BLE001
            letzte = e
            time.sleep(2 ** i)
    raise letzte


def banken_eines_landes(iso, cache=None):
    """Bank-POIs eines Landes — aus dem Cache, sonst über Overpass.

    Der Cache ist nicht nur Höflichkeit gegenüber einem gespendeten Dienst: er
    macht die Messung **wiederholbar**. Eine Machbarkeitsprüfung, deren Ergebnis
    von der Tagesform einer fremden API abhängt, belegt nichts — und OSM ändert
    sich täglich, die Zahlen hier wären sonst nie reproduzierbar.
    """
    cache = Path(cache or CACHE)
    datei = cache / f"osm_{iso}.json"
    if datei.exists():
        return json.loads(datei.read_text(encoding="utf-8"))
    el = hole(f'[out:json][timeout:200];'
              f'area["ISO3166-1"="{iso}"][admin_level=2]->.a;'
              f'nwr["amenity"="bank"](area.a);out tags center;').get("elements", [])
    cache.mkdir(parents=True, exist_ok=True)
    datei.write_text(json.dumps(el, ensure_ascii=False), encoding="utf-8")
    return el


def institute(con, laender):
    from determinism import ordered_query as ordered

    namen = ",".join(f"'{n}'" for n in sorted(laender.values()))
    return ordered(con, f"""
        SELECT DISTINCT country, lei, bank_name FROM '{PARQUET}'
        WHERE country IN ({namen}) AND bank_name IS NOT NULL
        ORDER BY country, lei, bank_name
    """, "Institute der Stichprobe")


def pruefe_land(iso, land, inst):
    """Ein Land: POIs holen, Institute dagegen matchen."""
    el = banken_eines_landes(iso)
    poi = []
    for e in el:
        t = e.get("tags") or {}
        for feld in ("operator", "name", "brand"):
            if t.get(feld):
                poi.append((feld, t[feld], kern(t[feld])))

    zeilen = []
    for _, lei, name in inst:
        if ist_verbund(name):
            zeilen.append({"land": land, "lei": lei, "bank_name": name,
                           "kern": kern(name), "urteil": "verbundmarke",
                           "n_treffer": "", "beispiel_osm": "", "feld": ""})
            continue
        k = kern(name)
        treffer = [(f, roh) for f, roh, ko in poi if passt(k, ko)]
        zeilen.append({
            "land": land, "lei": lei, "bank_name": name, "kern": k,
            "urteil": ("zu_kurz" if len(k) < MIN_KERN
                       else ("treffer" if treffer else "kein_treffer")),
            "n_treffer": len(treffer),
            "beispiel_osm": treffer[0][1] if treffer else "",
            "feld": treffer[0][0] if treffer else "",
        })
    t = lambda f: sum(1 for e in el if (e.get("tags") or {}).get(f))  # noqa: E731
    land_zeile = {
        "iso": iso, "land": land, "status": "erhoben", "n_poi": len(el),
        "n_operator": t("operator"), "n_name": t("name"), "n_brand": t("brand"),
        "n_institute": len(zeilen),
        "n_getroffen": sum(1 for z in zeilen if z["urteil"] == "treffer"),
    }
    bewertbar = sum(1 for z in zeilen if z["urteil"] in ("treffer", "kein_treffer"))
    land_zeile["trefferquote"] = (round(land_zeile["n_getroffen"] / bewertbar, 3)
                                  if bewertbar else "")
    return zeilen, land_zeile


def build(isos=None):
    import duckdb

    laender = {k: v for k, v in LAENDER.items() if not isos or k in isos}
    con = duckdb.connect()
    alle = institute(con, laender)
    je_land = {}
    for land, lei, name in alle:
        je_land.setdefault(land, []).append((land, lei, name))

    zeilen, land_zeilen = [], []
    for iso, land in sorted(laender.items()):
        inst = je_land.get(land, [])
        if not inst:
            print(f"  {iso}: keine Institute im Bestand — übersprungen")
            continue
        try:
            z, lz = pruefe_land(iso, land, inst)
        except Exception as e:                       # noqa: BLE001
            # Der Fehler gehoert IN die Ausgabe, nicht nur ins Log. Ein Lauf,
            # der bei sechs von sieben Laendern scheitert, schrieb sonst eine
            # Datei, die vollstaendig aussieht — genau das ist hier einmal
            # passiert und hat ein committetes Artefakt ueberschrieben.
            print(f"  {iso}: Abruf fehlgeschlagen ({type(e).__name__}) — "
                  f"NICHT als 'keine Treffer' gewertet")
            land_zeilen.append({
                "iso": iso, "land": land, "status": "abruf_fehlgeschlagen",
                "n_poi": "", "n_operator": "", "n_name": "", "n_brand": "",
                "n_institute": len(inst), "n_getroffen": "", "trefferquote": ""})
            continue
        zeilen += z
        land_zeilen.append(lz)
        print(f"  {iso} {land:14s} {lz['n_poi']:5d} POIs · {lz['n_institute']:3d} Institute "
              f"· Treffer {lz['n_getroffen']:3d} · Quote {lz['trefferquote']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    zeilen.sort(key=lambda z: (z["land"], z["lei"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)
    land_zeilen.sort(key=lambda z: z["iso"])
    with OUT_LAND.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER_LAND)
        w.writeheader()
        w.writerows(land_zeilen)

    print(f"\n✓ {OUT} ({len(zeilen)} Institute)")
    print(f"✓ {OUT_LAND} ({len(land_zeilen)} Länder)")
    for s in urteil(zeilen, land_zeilen):
        print("  " + s)
    return zeilen, land_zeilen


def urteil(zeilen, land_zeilen):
    import collections

    u = collections.Counter(z["urteil"] for z in zeilen)
    aus = ["Urteil je Institut: " + "  ".join(f"{k}={v}" for k, v in sorted(u.items()))]
    bewertbar = u["treffer"] + u["kein_treffer"]
    if bewertbar:
        # ZWEI Quoten, und sie sagen Verschiedenes. Die erste beantwortet
        # „funktioniert der Namensabgleich, wo er anwendbar ist"; die zweite
        # „wie viele Institute erreicht er". Nur die zweite ist der Massstab für
        # die Abbruchempfehlung des Issues — ein Verfahren, das bei 30 % der
        # Institute gar nicht erst greift, ist keine Abdeckung von 77 %.
        q_bed = u["treffer"] / bewertbar
        q_ges = u["treffer"] / len(zeilen)
        aus.append(f"Trefferquote unter den BEWERTBAREN: {q_bed:.1%} "
                   f"({u['treffer']} von {bewertbar})")
        aus.append(f"Trefferquote über ALLE Institute:   {q_ges:.1%} "
                   f"({u['treffer']} von {len(zeilen)}) — "
                   f"{u['zu_kurz']} Namen zu kurz, {u['verbundmarke']} Verbundmarken")
        aus.append("ABBRUCHEMPFEHLUNG des Issues (< 50 % über alle): "
                   + ("ERREICHT — die Idee trägt in dieser Form nicht"
                      if q_ges < 0.5 else "nicht erreicht"))
    f = collections.Counter(z["feld"] for z in zeilen if z["feld"])
    if f:
        aus.append("Treffer über Tag: " + "  ".join(f"{k}={v}" for k, v in f.most_common()))
    fehlt = [lz for lz in land_zeilen if lz["status"] != "erhoben"]
    if fehlt:
        aus.append("⚠ NICHT erhoben (Abruf fehlgeschlagen): "
                   + ", ".join(lz["iso"] for lz in fehlt)
                   + " — die Quoten oben gelten nur fuer die uebrigen Laender")
    erhoben = [lz for lz in land_zeilen if lz["status"] == "erhoben"]
    if erhoben:
        aus.append("Mapping-Dichte je Land (Bank-POIs je Institut im Bestand):")
        for lz in sorted(erhoben, key=lambda x: -x["n_poi"]):
            aus.append(f"  {lz['iso']} {lz['land'][:14]:16s} {lz['n_poi']:5d} POIs · "
                       f"operator {100*lz['n_operator']//max(lz['n_poi'],1):3d} % · "
                       f"Quote {lz['trefferquote']}")
    return aus


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "scripts"))
    build([a.upper() for a in sys.argv[1:]] or None)
