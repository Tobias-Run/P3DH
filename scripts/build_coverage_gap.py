"""Die Negativmenge: welche beaufsichtigten Institute fehlen im Hub? (#42)

Ausgabe: processed/coverage_gap.csv

## Die Umkehrung der Frage

Alles andere im Backlog fragt, was in den Daten steht. Hier geht es um das
Gegenteil — welche Institute müssten offenlegen und tauchen gar nicht auf.
Das ist „Fehlt ≠ Null" auf Populationsebene: nicht „diese Zahl ist auffällig",
sondern „hier fehlt eine ganze Bank".

## Warum die rohe Differenz nichts taugt

Die EZB-Liste der beaufsichtigten Einheiten führt 2.863 LEIs, unser Bestand
508. Die rohe Differenz sind **2.479** — und sie ist wertlos:

    Deutschland   1.093      Sparkassen und Genossenschaftsbanken
    Österreich      363      Raiffeisensektor
    Frankreich      264

Das sind fast durchweg kleine, nicht komplexe Institute, die nach CRR
Art. 433b/c gar nicht einzeln quartalsweise offenlegen. Sie als „fehlend" zu
zählen misst die Proportionalität, nicht eine Lücke.

## Der Konzerngraph steht in der Quelle selbst

Das Issue verlangt #32 als Voraussetzung, weil sonst jede Tochter als fehlend
gilt, die korrekt über die Mutter konsolidiert offenlegt. Ein GLEIF-Abruf ist
dafür aber nicht nötig: **die EZB-Liste trägt die Hierarchie mit.** In Spalte B
steht eine laufende Nummer nur beim Gruppenkopf; die folgenden Zeilen ohne
Nummer sind dessen Töchter.

    2   549300DYPOFMXOR7XM56   Crelan SA ; Crelan NV        Belgium
        CVRWQDHDBEPUUVU2FD09   Crelan Home Loan SCF         France

Damit ist je Einheit entscheidbar, ob ihr Gruppenkopf bei uns meldet.

## Die vier Einordnungen

    meldet_selbst          die Einheit steht in unserem Bestand
    ueber_gruppe           ihr Gruppenkopf steht bei uns — konsolidiert
                           abgedeckt, keine Lücke
    nicht_abgedeckt        weder sie noch ihr Gruppenkopf; bei einem
                           SIGNIFIKANTEN Institut eine offene Frage
    keine_gruppe_bekannt   Einheit ohne erkennbaren Kopf in der Liste

## Was das NICHT ist

Ein fehlendes Institut ist **kein Vorwurf**. Die überwiegende Mehrheit hat eine
legitime Erklärung — Proportionalität, jährliche statt quartalsweiser
Offenlegung, oder eine Offenlegung ausserhalb des Hubs. Die Spalte heisst
deshalb `einordnung` und nicht `verstoss`.

## Abdeckung der Quellen ist NICHT deckungsgleich

Die SSM-Liste umfasst den Euroraum (plus enge Zusammenarbeit). Unser Bestand
umfasst 31 Länder, darunter Schweden, Dänemark und Norwegen. Institute, die nur
bei uns stehen, sind deshalb in aller Regel **kein Fehler der EZB-Liste**,
sondern liegen ausserhalb ihres Geltungsbereichs. Der Bericht weist beide
Richtungen getrennt aus; eine EU-weite Vollständigkeit wird nirgends behauptet.

Aufruf: python3 scripts/build_coverage_gap.py [--xlsx PFAD]
"""

from pathlib import Path
import argparse
import collections
import csv
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "processed" / "entity_meta.csv"
OUT = ROOT / "processed" / "coverage_gap.csv"

# Die Übersichtsseite nennt die aktuelle Datei; der Monat wandert.
SEITE = "https://www.bankingsupervision.europa.eu/banking/list/who/html/index.en.html"
BASIS = "https://www.bankingsupervision.europa.eu"

LEI_RE = re.compile(r"^[A-Z0-9]{18}\d{2}$")

# Die beiden Blätter haben VERSCHIEDENE Layouts — SIs führt den LEI in Spalte C,
# LSIs in Spalte B. Fest verdrahtete Indizes lieferten für LSIs null Zeilen, und
# zwar lautlos. Deshalb werden die Spalten an der Kopfzeile erkannt.
KOPF = {"lei": "LEI", "typ": "Type", "name": "Name",
        "land": "Country of establishment"}

FELDER = ["lei", "name", "typ", "land", "signifikanz",
          "gruppenkopf_lei", "gruppenkopf_name", "im_bestand",
          "gruppe_im_bestand", "einordnung"]


def xlsx_url():
    """Den aktuellen Dateinamen von der Übersichtsseite lesen, nicht raten."""
    with urllib.request.urlopen(SEITE, timeout=60) as h:
        html = h.read().decode("utf-8", "replace")
    m = re.search(r'href="(/ecb/pub/pdf/ssm\.listofsupervisedentities\d+\.en\.xlsx)"', html)
    if not m:
        raise RuntimeError("Kein XLSX-Link auf der EZB-Übersichtsseite gefunden")
    return BASIS + m.group(1)


def lade(pfad=None):
    if pfad:
        return Path(pfad)
    ziel = Path("/tmp/ssm_liste.xlsx")
    url = xlsx_url()
    print(f"  hole {url.rsplit('/', 1)[-1]}")
    with urllib.request.urlopen(url, timeout=180) as h:
        ziel.write_bytes(h.read())
    return ziel


def spalten_von(ws):
    """Kopfzeile finden und die gebrauchten Spalten daran festmachen."""
    for row in ws.iter_rows(min_row=1, max_row=25, values_only=True):
        vals = ["" if c is None else str(c).strip() for c in row]
        if not any(v.startswith("LEI") for v in vals):
            continue
        gefunden = {}
        for feld, kopf in KOPF.items():
            for i, v in enumerate(vals):
                if v.startswith(kopf):
                    gefunden[feld] = i
                    break
        if "lei" in gefunden:
            return gefunden
    raise RuntimeError("Kopfzeile mit LEI nicht gefunden")


def lies_blatt(ws, signifikanz):
    """Zeilen mit LEI, samt Gruppenkopf aus der laufenden Nummer links davor.

    Die Nummer steht NUR beim Kopf. Jede folgende Zeile ohne Nummer gehört zu
    demselben Kopf — so trägt die Liste den Konzerngraphen, ohne ihn zu nennen.

    Nur das SI-Blatt führt diese Nummerierung. Im LSI-Blatt gibt es keine
    Gruppenstruktur; dort bleibt der Kopf leer, und die Einordnung sagt das
    ausdrücklich statt eine Gruppe zu erfinden.
    """
    SPALTEN = spalten_von(ws)
    lei_spalte = SPALTEN["lei"]
    aus, kopf = [], None
    for row in ws.iter_rows(values_only=True):
        vals = ["" if c is None else str(c).strip() for c in row]
        breite = max(SPALTEN.values()) + 1
        if len(vals) < breite:
            vals += [""] * (breite - len(vals))
        lei = vals[lei_spalte]
        if not LEI_RE.match(lei):
            continue
        # Die laufende Nummer steht unmittelbar links vom LEI — und nur dort,
        # wo das Blatt sie führt.
        nummer = vals[lei_spalte - 1] if lei_spalte > 0 else ""
        nummer = nummer if nummer.isdigit() else ""
        eintrag = {"lei": lei,
                   "name": vals[SPALTEN["name"]] if "name" in SPALTEN else "",
                   "typ": vals[SPALTEN["typ"]] if "typ" in SPALTEN else "",
                   "land": vals[SPALTEN["land"]] if "land" in SPALTEN else "",
                   "signifikanz": signifikanz}
        if nummer:                      # neue Gruppe beginnt
            kopf = eintrag
            eintrag["gruppenkopf_lei"] = lei
            eintrag["gruppenkopf_name"] = eintrag["name"]
        elif kopf:
            eintrag["gruppenkopf_lei"] = kopf["lei"]
            eintrag["gruppenkopf_name"] = kopf["name"]
        else:
            eintrag["gruppenkopf_lei"] = ""
            eintrag["gruppenkopf_name"] = ""
        aus.append(eintrag)
    return aus


def bestand_index(meta):
    """Unser Bestand, nachschlagbar — auch über den 18-stelligen LEI-Kern.

    Drei Kennzeichen im Bestand sind KEINE gültigen LEIs, sondern ein
    Länderpräfix plus abgeschnittener LEI:

        EZB            9695005MSX1OYEMGDF46   BPCE S.A.
        unser Bestand  FR9695005MSX1OYEMGDF   Groupe BPCE

    Dieselbe Einheit, zwei Schreibweisen. Ein reiner String-Vergleich zählte
    sie als fehlend — und mit ihnen ihre gesamte Gruppe: 52 Caisses régionales
    unter Crédit Agricole, 43 Caisses d'Épargne unter BPCE, 9 österreichische
    Volksbanken. 104 der ursprünglich 126 „nicht abgedeckten" signifikanten
    Institute waren allein dieser Schreibweise geschuldet.

    Der Kern ist 18 Zeichen lang, die beiden Prüfziffern kommen dahinter — ein
    Abgleich Kern gegen Kern ist deshalb eindeutig und keine Namensheuristik.
    """
    exakt = set(meta)
    kern = {}
    for l in meta:
        k = l[2:] if not LEI_RE.match(l) and len(l) == 20 else l[:18]
        kern.setdefault(k, l)
    return exakt, kern


def _drin(lei, exakt, kern):
    return lei in exakt or lei[:18] in kern


def einordnen(zeilen, bestand):
    """Fünf Zustände — und der fünfte ist der ehrlichste.

    Die EZB-Hierarchie ist FLACH: Kopf, darunter alle Einheiten der Gruppe,
    ohne Zwischenstufen. Das trifft den Fall Novo Banco. Die Gruppe hat als
    Kopf den Private-Equity-Halter `LSF Nani Investments S.à.r.l.`, der bei uns
    nicht meldet — aber `NOVO BANCO, S.A.` in der Mitte meldet sehr wohl, und
    dessen Töchter BEST und Novo Banco dos Açores sind damit sachlich
    abgedeckt. Die flache Liste kann das nicht zeigen.

    `gruppe_meldet_teilweise` sagt genau das und nicht mehr: der Kopf meldet
    nicht, aber ein anderes Mitglied derselben Gruppe tut es. Das ist weniger
    als Abdeckung und deutlich mehr als eine Lücke — beides zu behaupten wäre
    falsch.
    """
    exakt, kern = bestand if isinstance(bestand, tuple) else (set(bestand), {})
    melder_je_gruppe = collections.defaultdict(int)
    for z in zeilen:
        if z["gruppenkopf_lei"] and _drin(z["lei"], exakt, kern):
            melder_je_gruppe[z["gruppenkopf_lei"]] += 1
    for z in zeilen:
        selbst = _drin(z["lei"], exakt, kern)
        kopf = z["gruppenkopf_lei"]
        gruppe = bool(kopf) and _drin(kopf, exakt, kern)
        z["im_bestand"] = "true" if selbst else "false"
        z["gruppe_im_bestand"] = "true" if gruppe else "false"
        if selbst:
            z["einordnung"] = "meldet_selbst"
        elif gruppe:
            z["einordnung"] = "ueber_gruppe"
        elif not kopf:
            z["einordnung"] = "keine_gruppe_bekannt"
        elif melder_je_gruppe.get(kopf):
            z["einordnung"] = "gruppe_meldet_teilweise"
        else:
            z["einordnung"] = "nicht_abgedeckt"
    return zeilen


def build(xlsx=None):
    import openpyxl
    pfad = lade(xlsx)
    wb = openpyxl.load_workbook(pfad, data_only=True)
    zeilen = lies_blatt(wb["SIs"], "SI") + lies_blatt(wb["LSIs"], "LSI")

    # Dieselbe Einheit kann in beiden Blättern stehen; SI gewinnt.
    gesehen = {}
    for z in zeilen:
        if z["lei"] not in gesehen or z["signifikanz"] == "SI":
            gesehen[z["lei"]] = z
    zeilen = list(gesehen.values())

    with META.open(encoding="utf-8") as fh:
        meta = {r["lei"]: r for r in csv.DictReader(fh)}
    einordnen(zeilen, bestand_index(meta))

    zeilen.sort(key=lambda z: (z["signifikanz"], z["land"], z["lei"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    print(f"✓ {OUT}  ({len(zeilen)} beaufsichtigte Einheiten)")
    for s in bericht(zeilen, meta):
        print("  " + s)
    return zeilen


def bericht(zeilen, meta):
    ssm_kern = {z["lei"][:18] for z in zeilen}
    nur_bei_uns = sorted(l for l in meta
                         if l not in {z["lei"] for z in zeilen}
                         and (l[2:] if len(l) == 20 else l)[:18] not in ssm_kern
                         and l[:18] not in ssm_kern)
    aus = [f"EZB-Liste: {len(zeilen)} Einheiten · unser Bestand: {len(meta)}"]
    for sig in ("SI", "LSI"):
        teil = [z for z in zeilen if z["signifikanz"] == sig]
        c = collections.Counter(z["einordnung"] for z in teil)
        aus.append(f"{sig} (n={len(teil)}): " +
                   "  ".join(f"{k}={v}" for k, v in sorted(c.items())))
    offen = [z for z in zeilen
             if z["signifikanz"] == "SI" and z["einordnung"] == "nicht_abgedeckt"]
    aus.append(f"Signifikant und weder selbst noch über die Gruppe abgedeckt: {len(offen)}")
    if offen:
        nach_land = collections.Counter(z["land"] for z in offen)
        aus.append("  nach Land: " +
                   "  ".join(f"{k or '?'}={v}" for k, v in nach_land.most_common(6)))
    aus.append(f"Nur in unserem Bestand (ausserhalb des SSM-Bereichs): {len(nur_bei_uns)}")
    laender = collections.Counter(meta[l].get("country", "?") for l in nur_bei_uns)
    aus.append("  nach Land: " +
               "  ".join(f"{k}={v}" for k, v in laender.most_common(8)))
    return aus


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", help="lokale Kopie der EZB-Liste (sonst wird geholt)")
    a = ap.parse_args()
    build(a.xlsx)
