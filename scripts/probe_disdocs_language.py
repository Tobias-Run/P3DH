"""In welcher Sprache berichten die Institute? (#38)

Ausgabe: interim/disdocs_language.csv

## Die Vorbedingung, die noch offen war

#38 verlangt sie ausdrücklich, bevor irgendeine inhaltliche Aussage entsteht:

> ⚠️ **31 Länder, entsprechend viele Sprachen.** Eine Schlagwortsuche auf
> Deutsch oder Englisch erfasst einen verzerrten Ausschnitt und würde
> systematisch die Institute treffen, die auf Englisch berichten. Die
> Sprachverteilung ist vor jeder inhaltlichen Aussage zu messen.

`probe_disdocs.py` hat den Extraktionstest erledigt — 97 % der PDFs tragen eine
Textebene, der Korpus ist erschliessbar. Die Sprache aber blieb offen: **kein
einziges PDF gibt ein `/Lang` an.** Aus den Metadaten ist sie nicht zu holen.

## Warum Stoppwörter und nicht Zeichenstatistik

Erkannt wird über Funktionswörter — Artikel, Präpositionen, Konjunktionen. Sie
sind in jedem Sachtext häufig, sprachspezifisch und stehen unabhängig vom
Fachgebiet. Eine Zeichen- oder n-Gramm-Statistik wäre genauer, bräuchte aber
Trainingsdaten; Stoppwörter kommen ohne aus und ihre Fehler sind erklärbar.

Die verwandten Sprachen sind der wunde Punkt (Tschechisch/Slowakisch,
Dänisch/Norwegisch/Schwedisch). Deshalb wird nicht nur der Sieger gemeldet,
sondern auch der **Abstand zum Zweiten**: liegt er unter `MIN_ABSTAND`, heisst
das Urteil `unsicher` und nicht die wahrscheinlichere Sprache.

## Die Fehlerquote wird gemessen, nicht behauptet

Ein Spracherkenner ohne Gütemaß ist eine Behauptung. Geprüft wird gegen zwei
Dinge, die unabhängig von ihm feststehen:

1. **Das Sitzland.** Berichtet ein Institut in der Landessprache, muss die
   Erkennung sie treffen. Die Quote ist keine Genauigkeit — viele berichten
   zulässigerweise auf Englisch —, wohl aber eine untere Schranke: was NICHT
   Landessprache und NICHT Englisch ist, ist verdächtig.
2. **Die Selbstkonsistenz.** Zwei Berichte desselben Instituts zu verschiedenen
   Stichtagen sollten dieselbe Sprache tragen. Jede Abweichung ist ein Fehler
   der Erkennung oder ein echter Sprachwechsel — beides berichtenswert.

Aufruf: python3 scripts/probe_disdocs_language.py [--n 60] [--seed 20260915]
"""

from pathlib import Path
import argparse
import collections
import csv
import io
import random
import re
import sys
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "interim" / "disdocs_manifest.csv"
OUT = ROOT / "interim" / "disdocs_language.csv"
OUT_PAARE = ROOT / "interim" / "disdocs_language_paare.csv"

AGENT = "P3DH-research/1.0 (https://github.com/Tobias-Run/P3DH)"

# So viele Zeichen reichen für die Erkennung; mehr kostet nur Zeit. Gemessen
# ändert sich das Urteil zwischen 2.000 und 20.000 Zeichen praktisch nicht.
ZEICHEN = 20000

# Mindestabstand des Siegers zum Zweiten, gemessen in Treffern je 1.000 Wörter.
# Darunter heisst das Urteil `unsicher`: Tschechisch gegen Slowakisch und
# Dänisch gegen Norwegisch trennen sich über Funktionswörter nur knapp, und ein
# knapper Sieg ist dort keine Erkenntnis.
MIN_ABSTAND = 4.0

# Unter so vielen Wörtern wird gar nicht erst geurteilt.
MIN_WOERTER = 120

# Funktionswörter je Sprache. Bewusst kurz und bewusst nur Wörter, die in
# JEDEM Sachtext vorkommen — kein Fachvokabular, das die Erkennung an das
# Thema Bankenaufsicht binden würde.
STOPP = {
    "en": "the and of to in for is are with that this as be by on from not or",
    "de": "der die das und den von im ist für mit sich auch nicht eine dem des",
    "fr": "le la les des et du en une pour dans est que par sur au aux avec",
    "it": "il la di e che per non una del con sono nel alla dei gli come",
    "es": "el la los de y en que del las por para con una se es al",
    "pt": "o a de e que do da em para com não uma os as se por",
    "nl": "de het een en van in is dat op voor met te zijn niet aan door",
    "pl": "i w z na nie do się że jest oraz przez lub od dla po",
    "cs": "a v na se je že do to za pro ale nebo jako při podle bylo",
    "sk": "a v na sa je že do to za pre ale alebo ako pri podľa bolo",
    "sv": "och att det som en av för på med är till den de inte om",
    "da": "og at det som en af for på med er til den de ikke om",
    "no": "og at det som en av for på med er til den de ikke om",
    "fi": "ja on ei se että olla joka mutta kun niin myös sekä tai kuin",
    "hu": "a az és hogy nem is de egy meg ha vagy csak már még mint",
    "ro": "de la si in cu care nu pentru este pe din sa au mai ca",
    "bg": "и на в за не се от че да с като по или през при",
    "el": "και του της το των στο για με από που δεν να στη είναι",
    "hr": "i u na se je da za od ili kao po sa te su bio",
    "sl": "in v na se je da za od ali kot po pri so bil ter",
    "lt": "ir be su kad ne to iš per ar kaip nuo bei pagal buvo",
    "lv": "un ar par no to ka nav ka ir uz pec vai ta bija",
    "et": "ja on ei see et ning kui selle oma ka võib mis kõik siis",
    "ga": "agus an na is ar le do chun faoi seo sin nach mar go",
}
STOPPSAETZE = {k: set(v.split()) for k, v in STOPP.items()}

# Amtssprache je Sitzland — die Gegenprobe, nicht die Antwort. Ein Institut
# darf auf Englisch berichten; die Karte sagt nur, was ausser Englisch
# plausibel wäre.
LANDESSPRACHE = {
    "AT": "de", "BE": "nl", "BG": "bg", "CY": "el", "CZ": "cs", "DE": "de",
    "DK": "da", "EE": "et", "ES": "es", "FI": "fi", "FR": "fr", "GR": "el",
    "HR": "hr", "HU": "hu", "IE": "en", "IS": "en", "IT": "it", "LI": "de",
    "LT": "lt", "LU": "fr", "LV": "lv", "MT": "en", "NL": "nl", "NO": "no",
    "PL": "pl", "PT": "pt", "RO": "ro", "SE": "sv", "SI": "sl", "SK": "sk",
}

FELDER = ["lei", "bank_name", "country", "refdate", "sprache", "abstand",
          "landessprache", "urteil", "woerter", "status"]

WORT = re.compile(r"[^\W\d_]+", re.UNICODE)


def woerter(text):
    return WORT.findall((text or "").lower())


def erkenne(text, saetze=None, min_abstand=MIN_ABSTAND, min_woerter=MIN_WOERTER):
    """(sprache, abstand, n_woerter) — oder ("", 0.0, n) wenn unentscheidbar.

    Gezählt wird je Sprache, wie viele der Wörter Funktionswörter dieser
    Sprache sind, normiert auf 1.000 Wörter. Der Abstand zum Zweiten entscheidet
    mit: ein knapper Sieg zwischen Tschechisch und Slowakisch ist keine
    Erkenntnis, sondern ein Münzwurf mit Nachkommastellen.
    """
    saetze = saetze or STOPPSAETZE
    w = woerter(text)
    if len(w) < min_woerter:
        return "", 0.0, len(w)
    zaehler = collections.Counter(w)
    punkte = []
    for code, menge in saetze.items():
        treffer = sum(zaehler[x] for x in menge)
        punkte.append((1000.0 * treffer / len(w), code))
    punkte.sort(reverse=True)
    if len(punkte) < 2:
        return punkte[0][1], punkte[0][0], len(w)
    abstand = punkte[0][0] - punkte[1][0]
    if abstand < min_abstand:
        return "", round(abstand, 2), len(w)
    return punkte[0][1], round(abstand, 2), len(w)


def urteil_von(sprache, land, landessprache=None):
    """Wie die erkannte Sprache zum Sitzland steht.

    Kein Werturteil — auf Englisch zu berichten ist üblich und zulässig. Die
    Einstufung trennt nur das Erwartbare vom Erklärungsbedürftigen.
    """
    landessprache = landessprache or LANDESSPRACHE
    if not sprache:
        return "unsicher"
    amt = landessprache.get((land or "").upper())
    if amt and sprache == amt:
        return "landessprache"
    if sprache == "en":
        return "englisch"
    if not amt:
        return "land unbekannt"
    return "abweichend"


def lade_manifest(pfad=None):
    pfad = Path(pfad or MANIFEST)
    if not pfad.exists():
        return []
    with pfad.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def text_aus_paket(rohbytes, zeichen=ZEICHEN):
    """Erste PDF-Datei im ZIP, Text bis `zeichen`. ("" wenn keine da ist)."""
    from pypdf import PdfReader

    with zipfile.ZipFile(io.BytesIO(rohbytes)) as z:
        pdfs = [n for n in z.namelist() if n.lower().endswith(".pdf")]
        if not pdfs:
            return "", ""
        name = sorted(pdfs)[0]
        with z.open(name) as fh:
            leser = PdfReader(io.BytesIO(fh.read()))
            teile = []
            for seite in leser.pages:
                teile.append(seite.extract_text() or "")
                if sum(len(t) for t in teile) >= zeichen:
                    break
            return "".join(teile)[:zeichen], name


def paarstichprobe(zeilen, n, seed):
    """Institute mit MEHREREN Berichten, je zwei Stichtage.

    Die zufällige Stichprobe taugt für die Sprachverteilung, aber nicht für die
    Selbstkonsistenz: sie enthielt genau ein Institut mit zwei Berichten, und
    aus n=1 folgt nichts. Wer die Gegenprobe will, muss gezielt ziehen —
    zufällig zu ziehen und dann über das Ergebnis zu reden wäre eine Aussage
    über das Glück der Ziehung.
    """
    je = collections.defaultdict(list)
    for r in zeilen:
        je[r["lei"]].append(r)
    mehrfach = sorted((l, v) for l, v in je.items() if len(v) >= 2)
    r = random.Random(seed)
    gewaehlt = r.sample(mehrfach, min(n, len(mehrfach)))
    aus = []
    for _, v in gewaehlt:
        aus.extend(sorted(v, key=lambda x: x["refdate"])[:2])
    return aus


def konsistenz(zeilen):
    """(Paare, davon gleichsprachig) über Institute mit mehreren Berichten."""
    je = collections.defaultdict(set)
    for z in zeilen:
        if z["status"] == "ok" and z["sprache"]:
            je[z["lei"]].add(z["sprache"])
    mehr = {l: s for l, s in je.items()
            if len([z for z in zeilen if z["lei"] == l
                    and z["status"] == "ok" and z["sprache"]]) >= 2}
    return len(mehr), sum(1 for s in mehr.values() if len(s) == 1)


def build(n=60, seed=20260915, paare=False):
    zeilen = lade_manifest()
    if not zeilen:
        print(f"ERROR: {MANIFEST} fehlt — erst scripts/build_disdocs_manifest.py")
        return []
    if paare:
        stichprobe = paarstichprobe(zeilen, n, seed)
        print(f"DISDOCS im Manifest: {len(zeilen)} · Paarstichprobe: "
              f"{len(stichprobe)} Berichte von {len(stichprobe) // 2} Instituten")
    else:
        stichprobe = random.Random(seed).sample(zeilen, min(n, len(zeilen)))
        print(f"DISDOCS im Manifest: {len(zeilen)} · Stichprobe: {len(stichprobe)}")

    aus = []
    for i, r in enumerate(stichprobe, 1):
        satz = {"lei": r["lei"], "bank_name": r.get("bank_name", ""),
                "country": r.get("country", ""), "refdate": r.get("refdate", ""),
                "sprache": "", "abstand": "", "landessprache":
                    LANDESSPRACHE.get((r.get("country") or "").upper(), ""),
                "urteil": "", "woerter": 0, "status": ""}
        try:
            req = urllib.request.Request(r["url"], headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=180) as fh:
                roh = fh.read()
            text, datei = text_aus_paket(roh)
            if not datei:
                satz["status"] = "kein PDF im Paket"
            else:
                sp, ab, nw = erkenne(text)
                satz.update(sprache=sp, abstand=ab, woerter=nw,
                            urteil=urteil_von(sp, r.get("country")),
                            status="ok")
        except Exception as e:                       # noqa: BLE001
            satz["status"] = f"Fehler: {type(e).__name__}"
        aus.append(satz)
        if i % 10 == 0:
            print(f"  {i}/{len(stichprobe)}")

    ziel = OUT_PAARE if paare else OUT
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with ziel.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(aus)
    print(f"✓ {ziel}  ({len(aus)} Zeilen)")
    for s in bericht(aus):
        print("  " + s)
    return aus


def bericht(zeilen):
    ok = [z for z in zeilen if z["status"] == "ok"]
    b = [f"gelesen: {len(ok)} von {len(zeilen)} · "
         + "  ".join(f"{k}={v}" for k, v in
                     collections.Counter(z["status"] for z in zeilen).items())]
    if not ok:
        return b
    erkannt = [z for z in ok if z["sprache"]]
    b.append(f"Sprache erkannt: {len(erkannt)} von {len(ok)} "
             f"({100 * len(erkannt) / len(ok):.0f} %) — der Rest ist `unsicher`, "
             f"weil der Abstand zum Zweiten zu klein war")
    b.append("Sprachen: " + "  ".join(
        f"{k}={v}" for k, v in
        collections.Counter(z["sprache"] for z in erkannt).most_common()))
    u = collections.Counter(z["urteil"] for z in ok)
    b.append("Verhältnis zum Sitzland: " + "  ".join(
        f"{k}={v}" for k, v in u.most_common()))
    # Die Zahl, die #38 braucht: wie viel des Korpus eine Schlagwortsuche auf
    # Englisch ueberhaupt erreichen wuerde.
    en = sum(1 for z in ok if z["sprache"] == "en")
    b.append(f"→ Eine Suche NUR auf Englisch erreichte {en} von {len(ok)} "
             f"Berichten ({100 * en / len(ok):.0f} %). Genau die Verzerrung, "
             f"vor der #38 warnt — jetzt beziffert.")
    n_inst, n_gleich = konsistenz(zeilen)
    if n_inst:
        b.append(f"Selbstkonsistenz: {n_gleich} von {n_inst} Instituten mit "
                 f"mehreren Berichten tragen durchgehend DIESELBE Sprache")
    else:
        b.append("Selbstkonsistenz: in dieser Stichprobe kein Institut mit "
                 "zwei lesbaren Berichten — mit --paare gezielt ziehen")
    if any(z["urteil"] == "abweichend" for z in ok):
        b.append("  abweichend (weder Landessprache noch Englisch):")
        for z in ok:
            if z["urteil"] == "abweichend":
                b.append(f"    {z['country']} {z['bank_name'][:34]:36s} "
                         f"erkannt {z['sprache']} (erwartet "
                         f"{z['landessprache']}), Abstand {z['abstand']}")
    return b


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=60)
    p.add_argument("--seed", type=int, default=20260915)
    p.add_argument("--paare", action="store_true",
                   help="gezielt Institute mit mehreren Berichten ziehen "
                        "(Gegenprobe auf Selbstkonsistenz)")
    a = p.parse_args()
    build(a.n, a.seed, a.paare)
