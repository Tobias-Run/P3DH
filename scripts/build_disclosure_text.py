"""Berichtsumfang gegen Offenlegungsumfang (#38, Punkt 3 zweite Hälfte).

Das Issue nennt zwei Auswertungen. Die erste — „sagt der Text, was die Zahlen
sagen?" — ist eine Leseaufgabe über 31 Sprachen und braucht ein Modell
(38b–38e). Die zweite nennt es selbst als **billiger zu haben**:

> Zweite Auswertung, billiger zu haben: **Berichtsumfang gegen
> Offenlegungsumfang.** Viel Text bei wenigen tatsächlich offengelegten
> Templates ist ein eigenes Muster.

Sie ist vollständig deterministisch, braucht kein Modell und keine Lizenz —
und sie verbindet zum ersten Mal die beiden Korpora, die EDAP nebeneinander
statt gegeneinander stellt: den qualitativen Bericht und die Zahlenmeldung
desselben Instituts zum selben Stichtag.

## Der Korpus bleibt im Arbeitsspeicher

1.073 Pakete, rund 2 GB. Sie werden geladen, ausgewertet und verworfen; auf
Platte bleiben nur die Kennzahlen. Das ist kein Sparzwang, sondern die saubere
Form: ein 2-GB-Korpus im Repo wäre ein zweiter Zustand neben `raw/`, und die
Kennzahlen sind alles, was die Auswertung braucht. Preis dafür ist, dass ein
erneuter Lauf erneut lädt.

## Vier Fallen, die das Ergebnis sonst erfänden

**1. Kein Textlayer ist nicht null Zeichen.** Rund 3 % der PDFs sind Scans
ohne Textebene. Sie mit 0 Zeichen zu führen hiesse, einen gescannten
200-Seiten-Bericht als den knappsten im Bestand auszuweisen. Sie bekommen
`textebene = nein` und fallen aus der Textauswertung — gezählt, nicht
verschwiegen.

**2. Zeichen sind sprachabhängig.** Ein deutscher Bericht braucht für denselben
Inhalt andere Zeichenzahlen als ein englischer. Ein roher Vergleich über den
Korpus misst zur Hälfte die Sprachverteilung. Deshalb wird die Sprache je
Dokument bestimmt (deterministisch, aus #38a) und die Auswertung nach ihr
geschichtet.

**3. Beides wächst mit der Grösse.** Grosse Institute schreiben längere
Berichte *und* legen mehr Templates offen. Eine rohe Korrelation zwischen
beidem misst die Bilanzsumme — der Fehler aus #43, #45, #11 und #44. Deshalb
wird gegen `trea_eur` geschichtet und die Steigung gegen die Grösse
mitberichtet, statt sie zu unterschlagen.

**4. Ein Paket kann mehrere PDFs enthalten.** Nur das erste zu lesen — wie die
Stichprobe in `probe_disdocs_language.py`, wo es für die Sprachbestimmung
genügt — unterschlüge bei einem in Teilen eingereichten Bericht den Rest.
Hier werden alle summiert.

## Grenzen

- **Zeichen sind kein Informationsgehalt.** Ein langer Bericht kann leer sein
  und ein kurzer dicht. Gemessen wird Umfang, nicht Gehalt; das ist genau die
  Grenze, an der 38e mit einem Modell weitermacht.
- **Keine Aussage über Absicht** (Randbedingung des Issues).
"""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import csv
import io
import logging
import math
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from probe_disdocs_language import erkenne, urteil_von  # noqa: E402

MANIFEST = ROOT / "interim" / "disdocs_manifest.csv"
OMISSION = ROOT / "processed" / "omission_profile.csv"
SKALA = ROOT / "processed" / "scale_flags.csv"
OUT = ROOT / "processed" / "disclosure_text.csv"

UA = "P3DH-Pipeline/1.0 (+https://github.com/Tobias-Run/P3DH)"
ARBEITER = 6

# Unter dieser Ausbeute trägt ein PDF keine Textebene, sondern ein Bild davon.
# Die Schwelle stammt aus `probe_disdocs.py`, wo sie am Bestand belegt ist.
MIN_ZEICHEN_JE_SEITE = 200

# Zeichen, die in die Spracherkennung gehen. Mehr ändert das Urteil nicht und
# kostet nur Zeit — die Funktionswörter stehen auf jeder Seite.
SPRACHPROBE = 20000

# Grössenklassen nach TREA. Die Grenzen sind die Terzile des Bestands, nicht
# gesetzt: eine runde Zahl träfe hier nichts, weil die Verteilung über fünf
# Grössenordnungen läuft.
def groessenklassen(werte):
    """Terzilgrenzen aus den vorhandenen TREA-Werten."""
    w = sorted(v for v in werte if v)
    if len(w) < 3:
        return (0.0, 0.0)
    return (w[len(w) // 3], w[2 * len(w) // 3])


def groessenklasse(trea, grenzen):
    if not trea:
        return "unbekannt"
    unten, oben = grenzen
    if trea < unten:
        return "klein"
    return "gross" if trea >= oben else "mittel"


def textebene_von(zeichen, seiten, min_zeichen_je_seite=MIN_ZEICHEN_JE_SEITE):
    """Trägt das Dokument Text, oder ist es ein Bild davon?

    Ohne Seiten gibt es keine Aussage — nicht „nein". Ein Paket ohne PDF ist
    etwas anderes als ein Scan, und beides etwas anderes als ein leerer
    Bericht.
    """
    if not seiten:
        return ""
    return "ja" if zeichen / seiten >= min_zeichen_je_seite else "nein"


def lies_paket(rohbytes, sprachprobe=SPRACHPROBE):
    """ZIP -> (n_pdf, n_seiten, n_zeichen, Textanfang für die Sprach-ID).

    Alle PDFs des Pakets, alle Seiten. Ein in Teilen eingereichter Bericht
    zählt sonst nur zu seinem ersten Teil.
    """
    from pypdf import PdfReader

    n_pdf = seiten = zeichen = 0
    anfang = []
    with zipfile.ZipFile(io.BytesIO(rohbytes)) as z:
        for name in sorted(z.namelist()):
            if not name.lower().endswith(".pdf"):
                continue
            n_pdf += 1
            try:
                leser = PdfReader(io.BytesIO(z.read(name)))
            except Exception:
                continue
            seiten += len(leser.pages)
            for seite in leser.pages:
                t = seite.extract_text() or ""
                zeichen += len(t)
                if sum(len(x) for x in anfang) < sprachprobe:
                    anfang.append(t)
    return n_pdf, seiten, zeichen, "".join(anfang)[:sprachprobe]


def hole_und_lies(zeile):
    """Eine Manifestzeile -> Kennzahlen. Fehler werden Zeilen, nicht Abbrüche."""
    import requests

    try:
        r = requests.get(zeile["url"], timeout=180, headers={"User-Agent": UA})
        r.raise_for_status()
        groesse = len(r.content)
    except Exception as e:
        return {**zeile, "fehler": str(e)[:70]}
    try:
        n_pdf, seiten, zeichen, anfang = lies_paket(r.content)
    except Exception as e:
        return {**zeile, "paket_mb": round(groesse / 1e6, 3),
                "fehler": str(e)[:70]}
    # `erkenne` liefert auch die Wortzahl: zu wenige Wörter und ein knapper
    # Vorsprung führen beide zu `sprache = ""`, sind aber verschiedene Gründe.
    sprache, abstand, n_woerter = erkenne(anfang)
    return {
        **zeile,
        "paket_mb": round(groesse / 1e6, 3),
        "n_pdf": n_pdf,
        "n_seiten": seiten,
        "n_zeichen": zeichen,
        "zeichen_je_seite": round(zeichen / seiten, 1) if seiten else "",
        "textebene": textebene_von(zeichen, seiten),
        "sprache": sprache,
        "sprach_abstand": round(abstand, 2) if abstand else "",
        "sprach_woerter": n_woerter,
        "sprach_urteil": urteil_von(sprache, zeile.get("country", "")),
        "fehler": "",
    }


def lade_offenlegung(pfad=OMISSION):
    """(lei, scope, refPeriod) -> Offenlegungsbreite aus #34/#44."""
    if not Path(pfad).exists():
        return {}
    with open(pfad, encoding="utf-8") as fh:
        return {(r["lei"], r["scope"], r["refPeriod"]): r
                for r in csv.DictReader(fh)}


def lade_trea(pfad=SKALA):
    """(lei, scope, refPeriod) -> TREA. Nur die Reportzeilen tragen ihn."""
    if not Path(pfad).exists():
        return {}
    werte = {}
    with open(pfad, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("ebene") != "report" or not r.get("trea_eur"):
                continue
            try:
                werte[(r["lei"], r["scope"], r["refPeriod"])] = float(r["trea_eur"])
            except ValueError:
                continue
    return werte


def steigung(paare):
    """Kleinste Quadrate -> (a, b, r²) für y = a·x + b.

    Dieselbe Funktion wie in `check_proportionality.py`, und aus demselben
    Grund: ohne r² gegen die Grösse ist jede Aussage über „viel Text" eine
    Aussage über grosse Banken.
    """
    n = len(paare)
    if n < 3:
        return (None, None, None)
    sx = sum(x for x, _ in paare)
    sy = sum(y for _, y in paare)
    sxx = sum(x * x for x, _ in paare)
    sxy = sum(x * y for x, y in paare)
    nenner = n * sxx - sx * sx
    if not nenner:
        return (None, None, None)
    a = (n * sxy - sx * sy) / nenner
    b = (sy - a * sx) / n
    mittel = sy / n
    sst = sum((y - mittel) ** 2 for _, y in paare)
    if not sst:
        return (a, b, None)
    ssr = sum((y - (a * x + b)) ** 2 for x, y in paare)
    return (a, b, 1 - ssr / sst)


FELDER = ["lei", "bank_name", "country", "scope", "refPeriod", "im_xbrl_bestand",
          "paket_mb", "n_pdf", "n_seiten", "n_zeichen", "zeichen_je_seite",
          "textebene", "sprache", "sprach_abstand", "sprach_woerter",
          "sprach_urteil",
          "n_offengelegt", "n_ausgelassen", "quote_gegen_erwartung",
          "trea_eur", "groessenklasse", "zeichen_je_template", "fehler"]


def main():
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    if not MANIFEST.exists():
        print("DISDOCS-Manifest fehlt — erst build_disdocs_manifest.py laufen lassen.")
        return
    with MANIFEST.open(encoding="utf-8") as fh:
        zeilen = [{"lei": r["lei"], "bank_name": r["bank_name"],
                   "country": r["country"], "scope": r["consolidation"],
                   "refPeriod": r["refdate"],
                   "im_xbrl_bestand": r["im_xbrl_bestand"], "url": r["url"]}
                  for r in csv.DictReader(fh)]
    grenze = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if grenze:
        zeilen = zeilen[:grenze]
        print(f"AUSSCHNITT: nur die ersten {grenze} Pakete")
    print(f"{len(zeilen)} DISDOCS-Pakete, {ARBEITER} Arbeiter")

    with ThreadPoolExecutor(max_workers=ARBEITER) as ex:
        ergebnisse = list(ex.map(hole_und_lies, zeilen))

    offen = lade_offenlegung()
    trea = lade_trea()
    grenzen = groessenklassen(trea.values())
    for e in ergebnisse:
        e.pop("url", None)
        schluessel = (e["lei"], e["scope"], e["refPeriod"])
        o = offen.get(schluessel, {})
        e["n_offengelegt"] = o.get("n_offengelegt", "")
        e["n_ausgelassen"] = o.get("n_ausgelassen", "")
        e["quote_gegen_erwartung"] = o.get("quote_gegen_erwartung", "")
        t = trea.get(schluessel)
        e["trea_eur"] = t if t else ""
        e["groessenklasse"] = groessenklasse(t, grenzen)
        n_off = o.get("n_offengelegt")
        e["zeichen_je_template"] = (
            round(e.get("n_zeichen", 0) / int(n_off))
            if n_off and int(n_off) and e.get("n_zeichen") else "")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FELDER)
        w.writeheader()
        for z in sorted(ergebnisse,
                        key=lambda r: (r["lei"], r["scope"], r["refPeriod"])):
            w.writerow({f: z.get(f, "") for f in FELDER})
    print(f"  -> {OUT.relative_to(ROOT)} ({len(ergebnisse)} Zeilen)")
    bericht(ergebnisse)


def bericht(zeilen):
    from collections import Counter
    import statistics as st

    fehler = [z for z in zeilen if z.get("fehler")]
    print(f"\nnicht abrufbar/lesbar: {len(fehler)}")
    mit = [z for z in zeilen if not z.get("fehler")]
    print("Textebene:", dict(Counter(z["textebene"] for z in mit)))
    print("Sprachen:", dict(Counter(z["sprache"] for z in mit).most_common(8)))

    text = [z for z in mit if z["textebene"] == "ja"]
    if text:
        zz = sorted(z["n_zeichen"] for z in text)
        print(f"\nZeichen je Bericht (nur mit Textebene, n={len(zz)}): "
              f"Median {st.median(zz):,.0f}, min {zz[0]:,}, max {zz[-1]:,}")

    paare = [(math.log10(float(z["trea_eur"])), math.log10(z["n_zeichen"]))
             for z in text if z["trea_eur"] and z["n_zeichen"] > 0]
    a, b, r2 = steigung(paare)
    if r2 is not None:
        print(f"Textumfang gegen Groesse (beide log10, n={len(paare)}): "
              f"Steigung {a:.3f}, r² {r2:.3f}")

    print("\nZeichen je offengelegtem Template, nach Groesse und Sprache:")
    for kl in ("klein", "mittel", "gross"):
        g = [z for z in text if z["groessenklasse"] == kl
             and z["zeichen_je_template"]]
        if not g:
            continue
        for spr in ("en", "de"):
            s = [z for z in g if z["sprache"] == spr]
            if len(s) < 3:
                continue
            v = sorted(z["zeichen_je_template"] for z in s)
            print(f"  {kl:<7} {spr}  n={len(s):>3}  Median {st.median(v):>8,.0f}")


if __name__ == "__main__":
    main()
