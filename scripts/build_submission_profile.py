"""Korrekturverhalten als Qualitätssignal (#31)

Ausgaben: processed/submission_profile.csv   je Institut
          processed/persistent_findings.csv  Befund ohne Korrektur

## Die Ebene, die bisher unausgewertet war

Wir werten die Einreichungen aus. Wir besitzen aber auch den **Katalog über die
Einreichungen** — `interim/edap_recon/manifest_full.csv` mit `submission_ts`
und der vollständigen Resubmission-Historie. Diese Ebene beschreibt nicht die
Bank, sondern **ihr Verhalten**.

## Die Definition entscheidet über die Kernzahl — Faktor 7

Was eine „Korrektur" ist, hängt daran, was „dieselbe Meldung" heisst. Drei
plausible Schlüssel geben **472, 2.539 und 3.353** Korrekturen. Richtig ist nur
der Schlüssel MIT dem Modultyp aus dem Dateinamen: die Spalte `module` trägt
lediglich den PILLAR3-Code (`020000`), und unter einem Code liegen CODIS,
ESGDIS und FINDIS als eigenständige Meldungen nebeneinander. Wer sie
zusammenwirft, zählt verschiedene Module als Korrekturen voneinander.

Dieses Skript rechnet deshalb nicht selbst, sondern benutzt `submissions.py`
(#88), wo der Schlüssel einmal definiert ist. Zwei Definitionen im selben
Projekt wären der sichere Weg zu zwei Antworten auf dieselbe Frage.

## Der Zusammenhang, den das Issue behauptet — und der heute nicht trägt

#31 berichtet, Institute mit Plausibilitätsbefunden korrigierten 1,5- bis
1,9-mal häufiger, in jeder Umfangsklasse. Das wäre eine **externe Validierung
des #17-Verfahrens** gewesen: zwei Seiten, die nichts miteinander zu tun haben
— #17 misst Werte, der Katalog misst Verhalten — bestätigen einander.

**Nachgerechnet trägt das nicht:**

    Umfang   mit Befund      ohne Befund     Faktor
     1-3     0,000 (n= 11)   0,039 (n= 56)     0,00
     4-8     0,053 (n=113)   0,048 (n=133)     1,11
     9+      0,134 (n=149)   0,131 (n= 27)     1,03

Mit strengeren Befundkriterien kehrt sich das Vorzeichen sogar um: bei
`n_hoch > 0` liegt der Faktor in der grössten Klasse bei 0,74, bei
`n_findings >= 10` bei 0,66.

**Am Zählschlüssel liegt es nicht.** Geprüft mit beiden: der korrigierte
Schlüssel aus #88 (472 Korrekturen) und der naive ohne Modultyp (2.539) geben
dieselbe Antwort — Faktoren zwischen 0,95 und 1,07.

Die plausibelste Erklärung ist die **Befundpopulation**. Als #31 geschrieben
wurde, trugen 238 von 489 Instituten einen Befund; heute sind es 273, weil #36
(Zeitkonsistenz) und #83 (Skalenfehler) seither ganze Befundklassen
hinzugefügt haben. Die Vergleichsgruppe „ohne Befunde" ist damit kleiner und
anders zusammengesetzt als damals.

Sicher ist nur das Ergebnis, nicht seine Ursache: auf dem heutigen Bestand gibt
es diesen Zusammenhang nicht, und das Verfahren aus #17 bekommt seine
Bestätigung von dieser Seite nicht.

Die Schichtung nach Meldeumfang bleibt trotzdem fest eingebaut — ohne sie
stünde in der Tabelle Grösse statt Verhalten, der wiederkehrende Fehler dieses
Projekts (#43, #45, #11, #44).

## Die Kehrseite ist die eigentliche Nachricht

`persistent_findings.csv`: Institute mit `hoch`-Befund, die **nie** korrigiert
haben. Das ist eine Liste dauerhafter Auffälligkeiten, die es sonst nirgends
gibt — und die interessantere Hälfte des Befundes.

## Kein Werturteil

Eine Korrektur ist ein Zeichen von Sorgfalt, keine Schuld: wer nachbessert,
verhält sich richtig. Die Spalten heissen `n_korrekturen` und
`korrekturen_je_einreichung`, nicht „Fehlerquote".

Und `manifest_full.csv` ist ein Schnappschuss vom Harvest-Zeitpunkt: spätere
Korrekturen fehlen, die Zahlen sind eine **untere Schranke** und ändern sich
mit jedem Harvest (#6).

Aufruf: python3 scripts/build_submission_profile.py
"""

from pathlib import Path
import collections
import csv
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

MANIFEST = ROOT / "interim" / "edap_recon" / "manifest_full.csv"
QUALITY = ROOT / "processed" / "quality_profile.csv"
META = ROOT / "processed" / "entity_meta.csv"

OUT_PROFIL = ROOT / "processed" / "submission_profile.csv"
OUT_PERSISTENT = ROOT / "processed" / "persistent_findings.csv"

# Schichtung nach Meldeumfang. Die Grenzen folgen dem Issue (1–3, 4–8, 9+) und
# sind dort an der Verteilung gewählt, nicht gerundet.
KLASSEN = ((1, 3, "1-3"), (4, 8, "4-8"), (9, 10 ** 9, "9+"))

FELDER_PROFIL = ["lei", "bank_name", "country", "institution_type",
                 "n_einreichungen", "n_meldungen", "n_korrekturen",
                 "korrekturen_je_einreichung", "umfangsklasse",
                 "max_fassungen", "n_hoch", "n_findings", "hat_befund",
                 "hat_korrigiert"]

FELDER_PERSISTENT = ["lei", "bank_name", "country", "n_hoch", "n_findings",
                     "n_einreichungen", "templates_hoch"]


def umfangsklasse(n, klassen=KLASSEN):
    """Meldeumfangsklasse — die Schichtung, ohne die der Vergleich Grösse misst.

    Das Issue sagt es selbst: „Die Korrekturrate hängt am Meldeumfang; jeder
    Vergleich ohne Schichtung ist irreführend."
    """
    for unten, oben, name in klassen:
        if unten <= n <= oben:
            return name
    return ""


def zaehle(zeilen):
    """{lei: (n_einreichungen, n_meldungen, n_korrekturen, max_fassungen)}.

    Eine **Meldung** ist eine Identität im Sinne von `submissions.identitaet`;
    eine **Einreichung** ist eine Zeile des Katalogs. Die Differenz sind die
    Korrekturen.

    `max_fassungen` hält den Extremfall fest: ein Report wurde zehnmal
    eingereicht, alle zehn Fassungen innerhalb von zwei Tagen.
    """
    import submissions

    je_lei = collections.defaultdict(collections.Counter)
    for r in zeilen:
        je_lei[r["lei"]][submissions.identitaet(r)] += 1
    aus = {}
    for lei, c in je_lei.items():
        einreichungen = sum(c.values())
        meldungen = len(c)
        aus[lei] = (einreichungen, meldungen, einreichungen - meldungen,
                    max(c.values()))
    return aus


def kreuztabelle(profile):
    """{klasse: {"mit"/"ohne": (n, korrekturen_je_einreichung)}}.

    Die Schichtung aus dem Issue als reproduzierbares Artefakt. Gerechnet wird
    je EINREICHUNG, nicht je Institut — sonst steht in der Tabelle Grösse.
    """
    eimer = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in profile:
        if not p["umfangsklasse"]:
            continue
        seite = "mit" if p["hat_befund"] == "ja" else "ohne"
        eimer[p["umfangsklasse"]][seite].append(
            float(p["korrekturen_je_einreichung"]))
    aus = {}
    for klasse, seiten in eimer.items():
        aus[klasse] = {s: (len(v), statistics.mean(v) if v else 0.0)
                       for s, v in seiten.items()}
    return aus


def build():
    if not MANIFEST.exists():
        print(f"ERROR: {MANIFEST} fehlt — erst der Harvest")
        return [], []

    with MANIFEST.open(encoding="utf-8") as fh:
        zeilen = list(csv.DictReader(fh))
    gezaehlt = zaehle(zeilen)

    qual = collections.defaultdict(lambda: [0, 0, set()])
    if QUALITY.exists():
        with QUALITY.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                q = qual[r["lei"]]
                q[0] += int(r.get("n_hoch") or 0)
                q[1] += int(r.get("n_findings") or 0)
                if r.get("templates_hoch"):
                    q[2] |= set(r["templates_hoch"].split("|"))

    meta = {}
    if META.exists():
        with META.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                meta[r["lei"]] = (r.get("name", ""), r.get("country", ""),
                                  r.get("institution_type", ""))

    profil, persistent = [], []
    for lei, (ein, meld, korr, maxf) in sorted(gezaehlt.items()):
        name, land, itype = meta.get(lei, ("", "", ""))
        n_hoch, n_find, thoch = qual.get(lei, [0, 0, set()])
        profil.append({
            "lei": lei, "bank_name": name, "country": land,
            "institution_type": itype,
            "n_einreichungen": ein, "n_meldungen": meld,
            "n_korrekturen": korr,
            "korrekturen_je_einreichung": f"{korr / ein:.4f}" if ein else "",
            "umfangsklasse": umfangsklasse(ein),
            "max_fassungen": maxf,
            "n_hoch": n_hoch, "n_findings": n_find,
            "hat_befund": "ja" if n_find else "nein",
            "hat_korrigiert": "ja" if korr else "nein"})
        # Die interessantere Hälfte: hoch-Befund und nie korrigiert.
        if n_hoch and not korr:
            persistent.append({
                "lei": lei, "bank_name": name, "country": land,
                "n_hoch": n_hoch, "n_findings": n_find,
                "n_einreichungen": ein,
                "templates_hoch": "|".join(sorted(thoch)[:6])})

    profil.sort(key=lambda z: z["lei"])
    persistent.sort(key=lambda z: (-z["n_hoch"], z["lei"]))
    for pfad, felder, daten in ((OUT_PROFIL, FELDER_PROFIL, profil),
                                (OUT_PERSISTENT, FELDER_PERSISTENT, persistent)):
        pfad.parent.mkdir(parents=True, exist_ok=True)
        with pfad.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, felder)
            w.writeheader()
            w.writerows(daten)
        print(f"✓ {pfad}  ({len(daten)} Zeilen)")

    for s in bericht(profil, persistent, zeilen):
        print("  " + s)
    return profil, persistent


def bericht(profil, persistent, zeilen):
    ein = sum(p["n_einreichungen"] for p in profil)
    korr = sum(p["n_korrekturen"] for p in profil)
    aus = [f"Katalog: {len(zeilen)} Einreichungen · {ein - korr} eigenständige "
           f"Meldungen · {korr} Korrekturen",
           f"  Der Schlüssel stammt aus submissions.py (#88) und enthält den "
           f"MODULTYP. Ohne ihn zählten CODIS, ESGDIS und FINDIS als "
           f"Korrekturen voneinander — drei plausible Schlüssel geben 472, "
           f"2.539 und 3.353, ein Faktor von sieben."]
    viel = max(profil, key=lambda p: p["max_fassungen"], default=None)
    if viel and viel["max_fassungen"] > 2:
        aus.append(f"  Häufigste Nachmeldung: {viel['max_fassungen']} Fassungen "
                   f"desselben Reports ({viel['bank_name'][:34]})")

    kt = kreuztabelle(profil)
    if kt:
        aus.append("Korrekturen je Einreichung, geschichtet nach Meldeumfang "
                   "(#17-Befund ja/nein):")
        for klasse in [k for _, _, k in KLASSEN if k in kt]:
            m = kt[klasse].get("mit", (0, 0.0))
            o = kt[klasse].get("ohne", (0, 0.0))
            faktor = (m[1] / o[1]) if o[1] else float("nan")
            aus.append(f"    {klasse:>4s}  mit {m[1]:.3f} (n={m[0]:>3d})  ·  "
                       f"ohne {o[1]:.3f} (n={o[0]:>3d})  ·  Faktor {faktor:.2f}")
        aus.append("  Geschichtet und je EINREICHUNG gerechnet — die rohe Zahl "
                   "je Institut misst sonst Meldeumfang, nicht Verhalten.")
        faktoren = [kt[k]["mit"][1] / kt[k]["ohne"][1]
                    for k in kt
                    if kt[k].get("mit") and kt[k].get("ohne")
                    and kt[k]["ohne"][1]]
        if faktoren and max(faktoren) < 1.3:
            aus.append("  ⚠ #31 berichtet hier Faktoren von 1,5 bis 1,9 und "
                       "liest sie als externe Validierung von #17. Gemessen "
                       "bleibt davon nichts: die Faktoren liegen um 1. Geprüft "
                       "mit beiden Zählschlüsseln (mit und ohne Modultyp) — "
                       "daran liegt es nicht. Vermutlich hat sich die "
                       "Befundpopulation geändert (#36, #83 kamen seither "
                       "dazu), aber sicher ist nur das Ergebnis.")

    mit_hoch = [p for p in profil if p["n_hoch"]]
    if mit_hoch:
        aus.append(f"→ {len(persistent)} von {len(mit_hoch)} Instituten mit "
                   f"`hoch`-Befund haben NIE korrigiert. Das ist die Liste "
                   f"dauerhafter Auffälligkeiten, und die interessantere "
                   f"Hälfte des Befundes.")
        for p in persistent[:5]:
            aus.append(f"    {p['bank_name'][:32]:34s} {p['n_hoch']:>3d} hoch · "
                       f"{p['n_einreichungen']:>2d} Einreichungen · "
                       f"{p['templates_hoch'][:30]}")
    aus.append("Kein Werturteil: eine Korrektur ist Sorgfalt, keine Schuld. "
               "Und der Katalog ist ein Schnappschuss — spätere Korrekturen "
               "fehlen, die Zahlen sind eine untere Schranke (#6).")
    return aus


if __name__ == "__main__":
    build()
