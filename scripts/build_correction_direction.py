"""Stellen sich Institute durch ihre Korrekturen besser oder schlechter dar?

Die Frage, die `docs/korrekturspiel.md` §8 als die entscheidende benennt und
dort noch offenlässt. Sie ist beantwortbar, weil `manifest_full.csv` die URL
**jeder** Fassung führt, auch der überholten: beide Stände derselben Meldung
sind ladbar und gegeneinander zu rechnen.

Was hier gemessen wird, ist die **Richtung** einer Korrektur — ob die
korrigierte Fassung das Institut günstiger oder ungünstiger aussehen lässt als
die erste. Nicht gemessen wird Absicht, und aus der Richtung folgt keine.

## Fünf Entscheidungen, ohne die das Ergebnis eine Täuschung wäre

**1. Nur Quoten, keine Niveaus.** Ein gestiegener Risikobetrag ist nicht per se
ungünstig — steigt das Kapital mit, ist die Quote unverändert. Die Quote trägt
das Urteil, das Niveau nicht. Deshalb zählen nur die Zeilen aus KM1 (61.00),
bei denen „höher" eindeutig „besser für das Institut" heisst.

**2. Keine aufsichtlich gesetzten Grössen.** SREP-Anforderung, Puffer und
kombinierte Pufferanforderung sind Vorgaben der Aufsicht, nicht Zahlen des
Instituts. Eine niedrigere Anforderung sieht besser aus, ist aber keine
Selbstdarstellung. Sie bleiben draussen.

**3. Fehlt ≠ Null.** Taucht ein Wert erst in der Korrektur auf, ist das
Vollständigkeit, keine Richtung — und umgekehrt. Beide Fälle bekommen eigene
Urteile (`neu_gemeldet`, `entfallen`) und gehen **nicht** in die Bilanz
günstig/ungünstig ein.

**4. Skalenkorrekturen sind keine Selbstdarstellung.** Eine CET1-Quote, die von
17.315.177 % auf 18,4 % fällt, ist eine Einheitenkorrektur. Ungeprüft würde
diese Klasse die Richtung „ungünstiger" fast im Alleingang erzeugen — dieselbe
Falle wie die implausiblen Werte in #17. Ab Faktor `SKALENFAKTOR` gilt eine
Änderung als Skalenkorrektur und wird gesondert geführt.

**5. Die meisten Korrekturen sind keine Entscheidung.** Ein Fünftel aller
Nachmeldungen erfolgt binnen einer Stunde — missglückte Uploads. Jede Zeile
trägt deshalb ihre Latenzklasse, und die Auswertung, die die Frage des Titels
beantwortet, läuft über die späten.

## Grenzen

- **Nur CODIS.** Die Schlüsselkennzahlen stehen dort. FINDIS (Kreditqualität)
  und die übrigen Rahmenwerke bleiben aussen vor; für sie ist „günstig" ohne
  eigene Richtungstabelle nicht definiert.
- **Nur wer korrigiert hat.** Die Stichprobe sind Korrekturen, nicht Institute.
  Über die 327 Institute ohne jede Korrektur sagt das Blatt nichts.
- **Der Katalog ist ein Schnappschuss** (#6): spätere Korrekturen fehlen.
"""

from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import csv
import math
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from xbrl_csv_parser import XBRLCSVParser  # noqa: E402

MANIFEST = ROOT / "interim" / "edap_recon" / "manifest_full.csv"
CACHE = ROOT / "interim" / "korrekturen_raw"
CODEBOOK = ROOT / "codebook" / "dpm_codebook.csv"
META = ROOT / "processed" / "entity_meta.csv"
OUT = ROOT / "processed" / "correction_direction.csv"
OUT_SUM = ROOT / "processed" / "correction_summary.csv"

RAHMEN = "CODIS"
TEMPLATE = "61.00"
UA = "P3DH-Pipeline/1.0 (+https://github.com/Tobias-Run/P3DH)"

# Zeile -> (Name, Richtung). +1: höher ist für das Institut günstiger.
# Ausgelassen sind bewusst alle Niveaus (Kapital, TREA, HQLA) und alle
# aufsichtlich gesetzten Grössen (SREP, Puffer) — siehe Docstring.
KENNZAHLEN = {
    "0050": ("CET1-Quote", +1),
    "0060": ("Tier-1-Quote", +1),
    "0070": ("Gesamtkapitalquote", +1),
    "0200": ("CET1 nach SREP-Anforderung", +1),
    "0220": ("Verschuldungsquote", +1),
    "0320": ("LCR", +1),
    "0350": ("NSFR", +1),
}

# Spalte -> Periode. 0010 ist der Stichtag der Meldung; die übrigen sind
# Vorperioden, deren Korrektur eine Rückwirkung ist und getrennt zu lesen.
SPALTEN = {"0010": "T", "0020": "T-1", "0030": "T-2",
           "0040": "T-3", "0050": "T-4"}

# Eine Quote wird als Bruch gemeldet (0,1836 = 18,36 %). Die Schwelle ist
# nicht gesetzt, sondern abgelesen: die Beträge der Änderungen zerfallen in
# einen Haufen unterhalb 0,005 pp (ein Drittel aller Zellen — Rundung in der
# fünften Nachkommastelle des Bruchs, etwa 26,702 % -> 26,700 %) und den Rest
# mit Median 0,5 pp. Ein Basispunkt trennt die beiden.
MIN_PP = 0.01

# Ab welchem Verhältnis alt:neu eine Änderung keine Neubewertung derselben
# Grösse mehr ist, sondern eine andere Einheit.
SKALENFAKTOR = 10.0

# Plausible Bandbreite je Kennzahl, als Bruch. Ausserhalb ist der Wert selbst
# der Befund und nicht seine Richtung: eine CET1-Quote von 2.456 % ist kein
# Institut, das sich gut darstellt, sondern ein Skalenfehler (#17) — und eine
# von -0,24 %, die auf 25,2 % korrigiert wird, ist eine Fehlerbereinigung, die
# als „günstiger" die Auswertung verfälschte. Der Skalenfilter allein fängt
# beide nicht: er prüft die Änderung, nicht das Niveau.
#
# Die Liquiditätsquoten sind nach oben offen (Median 300 % bzw. 144 %,
# einzelne Häuser liegen im vierstelligen Bereich) und bekommen deshalb ein
# weiteres Band als die Kapitalquoten.
PLAUSIBEL = {
    "CET1-Quote": (0.0, 1.0),
    "Tier-1-Quote": (0.0, 1.0),
    "Gesamtkapitalquote": (0.0, 1.0),
    "CET1 nach SREP-Anforderung": (0.0, 1.0),
    "Verschuldungsquote": (0.0, 1.0),
    "LCR": (0.0, 100.0),
    "NSFR": (0.0, 100.0),
}

LATENZKLASSEN = ((1 / 24, "unter_1h"), (1, "unter_1t"),
                 (7, "unter_7t"), (30, "unter_30t"), (float("inf"), "ueber_30t"))


def rahmenwerk(url):
    """Das Rahmenwerk steht nur im Pfad, nicht in einer Spalte des Katalogs.

    Ohne diesen Schritt verschmelzen CODIS, ESGDIS und FINDIS desselben
    Instituts zu einer Meldung und gelten als Korrekturen voneinander — der
    Fehler, der #31 einmal auf 2.539 statt 472 Korrekturen brachte.
    """
    teil = url.split("/public-documents/")
    return teil[1].split("/")[0] if len(teil) > 1 else ""


def latenzklasse(tage, klassen=LATENZKLASSEN):
    """Abstand zur vorherigen Fassung -> Klasse."""
    for grenze, name in klassen:
        if tage < grenze:
            return name
    return klassen[-1][1]


def zahl(wert):
    try:
        return float(wert)
    except (TypeError, ValueError):
        return None


def skalenkorrektur(alt, neu, faktor=SKALENFAKTOR):
    """Unterscheidet eine Einheitenkorrektur von einer Neubewertung.

    Beide Werte müssen echt positiv sein, damit ein Verhältnis überhaupt
    definiert ist — ein Vorzeichenwechsel oder eine Null ist etwas anderes und
    hier ausdrücklich keine Skalenkorrektur.
    """
    if alt is None or neu is None or alt <= 0 or neu <= 0:
        return False
    return max(alt / neu, neu / alt) >= faktor


def plausibel(wert, band):
    """Liegt der Wert im Bereich, in dem die Kennzahl überhaupt etwas bedeutet?"""
    if wert is None or band is None:
        return True
    unten, oben = band
    return unten <= wert <= oben


def urteil_von(alt, neu, richtung, min_pp=MIN_PP, faktor=SKALENFAKTOR,
               band=None):
    """Richtung einer einzelnen Zellenänderung.

    `guenstiger`/`unguenstiger` sind Aussagen über die Darstellung, nicht über
    das Institut: eine Korrektur nach unten ist das Zurücknehmen einer zu
    schönen Zahl und spricht für die interne Kontrolle, nicht gegen sie.

    Die Reihenfolge der Prüfungen trägt das Ergebnis. Zuerst das Niveau
    (`unplausibel`), dann die Änderung (`skalenkorrektur`), dann erst die
    Richtung — umgekehrt bekäme jeder Skalenfehler ein Vorzeichen und die
    Bilanz zählte Einheitenkorrekturen als Selbstdarstellung.
    """
    if alt is None and neu is None:
        return "unveraendert"
    if alt is None:
        return "neu_gemeldet"
    if neu is None:
        return "entfallen"
    if not (plausibel(alt, band) and plausibel(neu, band)):
        return "unplausibel"
    if skalenkorrektur(alt, neu, faktor):
        return "skalenkorrektur"
    delta_pp = (neu - alt) * 100
    if abs(delta_pp) < min_pp:
        return "unveraendert"
    return "guenstiger" if delta_pp * richtung > 0 else "unguenstiger"


def lade_meta(pfad=META):
    """LEI -> (Name, Land). Fehlt die Datei, bleibt der Name leer."""
    if not Path(pfad).exists():
        return {}
    with open(pfad, encoding="utf-8") as fh:
        # Die Spalte heisst `name`, nicht `bank_name` — ein stiller Fehlgriff
        # hier liefert leere Namen und keine Fehlermeldung.
        return {r["lei"]: (r.get("name", ""), r.get("country", ""))
                for r in csv.DictReader(fh)}


def fassungen(pfad=MANIFEST, rahmen=RAHMEN):
    """Meldungen mit mehr als einer Fassung, je Meldung zeitlich sortiert."""
    if not Path(pfad).exists():
        return {}
    with open(pfad, encoding="utf-8") as fh:
        zeilen = list(csv.DictReader(fh))
    g = defaultdict(list)
    for r in zeilen:
        if rahmenwerk(r["url"]) == rahmen:
            g[(r["lei"], r["consolidation"], r["module"], r["refdate"])].append(r)
    return {k: sorted(v, key=lambda r: r["submission_ts"])
            for k, v in g.items() if len(v) > 1}


def hole(url, ziel=CACHE):
    """Lädt eine Fassung, wenn sie nicht im Zwischenspeicher liegt."""
    import requests
    ziel.mkdir(parents=True, exist_ok=True)
    p = ziel / url.rsplit("/", 1)[1]
    if p.exists() and p.stat().st_size > 0:
        return p
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": UA})
        r.raise_for_status()
        p.write_bytes(r.content)
        return p
    except Exception as e:
        print(f"  FEHLER {p.name}: {str(e)[:70]}")
        return None


def lies(pfad, codebook=CODEBOOK, template=TEMPLATE):
    """Ein Paket -> ({(Zeile, Spalte): Wert} für KM1, {alle Zellen}: Wert)."""
    try:
        _, dps = XBRLCSVParser(pfad, codebook).parse()
    except Exception as e:
        print(f"  PARSEFEHLER {pfad.name}: {str(e)[:70]}")
        return None
    kennzahl, alle = {}, {}
    for d in dps:
        alle[(d["template_id"], d["cell_row"], d["cell_col"],
              d["open_axis_dims"])] = d["fact_value"]
        if d["template_id"] == template:
            kennzahl[(d["cell_row"], d["cell_col"])] = d["fact_value"]
    return kennzahl, alle


def abstand_tage(frueher, spaeter):
    f = datetime.strptime(frueher[:14], "%Y%m%d%H%M%S")
    s = datetime.strptime(spaeter[:14], "%Y%m%d%H%M%S")
    return (s - f).total_seconds() / 86400.0


def vergleiche(a, b, kennzahlen=KENNZAHLEN, spalten=SPALTEN):
    """Zwei Fassungen -> Liste der Kennzahlurteile.

    Nur Zellen, die sich unterscheiden, erzeugen eine Zeile; `unveraendert`
    entsteht ausschliesslich, wenn eine Änderung unterhalb der
    Wesentlichkeitsschwelle liegt.
    """
    treffer = []
    for zeile, (name, richtung) in kennzahlen.items():
        for spalte, periode in spalten.items():
            roh_alt = a.get((zeile, spalte))
            roh_neu = b.get((zeile, spalte))
            if roh_alt == roh_neu:
                continue
            alt, neu = zahl(roh_alt), zahl(roh_neu)
            treffer.append({
                "kennzahl": name,
                "zeile": zeile,
                "periode": periode,
                "wert_alt": alt,
                "wert_neu": neu,
                "delta_pp": None if (alt is None or neu is None)
                            else round((neu - alt) * 100, 6),
                "urteil": urteil_von(alt, neu, richtung,
                                     band=PLAUSIBEL.get(name)),
            })
    return treffer


def mengenvergleich(alle_a, alle_b):
    """(nur_neu, nur_alt, geaendert) über alle Templates.

    Drei Zahlen, nicht eine: eine Zelle, die erst in der zweiten Fassung
    auftaucht, ist etwas anderes als eine, deren Wert sich geändert hat.
    """
    nur_neu = sum(1 for s in alle_b if s not in alle_a)
    nur_alt = sum(1 for s in alle_a if s not in alle_b)
    geaendert = sum(1 for s in alle_a if s in alle_b and alle_a[s] != alle_b[s])
    return nur_neu, nur_alt, geaendert


def art_der_nachmeldung(nur_neu, nur_alt, geaendert):
    """Nicht jede Nachmeldung ist eine Korrektur — das ist der Hauptbefund.

    Der Katalog führt alle drei Fälle unter demselben Wort, und sie
    zusammenzuzählen war der erste Entwurf dieses Skripts. Sie messen
    verschiedene Dinge:

    - `inhaltsgleich`: kein einziges Faktum unterscheidet sich. Die Datei ist
      neu, der Inhalt nicht — ein erneuter Upload.
    - `vervollstaendigung`: es kommen Fakten hinzu, keines ändert seinen Wert.
      Die erste Fassung war unvollständig, nicht falsch. Ein Institut im
      Bestand meldet zuerst **null** Fakten und liefert dann 1.284 nach.
    - `kuerzung`: der umgekehrte Fall, Fakten fallen weg.
    - `wertkorrektur`: mindestens ein gemeldeter Wert ändert sich. **Nur hier
      ist die Frage nach der Richtung überhaupt gestellt.**
    """
    if not (nur_neu or nur_alt or geaendert):
        return "inhaltsgleich"
    if geaendert:
        return "wertkorrektur"
    if nur_neu and not nur_alt:
        return "vervollstaendigung"
    if nur_alt and not nur_neu:
        return "kuerzung"
    return "umbau"


def main():
    meta = lade_meta()
    gruppen = fassungen()
    if not gruppen:
        print("Kein Katalog gefunden — nichts zu tun.")
        return

    urls = [r["url"] for v in gruppen.values() for r in v]
    print(f"{len(gruppen)} Meldungen mit mehreren Fassungen, {len(urls)} Dateien")
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(hole, urls))

    gelesen = {}

    def paket(url):
        if url not in gelesen:
            p = CACHE / url.rsplit("/", 1)[1]
            gelesen[url] = lies(p) if p.exists() else None
        return gelesen[url]

    zeilen, summen, uebersprungen = [], [], []
    for schluessel, v in sorted(gruppen.items()):
        lei, scope, modul, refdate = schluessel
        name, land = meta.get(lei, ("", ""))
        for nr, (a, b) in enumerate(zip(v, v[1:]), start=1):
            pa, pb = paket(a["url"]), paket(b["url"])
            if pa is None or pb is None:
                # Rund 1 % der Katalogeinträge sind tote Links (HTTP 404, die
                # Zeile steht im Katalog, die Datei wurde nie veröffentlicht).
                # Sie hier still zu überspringen hiesse, die Grundgesamtheit
                # unbemerkt zu verkleinern — sie werden gezählt und genannt.
                uebersprungen.append((lei, refdate, nr))
                continue
            tage = abstand_tage(a["submission_ts"], b["submission_ts"])
            klasse = latenzklasse(tage)
            treffer = vergleiche(pa[0], pb[0])
            basis = {
                "lei": lei, "bank_name": name, "country": land, "scope": scope,
                "modul": modul, "refPeriod": refdate, "fassung": nr,
                "ts_alt": a["submission_ts"], "ts_neu": b["submission_ts"],
                "abstand_tage": round(tage, 4), "latenzklasse": klasse,
            }
            nur_neu, nur_alt, geaendert = mengenvergleich(pa[1], pb[1])
            art = art_der_nachmeldung(nur_neu, nur_alt, geaendert)
            gezaehlt = {"guenstiger": 0, "unguenstiger": 0}
            for t in treffer:
                if t["urteil"] in gezaehlt:
                    gezaehlt[t["urteil"]] += 1
                zeilen.append({**basis, "art": art, **t})
            summen.append({
                **basis,
                "art": art,
                "n_fakten_alt": len(pa[1]),
                "n_fakten_neu": len(pb[1]),
                "n_nur_neu": nur_neu,
                "n_nur_alt": nur_alt,
                "n_wert_geaendert": geaendert,
                "n_kennzahl_beruehrt": len(treffer),
                "n_guenstiger": gezaehlt["guenstiger"],
                "n_unguenstiger": gezaehlt["unguenstiger"],
                "gesamturteil": gesamturteil(gezaehlt, len(treffer)),
            })

    schreibe(OUT, zeilen, ["lei", "bank_name", "country", "scope", "modul",
                           "refPeriod", "fassung", "ts_alt", "ts_neu",
                           "abstand_tage", "latenzklasse", "art", "kennzahl",
                           "zeile", "periode", "wert_alt", "wert_neu",
                           "delta_pp", "urteil"])
    schreibe(OUT_SUM, summen, ["lei", "bank_name", "country", "scope", "modul",
                               "refPeriod", "fassung", "ts_alt", "ts_neu",
                               "abstand_tage", "latenzklasse", "art",
                               "n_fakten_alt", "n_fakten_neu", "n_nur_neu",
                               "n_nur_alt", "n_wert_geaendert",
                               "n_kennzahl_beruehrt", "n_guenstiger",
                               "n_unguenstiger", "gesamturteil"])
    bericht(zeilen, summen, uebersprungen)


def gesamturteil(gezaehlt, n_beruehrt):
    """Ein Paar kann in beide Richtungen korrigieren — das ist kein Fehler,
    sondern der häufige Fall, und wird als `gemischt` geführt statt saldiert.
    Eine Saldierung würde gegenläufige Korrekturen zum Verschwinden bringen.

    `kennzahl_unberuehrt` und `ohne_richtung` auseinanderzuhalten ist nötig:
    das erste heisst „die Schlüsselkennzahlen blieben, wie sie waren", das
    zweite „sie änderten sich, aber nur durch Ergänzung, Einheitenkorrektur
    oder Rundung". Zusammengefasst sähe beides wie Unauffälligkeit aus.
    """
    g, u = gezaehlt["guenstiger"], gezaehlt["unguenstiger"]
    if g and u:
        return "gemischt"
    if g:
        return "guenstiger"
    if u:
        return "unguenstiger"
    return "kennzahl_unberuehrt" if n_beruehrt == 0 else "ohne_richtung"


def schreibe(pfad, zeilen, felder):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with pfad.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=felder)
        w.writeheader()
        for z in sorted(zeilen, key=lambda r: tuple(
                str(r.get(f, "")) for f in felder)):
            w.writerow({f: z.get(f, "") for f in felder})
    print(f"  -> {pfad.relative_to(ROOT)} ({len(zeilen)} Zeilen)")


def bericht(zeilen, summen, uebersprungen=()):
    from collections import Counter
    print(f"\nPaare: {len(summen)}")
    if uebersprungen:
        print(f"uebersprungen (Datei nicht abrufbar): {len(uebersprungen)}")
    print("Art der Nachmeldung:", dict(Counter(s["art"] for s in summen)))
    print("Urteile je Zelle:", dict(Counter(z["urteil"] for z in zeilen)))

    # Die Richtungsfrage stellt sich nur bei echten Wertkorrekturen. Über alle
    # Nachmeldungen gerechnet mischte sie Ergänzungen und Uploads darunter.
    echt = [s for s in summen if s["art"] == "wertkorrektur"]
    print(f"\nWertkorrekturen: {len(echt)} von {len(summen)} Nachmeldungen")
    print("  Gesamturteil:", dict(Counter(s["gesamturteil"] for s in echt)))
    for klasse in ("unter_1h", "unter_1t", "unter_7t", "unter_30t", "ueber_30t"):
        g = [s for s in echt if s["latenzklasse"] == klasse]
        if not g:
            continue
        c = Counter(s["gesamturteil"] for s in g)
        print(f"  {klasse:<10} n={len(g):>3}  guenstiger {c['guenstiger']:>3}  "
              f"unguenstiger {c['unguenstiger']:>3}  gemischt {c['gemischt']:>3}  "
              f"ohne Richtung {c['ohne_richtung'] + c['kennzahl_unberuehrt']:>3}")
    inst = {s["lei"] for s in echt}
    print(f"  betroffene Institute: {len(inst)} — eine Zeile je Paar zählt ein "
          f"Institut mehrfach")


if __name__ == "__main__":
    main()
