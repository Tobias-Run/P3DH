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

## Die sechs Einordnungen

    meldet_selbst            die Einheit steht in unserem Bestand
    ueber_gruppe             ihr Gruppenkopf steht bei uns — konsolidiert
                             abgedeckt, keine Lücke
    gruppe_meldet_teilweise  der Kopf meldet nicht, ein anderes Mitglied
                             derselben Gruppe aber schon
    namensgleicher_melder    keine LEI trifft, aber ein Haus gleichen Namens
                             im selben Land meldet — Verdacht, keine Aussage
    nicht_abgedeckt          weder sie noch ihr Gruppenkopf noch ein
                             gleichnamiges Haus; bei einem SIGNIFIKANTEN
                             Institut eine offene Frage
    keine_gruppe_bekannt     Einheit ohne erkennbaren Kopf in der Liste

## Die LEI der Aufsicht ist nicht immer die LEI der Offenlegung

Rein über die LEI gerechnet fehlten **12** signifikante Institute. Elf davon
melden nachweislich — nur unter einer anderen LEI als der, die die EZB-Liste
führt: Griechenlands Gruppe steht dort als `Piraeus Bank S.A.`, offen legt sie
als `Piraeus Financial Holdings`; die neun österreichischen Volksbanken melden
über den Verbund `Volksbank Wien`. Sie als fehlend zu zählen wäre eine
Unterstellung, sie stillschweigend als abgedeckt zu zählen eine Behauptung.
`namensgleicher_melder` sagt beides nicht und weist den Treffer in
`namenstreffer` aus, damit er nachprüfbar ist.

Übrig bleibt **ein** signifikantes Institut ohne jede Spur — und das ist die
Zahl, die #42 sucht.

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
          "gruppe_im_bestand", "einordnung", "namenstreffer"]


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


def laendernamen(ws):
    """Die Ländernamen, wie das SI-Blatt sie schreibt.

    Nicht fest verdrahtet, sondern aus dem Blatt selbst: die Liste der
    SSM-Länder ändert sich (Bulgarien und Kroatien kamen dazu), und eine
    handgepflegte Kopie veraltete lautlos.
    """
    spalten = spalten_von(ws)
    if "land" not in spalten:
        return frozenset()
    i = spalten["land"]
    aus = set()
    for row in ws.iter_rows(values_only=True):
        vals = ["" if c is None else str(c).strip() for c in row]
        if len(vals) > i and vals[i] and not vals[i].startswith(KOPF["land"]):
            aus.add(vals[i])
    return frozenset(aus)


def lies_blatt(ws, signifikanz, laender=frozenset()):
    """Zeilen mit LEI, samt Gruppenkopf aus der laufenden Nummer links davor.

    Die Nummer steht NUR beim Kopf. Jede folgende Zeile ohne Nummer gehört zu
    demselben Kopf — so trägt die Liste den Konzerngraphen, ohne ihn zu nennen.

    Nur das SI-Blatt führt diese Nummerierung. Im LSI-Blatt gibt es keine
    Gruppenstruktur; dort bleibt der Kopf leer, und die Einordnung sagt das
    ausdrücklich statt eine Gruppe zu erfinden.

    ## Das LSI-Blatt hat gar keine Land- und keine Namensspalte

    Es ist nach Ländern GEGLIEDERT: eine Zeile „Belgium", darunter die
    nationale Aufsicht, darunter die Institute — Name und Zwischenüberschrift
    in derselben Spalte. Wer nur nach Spaltenköpfen sucht, bekommt für alle
    2.066 LSIs ein leeres Land und einen leeren Namen, und zwar lautlos. Genau
    die Falle, die weiter oben schon einmal zuschlug (feste Spaltenindizes) —
    hier noch teurer, weil #42 die Abdeckung JE LAND ausweisen muss und 72 %
    der Grundgesamtheit LSIs sind.

    Das Land wird deshalb wie die Gruppennummer mitgeführt: als laufende
    Überschrift. Erkannt wird sie daran, dass ihr Text einer der Ländernamen
    ist, die das SI-Blatt führt (`laender`) — kein eingebauter Ländervorrat,
    der veralten könnte.
    """
    SPALTEN = spalten_von(ws)
    lei_spalte = SPALTEN["lei"]
    aus, kopf = [], None
    land_block, block_spalte = "", None
    for row in ws.iter_rows(values_only=True):
        vals = ["" if c is None else str(c).strip() for c in row]
        breite = max(list(SPALTEN.values()) + [block_spalte or 0]) + 1
        if len(vals) < breite:
            vals += [""] * (breite - len(vals))
        lei = vals[lei_spalte]
        if not LEI_RE.match(lei):
            # Eine Zwischenüberschrift — aber nur auf einem Blatt, das das Land
            # nicht als Spalte führt. Sonst überschriebe eine zufällige
            # Textzelle das ordentlich gelesene Land.
            if "land" not in SPALTEN:
                for i, v in enumerate(vals):
                    if v in laender:
                        land_block, block_spalte = v, i
                        break
            continue
        # Die laufende Nummer steht unmittelbar links vom LEI — und nur dort,
        # wo das Blatt sie führt.
        nummer = vals[lei_spalte - 1] if lei_spalte > 0 else ""
        nummer = nummer if nummer.isdigit() else ""
        # Ohne Namensspalte steht der Name in derselben Spalte wie die
        # Länderüberschrift.
        if "name" in SPALTEN:
            name = vals[SPALTEN["name"]]
        elif block_spalte is not None and len(vals) > block_spalte:
            name = vals[block_spalte]
        else:
            name = ""
        eintrag = {"lei": lei,
                   "name": name,
                   "typ": vals[SPALTEN["typ"]] if "typ" in SPALTEN else "",
                   "land": vals[SPALTEN["land"]] if "land" in SPALTEN
                           else land_block,
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


# Rechtsformen, die keinen Namen unterscheiden. Ohne sie zu entfernen trennt
# „Piraeus Bank S.A." von „Piraeus Financial Holdings" nichts als Wortsalat.
RECHTSFORMEN = {
    "ag", "sa", "s.a.", "nv", "n.v.", "bv", "b.v.", "plc", "spa", "s.p.a.",
    "eg", "e.g.", "egen", "e.gen.", "gen", "sarl", "s.a.r.l.", "srl", "as",
    "a.s.", "ab", "oyj", "oy", "se", "kgaa", "gmbh", "aktiengesellschaft",
    "aktiebolag", "group", "groupe", "holding", "holdings", "bank", "banca",
    "banco", "banque", "bankas", "banka", "the", "of", "and", "financial",
    "co", "company", "international",
}


def namensworte(name):
    """Die bedeutungstragenden Wörter eines Namens.

    Alles unter drei Zeichen fliegt raus. Der Grund ist konkret: die Trennung
    an Satzzeichen zerlegt `S.A.` in „s" und „a" und `N.V.` in „n" und „v" —
    und dann teilen `Piraeus Bank S.A.` und `Alpha Bank S.A.` zwei Wörter und
    gelten als dasselbe Haus. Eine Rechtsform in der Sperrliste hilft nichts,
    wenn sie als Einzelbuchstaben ankommt.
    """
    return {w for w in re.split(r"[^0-9A-Za-zÄÖÜäöüßÀ-ÿ]+", (name or "").lower())
            if len(w) >= 3 and w not in RECHTSFORMEN}


def namensnah(a, b):
    """Zwei Namen, die dasselbe Haus meinen könnten.

    Gefordert sind ZWEI gemeinsame Wörter, nicht eins. Ein Wort genügt nur,
    wenn einer der Namen nach Abzug der Rechtsformen bloss aus einem besteht —
    `Piraeus Bank S.A.` gegen `Piraeus Financial Holdings` ist dann ein Treffer.

    Der Fall, der die Regel erzwungen hat: `Nederlandse Waterschapsbank N.V.`
    traf über das erste Wort auf `Nederlandse Financierings-Maatschappij` —
    zwei völlig verschiedene Banken, verbunden nur durch das Wort
    „niederländisch". Ein Nationaladjektiv unterscheidet nichts, und ein
    falscher Treffer wäre hier besonders teuer: er erklärte eine echte Lücke weg.
    """
    wa, wb = namensworte(a), namensworte(b)
    if not wa or not wb:
        return False
    return len(wa & wb) >= min(2, len(wa), len(wb))


def namensverdacht(zeilen, meta):
    """Wo der LEI-Abgleich eine Lücke meldet, aber ein gleichnamiges Haus
    im Bestand steht, wird der Verdacht ausgewiesen statt der Lücke.

    Der Fall, der das erzwungen hat: Die EZB führt die griechische Gruppe unter
    `Piraeus Bank S.A.`, offen legt sie aber als `Piraeus Financial Holdings` —
    eine andere LEI. Rein über die LEI gerechnet fehlt Griechenlands
    viertgrösste Bank vollständig, und das wäre eine Unterstellung statt eines
    Befunds.

    Gefordert wird das LAND und die Namensnähe nach `namensnah`. Das Land allein
    wäre wertlos, die Namensnähe allein träfe alle zwölf Volksbanken quer durch
    Europa.
    """
    je_land = collections.defaultdict(list)
    for m in meta.values():
        je_land[m.get("country", "")].append(m)
    for z in zeilen:
        if z["einordnung"] != "nicht_abgedeckt":
            continue
        # Auch über den Gruppenkopf: bei den österreichischen Volksbanken ist
        # nicht die Einheit selbst namensgleich, sondern ihr Kopf.
        for name in (z["name"], z["gruppenkopf_name"]):
            treffer = [m for m in je_land.get(z["land"], [])
                       if namensnah(name, m.get("name", ""))]
            if treffer:
                treffer.sort(key=lambda m: m["lei"])
                z["einordnung"] = "namensgleicher_melder"
                z["namenstreffer"] = f"{treffer[0]['lei']} {treffer[0]['name']}"
                break
    return zeilen


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
    # Die Ländernamen kommen aus dem SI-Blatt und dienen dem LSI-Blatt als
    # Schlüssel für seine Zwischenüberschriften.
    laender = laendernamen(wb["SIs"])
    zeilen = (lies_blatt(wb["SIs"], "SI", laender)
              + lies_blatt(wb["LSIs"], "LSI", laender))

    # Dieselbe Einheit kann in beiden Blättern stehen; SI gewinnt.
    gesehen = {}
    for z in zeilen:
        if z["lei"] not in gesehen or z["signifikanz"] == "SI":
            gesehen[z["lei"]] = z
    zeilen = list(gesehen.values())

    with META.open(encoding="utf-8") as fh:
        meta = {r["lei"]: r for r in csv.DictReader(fh)}
    einordnen(zeilen, bestand_index(meta))
    namensverdacht(zeilen, meta)

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
    verdacht = [z for z in zeilen if z["signifikanz"] == "SI"
                and z["einordnung"] == "namensgleicher_melder"]
    if verdacht:
        aus.append(f"Namensgleicher Melder unter anderer LEI: {len(verdacht)} "
                   f"— nachweislich meldend, aber nicht über die LEI der "
                   f"EZB-Liste zuzuordnen:")
        for z in sorted(verdacht, key=lambda z: (z["land"], z["name"]))[:4]:
            aus.append(f"    {z['land']:12s} {z['name'][:34]:36s} → "
                       f"{z['namenstreffer'][:44]}")
        if len(verdacht) > 4:
            aus.append(f"    … und {len(verdacht) - 4} weitere")

    offen = [z for z in zeilen
             if z["signifikanz"] == "SI" and z["einordnung"] == "nicht_abgedeckt"]
    # Die Zahl, um die es #42 geht. Sie steht bewusst NACH den Verdachtsfällen:
    # wer nur über die LEI rechnet, liest hier 12 statt 1 und hält elf meldende
    # Häuser für Lücken.
    aus.append(f"► Signifikant und ohne jede Spur — weder selbst, noch über die "
               f"Gruppe, noch namensgleich: {len(offen)}")
    for z in sorted(offen, key=lambda z: (z["land"], z["name"])):
        aus.append(f"    {z['land']:12s} {z['name'][:44]}")
    aus.append("  Auch das ist kein Vorwurf: Art. 433a lässt für nicht "
               "börsennotierte Institute jährliche statt quartalsweiser "
               "Offenlegung zu, und eine Offenlegung ausserhalb des Hubs ist "
               "damit nicht ausgeschlossen.")
    # #42 verlangt die Abdeckung JE LAND ausdrücklich — und verbietet ebenso
    # ausdrücklich, daraus eine EU-weite Vollständigkeit zu machen. Beides
    # steht deshalb hier nebeneinander.
    # Getrennt nach SI und LSI, und das ist keine Formalie: die LSI-Quote ist
    # niedrig, WEIL sie niedrig sein soll. Nach CRR Art. 433a–c legen kleine,
    # nicht börsennotierte Institute seltener und weniger offen; Deutschlands
    # 1.109 LSIs sind überwiegend Sparkassen und Genossenschaftsbanken. Eine
    # gemeinsame Quote läse sich als Abdeckungslücke und wäre eine
    # Unterstellung — die aussagekräftige Zahl ist die der SIs.
    aus.append("Abdeckung je Land (Anteil, der selbst oder über die Gruppe "
               "offenlegt) — SI und LSI getrennt:")
    je_land = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for z in zeilen:
        t = je_land[z["land"] or "?"][z["signifikanz"]]
        t[0] += 1
        t[1] += z["einordnung"] in ("meldet_selbst", "ueber_gruppe",
                                    "gruppe_meldet_teilweise")
    reihen = sorted(je_land.items(),
                    key=lambda kv: (-kv[1]["SI"][0], kv[0]))[:8]
    aus.append(f"    {'Land':14s} {'SI':>14s}   {'LSI':>14s}")
    for land, teil in reihen:
        def q(sig):
            n, ab = teil[sig]
            return f"{ab:4d}/{n:<4d} {100*ab/n:4.0f} %" if n else "        —   "
        aus.append(f"    {land:14s} {q('SI')}   {q('LSI')}")
    aus.append("  Die LSI-Quote ist niedrig, weil sie es sein soll: CRR "
               "Art. 433a–c verlangt von kleinen, nicht börsennotierten "
               "Instituten weniger. Sie ist kein Abdeckungsmangel.")
    aus.append("  ⚠ Der SSM-Bereich umfasst den Euroraum. Unser Bestand reicht "
               "darüber hinaus; für Länder ausserhalb gibt es hier keine "
               "Grundgesamtheit und damit KEINE Abdeckungsaussage.")

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
