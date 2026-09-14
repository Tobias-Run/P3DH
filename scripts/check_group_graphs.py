"""Zwei Konzerngraphen gegeneinander: GLEIF gegen EZB-Hierarchie (#32, #42).

Ausgabe: processed/group_graph_check.csv

## Warum es die Prüfung gibt

Im Repo liegen **zwei** Konzerngraphen, die nie gegeneinander geprüft wurden:

    processed/lei_relations.csv   GLEIF Level-2 (#32) — 189 oberste Mütter
    processed/coverage_gap.csv    EZB-Hierarchie (#42) — 797 Gruppenköpfe

`build_eba_reconciliation.py` schliesst über den ersten 90 Institutszeilen aus,
damit ein Länderaggregat Mutter und Tochter nicht doppelt zählt. Wäre der Graph
falsch, wären es die Aggregate auch — und niemand hätte es gemerkt. Das ist
dieselbe Konstruktion wie #37: eine Behauptung gegen eine unabhängige Quelle
halten, statt sie gegen sich selbst zu prüfen.

## Das Ergebnis: sie widersprechen sich NICHT

97 Institute haben in beiden Quellen einen Kopf.

    67   identisch
    30   ssm_schnitt
     0   konflikt

Und die 30 sind kein Fehler, sondern die **Perimetergrenze**: in allen 30 Fällen
liegt der GLEIF-Kopf ausserhalb der EZB-Liste, weil der Konzern über den SSM
hinausreicht. Bei 27 davon ist der EZB-Kopf das Institut selbst — es IST die
Spitze seiner beaufsichtigten Gruppe.

    BofA Securities Europe SA     EZB: sie selbst    GLEIF: Bank of America (US)
    HSBC Continental Europe       EZB: sie selbst    GLEIF: HSBC Holdings (UK)
    AB SEB bankas (LT)            EZB: sie selbst    GLEIF: SEB AB (SE, ausser SSM)

Die übrigen drei sind derselbe Schnitt eine Ebene tiefer: HSBC Bank Malta hat
als EZB-Kopf HSBC Continental Europe und als GLEIF-Kopf HSBC Holdings.

Die Gegenprobe stützt das: bei allen 67 Übereinstimmungen liegt der Kopf **in**
der EZB-Liste.

## Was daraus folgt

**Keiner der beiden Graphen ersetzt den anderen.** Sie beantworten verschiedene
Fragen, und welche man braucht, hängt vom Zweck ab:

    Aggregate ohne Doppelzählung   -> EZB-Kopf (die beaufsichtigte Gruppe)
    Wem gehört dieses Institut     -> GLEIF (der Konzern)

Für die Länderaggregate in #37 ist der EZB-Kopf der richtige: eine US-Mutter
meldet nicht nach CRR Teil 8 und kann in einem EU-Aggregat nicht doppelt zählen.

## Die Kategorie, auf die es ankommt, ist leer — und das muss laut gesagt werden

`konflikt` heisst: der GLEIF-Kopf steht in der EZB-Liste, ist dort aber ein
ANDERER als der EZB-Kopf. Das wäre ein echter Widerspruch, und es gibt ihn
derzeit nicht.

Eine Prüfung, deren interessante Kategorie leer ist, sieht aus wie eine Prüfung,
die nichts tut. Der Unterschied ist die Gegenprobe: 97 Vergleichspaare, davon 30
mit abweichendem Kopf — der Vergleich greift also, er findet nur keinen
Widerspruch. Ohne diese Zahl wäre „0 Konflikte" bedeutungslos.

Aufruf: python3 scripts/check_group_graphs.py
"""

from pathlib import Path
import collections
import csv
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

GLEIF = ROOT / "processed" / "lei_relations.csv"
EZB = ROOT / "processed" / "coverage_gap.csv"
OUT = ROOT / "processed" / "group_graph_check.csv"

FELDER = ["lei", "name", "land", "ezb_kopf_lei", "ezb_kopf_name",
          "gleif_kopf_lei", "gleif_kopf_name", "ezb_kopf_ist_selbst",
          "gleif_kopf_in_ezb_liste", "urteil"]


def urteil_von(lei, ezb_kopf, gleif_kopf, gleif_kopf_bekannt):
    """Wie verhalten sich die beiden Köpfe zueinander?

    `identisch`     beide nennen denselben.
    `ssm_schnitt`   sie weichen ab, UND der GLEIF-Kopf ist der EZB gar nicht
                    bekannt — der Konzern reicht über den SSM hinaus. Das ist
                    kein Widerspruch, sondern zwei Fragen mit zwei Antworten.
    `konflikt`      sie weichen ab, und der GLEIF-Kopf IST in der EZB-Liste.
                    Dann behaupten zwei Quellen über dieselbe beaufsichtigte
                    Landschaft Verschiedenes, und eine davon irrt.

    Die Reihenfolge ist wichtig: wer `ssm_schnitt` nicht prüft, meldet 30
    Konflikte, wo keine sind — und wer nur auf Gleichheit prüft, hält 69 %
    Übereinstimmung für 31 % Fehler.
    """
    if not ezb_kopf or not gleif_kopf:
        return ""
    if ezb_kopf == gleif_kopf:
        return "identisch"
    return "konflikt" if gleif_kopf_bekannt else "ssm_schnitt"


def lade():
    """(GLEIF-Köpfe, EZB-Köpfe, Namen) — je {lei: ...}."""
    gleif, ezb, namen, land = {}, {}, {}, {}
    with GLEIF.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("ultimate_parent_lei"):
                gleif[r["lei"]] = r["ultimate_parent_lei"]
    with EZB.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r.get("lei"):
                continue
            namen[r["lei"]] = r.get("name", "")
            land[r["lei"]] = r.get("land", "")
            if r.get("gruppenkopf_lei"):
                ezb[r["lei"]] = r["gruppenkopf_lei"]
    return gleif, ezb, namen, land


def build():
    gleif, ezb, namen, land = lade()
    bekannt = set(namen)                 # alle LEIs, die die EZB überhaupt führt

    zeilen = []
    for lei in sorted(set(gleif) & set(ezb)):
        g, e = gleif[lei], ezb[lei]
        zeilen.append({
            "lei": lei, "name": namen.get(lei, ""), "land": land.get(lei, ""),
            "ezb_kopf_lei": e, "ezb_kopf_name": namen.get(e, ""),
            "gleif_kopf_lei": g, "gleif_kopf_name": namen.get(g, ""),
            "ezb_kopf_ist_selbst": "ja" if e == lei else "nein",
            "gleif_kopf_in_ezb_liste": "ja" if g in bekannt else "nein",
            "urteil": urteil_von(lei, e, g, g in bekannt),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    print(f"✓ {OUT}  ({len(zeilen)} Vergleichspaare)")
    for s in bericht(zeilen, gleif, ezb):
        print("  " + s)
    return zeilen


def bericht(zeilen, gleif, ezb):
    u = collections.Counter(z["urteil"] for z in zeilen)
    aus = [f"GLEIF kennt {len(gleif)} oberste Mütter · EZB {len(ezb)} Gruppenköpfe "
           f"· gemeinsam {len(zeilen)}",
           "Urteil: " + "  ".join(f"{k}={v}" for k, v in sorted(u.items()))]

    schnitt = [z for z in zeilen if z["urteil"] == "ssm_schnitt"]
    if schnitt:
        selbst = sum(1 for z in schnitt if z["ezb_kopf_ist_selbst"] == "ja")
        aus.append(f"Von den {len(schnitt)} Abweichungen ist der EZB-Kopf bei "
                   f"{selbst} das Institut selbst — es ist die Spitze seiner "
                   f"beaufsichtigten Gruppe, der Konzern reicht darüber hinaus.")
        aus.append("Beispiele:")
        for z in schnitt[:5]:
            aus.append(f"  {z['name'][:30]:32s} EZB: "
                       f"{(z['ezb_kopf_name'] or 'sie selbst')[:26]:28s} "
                       f"GLEIF: ausserhalb der EZB-Liste")

    ident = [z for z in zeilen if z["urteil"] == "identisch"]
    if ident:
        drin = sum(1 for z in ident if z["gleif_kopf_in_ezb_liste"] == "ja")
        aus.append(f"Gegenprobe: bei {drin} der {len(ident)} Übereinstimmungen "
                   f"liegt der Kopf in der EZB-Liste.")

    aus.append("")
    if u["konflikt"]:
        aus.append(f"⚠ {u['konflikt']} ECHTE Widersprüche — beide Quellen führen den "
                   f"Kopf, nennen aber verschiedene:")
        for z in zeilen:
            if z["urteil"] == "konflikt":
                aus.append(f"  {z['name'][:28]:30s} EZB {z['ezb_kopf_name'][:24]:26s} "
                           f"GLEIF {z['gleif_kopf_name'][:24]}")
    else:
        aus.append(f"✓ Kein Widerspruch. Der Vergleich GREIFT — {len(zeilen)} Paare, "
                   f"davon {len(schnitt)} mit abweichendem Kopf —, er findet nur "
                   f"keinen Konflikt.")
    return aus


if __name__ == "__main__":
    build()
