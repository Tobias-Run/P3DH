"""Issue #17: Plausibilitäts-Profil je Institut — Werte gegen die Population.

Ergänzt den Gap-Scan aus #9, der einen strukturellen blinden Fleck hat: er sucht
eine SCHARFE bimodale Lücke (>=3 Größenordnungen, >=3 Institute je Seite). Wo die
Werte über viele Größenordnungen VERSCHMIERT streuen, findet er nichts. Der
schlimmste Fall im Bestand fällt genau dadurch: REM1 `30.01` r0020/c0020 streut
über 14 Größenordnungen (Rabobank meldet 11,7 Bio. EUR fixe Vergütung für 9
Vorstandsmitglieder) und steht NICHT in `interim/unit_consistency_report.csv`.

Drei Verfahren, bewusst unterschiedlich verwundbar:

1. **cell_outlier** — robuster Ausreißer gegen die eigene Zellpopulation:
   Median und MAD auf log10(|Wert|), geflaggt ab z > OUTLIER_Z. Der Maßstab
   ist die Zelle selbst, nicht eine globale Konstante. Eine globale Schranke
   ("Prozente <= 1") wäre falsch: Zellen unterscheiden sich legitim in ihrer
   Konvention, und echte Bankgrößen-Unterschiede erklären im Median 3,76
   Größenordnungen Streuung.

   Zwei Eigenschaften dieses Tests sind hart erarbeitet und dürfen nicht
   stillschweigend zurückgedreht werden:

   a) **Nur die OBERE Flanke.** Die untere Flanke einer Exposure-Verteilung
      ist natürlich: sehr viele Institute haben nahe null Exposure zu einer
      gegebenen Kategorie, und ein Betrag von 100 EUR in einer Zelle mit
      Median 10^8 ist eine kleine Position, kein Meldefehler. Symmetrisch
      geprüft lagen 9.750 von 12.744 Befunden UNTER dem Median, davon 2.645
      bei |Wert| < 1 Währungseinheit (Deutsche Bank meldet 1,7·10^-11 EUR —
      der Gleitkomma-Rest einer effektiven Null). Das ist Rauschen, kein
      Produkt. Die untere Flanke gehört zu den Ratio-Regeln (3), die dort
      mit fachlichem Wissen statt Statistik urteilen.

   b) **Monetäre Zellen werden in EUR verglichen** (`fact_value_eur`), nicht
      in Meldewährung. Sonst schlägt der Test auf die Währung an statt auf
      den Wert: HUF/EUR ~400 und NOK/EUR ~11,7 verschieben log10 um bis zu
      2,6 Größenordnungen, was bei einem typischen MAD von 0,4 bereits über
      der Schwelle liegt. Vorher stammten 43 % der Befunde von Nicht-EUR-
      Meldern, allein 858 von zwei norwegischen Instituten.

2. **cell_incoherent** — die Zelle SELBST ist unbrauchbar. Streut schon der
   Rumpf (p10..p90) über >= INCOHERENT_SPREAD Größenordnungen, ist keine
   Instituts-Zuschreibung mehr zu verantworten: dann ist unklar, welche Lesart
   die richtige ist, nicht welches Institut falsch liegt. Solche Zellen werden
   ausdrücklich OHNE Schuldzuweisung ausgewiesen und aus (1) ausgenommen.
   Belegbeispiel: `09.05` c0020 ("Of which exposures in default", als
   `percentage` typisiert) streut über 6,47 Größenordnungen bis 28,5 Mrd —
   303 Werte <= 1 gegen 316 > 1, also eine echte 50:50-Spaltung der Lesart.

3. **ratio** — fachlich begründete Korridore auf abgeleiteten Verhältnissen
   INNERHALB eines Reports (RATIO_RULES). Diese sind gegen genau die Fehler
   immun, die (1) und (2) plagen: meldet ein Institut durchgängig in Millionen,
   kürzt sich der Faktor im Quotienten heraus. Sie bringen dafür fachliches
   Wissen ein, das die Statistik nicht hat.

4. **time_jump / time_break** — dieselbe Zelle desselben Instituts an zwei
   aufeinanderfolgenden Stichtagen (#36). Die Verfahren (1) bis (3) messen
   einen Wert an ANDEREN: an der Population derselben Zelle oder an einem
   fachlichen Korridor. Beides erzwingt Annahmen — vergleichbare Grösse,
   vergleichbare Währung, vergleichbare Peers —, und für jede davon steht oben
   ein Fehler, den ich beim Bau machen musste. Der Zeitvergleich braucht keine
   davon: **das Institut ist sein eigener Massstab.**

   Er ist deshalb auch der einzige der vier, der einen Skalenfehler von unten
   sehen kann. `robust_z` sieht per Konstruktion nur nach oben (1a), und ein zu
   klein gemeldeter Wert liegt unten — das ist der blinde Fleck, für den es
   scripts/build_report_scale.py gibt. Der Zeitvergleich misst den BETRAG der
   Änderung und ist damit richtungsblind.

   Was dabei herauskommt, ist die stärkste Gegenprobe, die #83 bisher hatte:
   8 der 21 Report-Paare mit Strukturbruch enthalten einen Report, den #83
   unabhängig als `skaliert` führt — darunter fünf der sechs am höchsten
   konzentrierten (Deutsche Pfandbriefbank 79,9 % und 72,9 %, First Investment
   Bank 57,7 % und 44,2 %, Banco Santander Totta 35,1 %). Zwei Verfahren ohne
   gemeinsame Evidenz — #83 urteilt aus TREA-Grössen und `decimals`, #36 aus
   der Zeitreihe — zeigen auf dieselben Reports, und in der richtigen
   Richtung: bei der Pfandbriefbank ist der FRÜHERE Report der skalierte, der
   spätere sauber.

   Die übrigen 13 sind der Ertrag: dort findet der Zeitvergleich etwas, das
   #83 nicht sieht (Sparebanken Norge 25,3 %, Groupe BPCE 18,2 %, DNB Bank
   14,4 %) — bei BPCE springen 855 von 4.693 Zellen, mit Median 6,01
   Grössenordnungen: die Signatur eines Faktorwechsels, nicht einer Fusion.

   Der Befund aus #36, den der Querschnitt nie zeigen würde: die Deutsche Bank
   meldet in 63.02.A r0270 („8. Others") 12,1 Mrd EUR, dann 2,7 Mrd, dann
   −9,5·10^-8 und schliesslich 0. Der vorletzte Wert ist eine effektive Null
   zwischen normalen Werten — im Querschnitt unauffällig, weil er unter dem
   Zellmedian liegt, wo (1) bewusst nicht hinsieht.

Schwellen sind an der beobachteten Verteilung geeicht, nicht geraten — siehe
die Konstanten unten.

**Kein Werturteil über Institute.** Das Ergebnis ist ein reproduzierbarer
Konsistenz-Check, der sagt "dieser Wert passt nicht zur Population", nicht
"dieses Institut meldet falsch". Ein Ausreißer kann eine korrekte Besonderheit
sein; die Entscheidung bleibt beim Leser.

Lauf:  python3 scripts/check_plausibility.py
Out:   interim/plausibility_cells.csv      (Zellstatistik, inkl. unbrauchbarer Zellen)
       interim/plausibility_findings.csv   (Einzelbefunde je Fakt)
       processed/quality_profile.csv       (Profil je Institut/Report)
"""

from pathlib import Path
import csv
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metrics  # noqa: E402
from determinism import ordered_query  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
CELLS_OUT = ROOT / "interim" / "plausibility_cells.csv"
FINDINGS_OUT = ROOT / "interim" / "plausibility_findings.csv"
PROFILE_OUT = ROOT / "processed" / "quality_profile.csv"

# Mindestbesetzung einer Zelle, damit Median/MAD tragen. Unter ~20 Instituten
# verschiebt ein einzelner Ausreißer den Median selbst zu stark.
MIN_INSTITUTES = 20

# Ausreißer ab |robustem z| > 6. Konservativ: bei normalverteilten log-Werten
# entspräche das ~1 Fehlalarm auf 10^9. Wir wollen wenige, harte Befunde.
OUTLIER_Z = 6.0

# --- Schweregrad (#53) ------------------------------------------------------
# Erkannt wird über den robusten z-Wert, eingestuft wurde bis 2026-09 allein
# über den Abstand vom Zellmedian in Größenordnungen. Diese Skala ist auf
# Einheiten-Verwechslungen geeicht und dort richtig — für eine ENGE Zelle ist
# sie es nicht: zwei Größenordnungen sind in einer Quotenzelle gewaltig und in
# einer Betragszelle mit 3,8 Größenordnungen Rumpfstreuung gewöhnlich.
#
# Der Beleg, an dem die neue Skala geeicht ist, steht in KM1 r0050 c0010
# (CET1-Quote). Dort liegen 20 Befunde, und sie zerfallen in zwei Gruppen, die
# sich unabhängig von jeder Statistik nachprüfen lassen — am Kapital und am
# Gesamtrisikobetrag DERSELBEN Meldung:
#
#   16 beweisbare Meldeartefakte. Die Quote ist in Prozent statt als Bruch
#      gemeldet (Faktor exakt 100: Société générale, Belfius, Česká spořitelna,
#      RCI Banque, NEST Bank, Bank Frick, Caisse régionale, Erwerbsgesellschaft
#      der S-Finanzgruppe), einmal Faktor 1000 (Aresbank) und einmal völlig
#      entgleist (Citfin, 1,7·10^8).
#    4 korrekte Werte. Kommuninvest meldet 355 % CET1 — und 12,026 Mrd SEK
#      Kapital gegen 3,385 Mrd SEK TREA ergeben genau das. Ein Kommunal-
#      finanzierer hat praktisch nur nullgewichtete Aktiva.
#
# Auf der alten Skala stehen 14 der 16 Artefakte auf `niedrig`, gemeinsam mit
# Kommuninvest: eine Verwechslung des Faktors 100 sind nur 2 Größenordnungen.
# Gemessen in RUMPFBREITEN der eigenen Zelle trennen sich beide Gruppen sauber:
# die Artefakte liegen bei 5,19 bis 25,4, Kommuninvest bei 3,63 bis 3,75.
# SEVERITY_REL_HIGH = 5,0 liegt in dieser Lücke.
#
# Was `hoch` damit heißt: der Wert liegt mehr als fünfmal so weit über dem
# Median, wie der Rumpf der Zelle überhaupt breit ist. Es heißt NICHT "dieses
# Institut meldet falsch" — Kommuninvest zeigt, dass ein weit außen liegender
# Wert korrekt sein kann, und diese Entscheidung bleibt beim Leser.
SEVERITY_HIGH = 6.0          # absolut: volle Einheiten-Verwechslung (10^6)
SEVERITY_MID = 3.0           # absolut: Faktor 1000
SEVERITY_REL_HIGH = 5.0      # relativ: Rumpfbreiten (p10..p90) über dem Median
SEVERITY_REL_MID = 2.5

# Zelle gilt als unbrauchbar, wenn schon ihr Rumpf (p10..p90) >= 6 Größen-
# ordnungen streut. Geeicht an der beobachteten Verteilung über 4.569 Zellen
# mit >= 20 Instituten: Median 3,76 · p75 4,45 · p90 5,12 · p95 5,85 · p99 7,05.
# 6,0 liegt oberhalb von p95 und entspricht exakt dem Faktor einer Einheiten-
# Verwechslung (10^6 = Millionen statt Währungseinheiten) — ist der Rumpf so
# breit wie eine volle Einheiten-Verwechslung, ist keine Zuschreibung sicher.
INCOHERENT_SPREAD = 6.0

# --- Zeitvergleich (#36) ----------------------------------------------------
# Ab wann ein Sprung ein Befund ist. Gleiche Skala wie SEVERITY_* — der Sprung
# IST ein Abstand in Grössenordnungen, nur gemessen gegen den eigenen Vorwert
# statt gegen den Zellmedian. 3 = Faktor 1.000, 6 = volle Einheiten-
# Verwechslung. Unterhalb von 3 ist ein halbes Jahr echter Geschäftstätigkeit
# eine völlig ausreichende Erklärung.
TIME_JUMP_MIN = SEVERITY_MID
# Ein Sprung ist NICHT per se ein Fehler — eine Bank kann ein Portfolio
# verkauft, eine Tochter entkonsolidiert oder fusioniert haben. Springen aber
# viele Zellen EINES Reports gleichzeitig, ist ein Strukturbruch (oder ein
# Einheitenwechsel) wahrscheinlicher als ein Tippfehler, und dann ist die
# Aussage über den Report zu treffen und nicht über 1.152 einzelne Zellen.
#
# Geeicht an der beobachteten Verteilung über 490 Report-Paare mit >= 50
# vergleichbaren Zellen: Median 0,0 % · p75 0,40 % · p90 1,23 % · p95 4,11 %
# · p99 36,1 % · max 79,9 %. 5 % liegt knapp über p95 und fasst 21 Report-Paare,
# die zusammen 77 % ALLER Zellsprünge tragen. Das Band 1–5 % ist stetig besetzt,
# es gibt dort keine natürliche Lücke; die Schwelle ist eine Setzung, und der
# Bericht führt `sprung_median` mit, damit der Leser sie nachrechnen kann.
TIME_BREAK_SHARE = 0.05
# Unter 50 vergleichbaren Zellen trägt ein Anteil nicht: bei 12 Zellen sind
# zwei Sprünge schon 17 %, ohne dass das etwas über den Report aussagt.
TIME_BREAK_MIN_CELLS = 50
# Wesentlichkeitsschwelle je Datentyp. Liegen BEIDE Werte eines Zeitpaars
# darunter, ist der Sprung Rauschen zwischen zwei effektiven Nullen. Immer
# beide — liegt eine Seite darüber, ist der Sprung echt, und das ist der Fall,
# auf den es ankommt: ein Skalenfehler macht einen GROSSEN Wert klein.
#
#   monetary    eine Währungseinheit. Dieselbe Grenze, an der im Querschnitt
#               2.645 Befunde als Gleitkomma-Rest erkannt wurden (Docstring
#               1a). Sie entfernt 20 Zeitbefunde, darunter den schwersten
#               überhaupt: AIB Group meldet in 67.01.A 0,0008 EUR gegen
#               5·10^-23 EUR — 19,2 Grössenordnungen zwischen zwei Nichtsen.
#
#   percentage  ein Millionstel, also 0,0001 %. Eine Quote braucht eine EIGENE
#               Grenze: dort ist ein Wert unter 1 der Normalfall, und eine
#               gemeinsame Schwelle hätte 74 echte Befunde mitverworfen —
#               BPER Banca fällt in 41.00 von 0,24 auf 3·10^-6, und das ist
#               ein Befund, weil eine Seite ein Viertel ist.
#               Die Grenze ist eine Setzung, keine Messung: die beobachtete
#               Verteilung läuft glatt aus (1.769 Quoten bei 10^-6, 625 bei
#               10^-7, 317 bei 10^-8), es gibt dort keine Kante. Sie entfernt
#               heute zwei Zellpaare, und beide sind „of which environmentally
#               sustainable"-Anteile in der Grössenordnung 10^-10.
#
#   integer     keine. Eine Kopfzahl unter 1 gibt es nicht (gemessen: null
#               Fälle im Bestand), eine Schwelle wäre folgenlose Dekoration.
MATERIALITAET = {"monetary": 1.0, "percentage": 1e-6, "decimal": 1e-6}


# --- Fachliche Ratio-Regeln ------------------------------------------------
# Deklarativ, damit neue Regeln ohne Codeänderung dazukommen. Jede Regel bildet
# innerhalb EINES Reports (lei, scope, refPeriod) und einer Spalte den Quotienten
# zweier Zeilen und prüft ihn gegen einen Korridor.
#
# Zeile 0010 ist die Kopfzahl der "identified staff" (typisiert integer), Zeile
# 0020 der zugehörige Gesamtbetrag — der Quotient ist eine Vergütung pro Kopf.
# In REM1 (30.01) ist das die FIXE Vergütung, in REM2 (30.02) die GARANTIERTE
# VARIABLE; verschiedene Konzepte, aber dieselbe Größenordnungsfrage, und der
# Korridor prüft nichts anderes.
#
# Die Grenzen stehen in scripts/metrics.py und werden von dort geholt: der
# Viewer filtert mit denselben Zahlen die Vergütungs-Rangliste (#18). Zwei
# Zahlenpaare an zwei Orten wären hier gefährlich — eine Rangliste, die nach
# einem anderen Korridor filtert als der, gegen den geprüft wurde.
RATIO_RULES = [
    {
        "id": "rem_per_head",
        "templates": ("30.01", "30.02"),
        "numerator_row": "0020",     # Gesamtbetrag (monetary, in EUR gerechnet)
        "denominator_row": "0010",   # Number of identified staff (integer)
        "lo": metrics.REM_PER_HEAD[0],
        "hi": metrics.REM_PER_HEAD[1],
        "label": "Vergütung pro identifiziertem Mitarbeiter "
                 "(REM1: fix · REM2: garantiert variabel)",
        "unit": "EUR",
    },
]


def cell_stats(values):
    """Robuste Kennzahlen einer Zellpopulation auf log10(|Wert|).

    values: Iterable numerischer Werte (Nullen und None werden ignoriert —
    log10(0) ist undefiniert, und eine gemeldete Null ist kein Größenindiz).

    Liefert None, wenn zu wenige verwertbare Werte übrig bleiben, sonst ein
    Dict mit n, median, mad, spread (p90-p10) und incoherent.
    """
    logs = sorted(math.log10(abs(v)) for v in values if v)
    n = len(logs)
    if n < MIN_INSTITUTES:
        return None
    mid = n // 2
    median = logs[mid] if n % 2 else (logs[mid - 1] + logs[mid]) / 2
    devs = sorted(abs(x - median) for x in logs)
    m = len(devs) // 2
    mad = devs[m] if len(devs) % 2 else (devs[m - 1] + devs[m]) / 2
    spread = logs[int(0.9 * (n - 1))] - logs[int(0.1 * (n - 1))]
    return {"n": n, "median": median, "mad": mad, "spread": spread,
            "incoherent": spread >= INCOHERENT_SPREAD}


def robust_z(value, stats):
    """Abstand ÜBER dem Zellmedian in robusten Standardabweichungen (MAD).

    Einseitig: Werte unterhalb des Medians liefern 0. Begründung im Modul-
    Docstring (1a) — die untere Flanke ist bei Exposure-Daten natürlich, ihre
    Prüfung gehört zu den fachlichen Ratio-Regeln.

    Bei mad == 0 (mehr als die Hälfte der Zelle trägt exakt denselben Betrag)
    ist der Quotient nicht definiert; wir weichen auf den reinen Abstand in
    Größenordnungen aus, damit eine solche Zelle nicht ALLE abweichenden Werte
    als unendlich auffällig meldet.
    """
    if not value:
        return 0.0
    d = math.log10(abs(value)) - stats["median"]
    if d <= 0:
        return 0.0
    scale = 1.4826 * stats["mad"]
    return d / scale if scale > 1e-9 else d


def severity(deviation_orders, relative=None):
    """Schweregrad aus BEIDEN Maßen — dem absoluten Abstand in Größenordnungen
    und, wo eine Zelle eine messbare Rumpfbreite hat, dem Abstand in
    Rumpfbreiten. Es gilt der jeweils höhere; Begründung und Eichung stehen bei
    den Konstanten.

    `relative` ist None, wo es keine Rumpfbreite gibt: bei den fachlichen
    Korridoren (dort ersetzt der Korridor selbst die Population) und bei Zellen
    mit Rumpfbreite ~0. Dann entscheidet der absolute Abstand allein.
    """
    if deviation_orders >= SEVERITY_HIGH or (relative is not None
                                             and relative >= SEVERITY_REL_HIGH):
        return "hoch"
    if deviation_orders >= SEVERITY_MID or (relative is not None
                                            and relative >= SEVERITY_REL_MID):
        return "mittel"
    return "niedrig"


def ratio_violations(rule, pairs):
    """Reine Funktion: prüft einen Korridor gegen Zähler/Nenner-Paare.

    pairs: Iterable von (key, numerator, denominator). key ist beliebig
    (typisch: (lei, scope, refPeriod, template_id, cell_col)).

    Liefert Befunde für Paare ausserhalb [lo, hi]. Nenner <= 0 wird
    übersprungen — eine Kopfzahl von 0 ist keine Plausibilitätsaussage über
    die Vergütung, sondern eine eigene (hier nicht behandelte) Frage.
    """
    # Gemessen wird ab der MITTE des Korridors, nicht ab dem verletzten Rand
    # (#53). Der Rand ist der falsche Nullpunkt: bei den Zell-Ausreißern ist
    # der Bezug der Median, also die Mitte der Population. Der Korridor hier
    # ist bewusst weit — 1.000 bis 20.000.000 EUR sind 4,3 Größenordnungen —,
    # und ab seinem Rand gemessen erschien der schlimmste Fall im ganzen
    # Bestand als "mittel": Rabobank meldet 1,3 Bio. EUR fixe Vergütung pro
    # Vorstandsmitglied, das sind 4,81 Größenordnungen über der Obergrenze,
    # aber 6,97 über der Mitte. Erst der zweite Wert ist mit dem Abstandsmaß
    # der Zell-Ausreißer vergleichbar — und erst er ergibt "hoch".
    center = math.sqrt(rule["lo"] * rule["hi"])
    out = []
    for key, num, den in pairs:
        if den is None or num is None or den <= 0:
            continue
        ratio = num / den
        if rule["lo"] <= ratio <= rule["hi"]:
            continue
        if ratio <= 0:
            # Eine gemeldete Null bei positiver Kopfzahl — KEIN Befund.
            #
            # Zuerst stand hier `SEVERITY_HIGH` als Platzhalter für den
            # undefinierten log10(0), der anschließend als gemessener Abstand
            # eingestuft wurde; eine Null bekam damit "hoch", während Rabobanks
            # 1,3 Bio. pro Kopf "mittel" bekam. Der Platzhalter fiel mit #53 —
            # aber "hoch" blieb, jetzt fachlich begründet. Auch das war zu viel,
            # und die Fälle zeigen es: 8 der 10 Nullen stehen in REM2, also bei
            # der GARANTIERTEN VARIABLEN Vergütung, wo null der Normalfall ist
            # (BBVA, Agence France Locale, Raiffeisen-Landesbank Tirol). Die
            # übrigen zwei sind unentgeltlich arbeitende Aufsichtsräte in REM1.
            #
            # Dieser Korridor ist eine EINHEITENPRÜFUNG. Keine Zehnerpotenz
            # bildet einen echten Betrag auf null ab; eine Null kann also gar
            # kein Einheitenfehler sein. Sie ist eine Angabe — und die als
            # Fehler zu führen, wäre dieselbe Verwechslung wie "Fehlt = Null",
            # nur andersherum.
            continue
        bound = rule["lo"] if ratio < rule["lo"] else rule["hi"]
        dev = abs(math.log10(ratio / center))
        out.append({"key": key, "rule": rule["id"], "ratio": ratio,
                    "bound": bound, "center": center, "deviation_orders": dev,
                    "severity": severity(dev)})
    return out


# --- Zeitvergleich: reine Funktionen (#36) ---------------------------------

def jump_orders(v1, v2, floor=0.0):
    """Betrag der Änderung in Grössenordnungen, oder None.

    None heisst „nicht messbar", nicht „kein Sprung". Eine gemeldete Null hat
    keine Grössenordnung (log10(0) ist undefiniert), und sie ist auch keine:
    eine Null ist eine ANGABE — „diese Position gibt es nicht" —, während der
    Sprung eine Aussage über ein Verhältnis ist. Keine Zehnerpotenz bildet
    einen Betrag auf null ab, ein Einheitenfehler kann also gar nicht so
    aussehen; dieselbe Begründung steht bei `ratio_violations`.

    196.302 der 658.149 Zeitpaare haben auf einer Seite eine Null. Sie fallen
    heraus, und das muss sichtbar bleiben — der Bericht zählt sie.

    Richtungsblind mit Absicht: gemessen wird der Betrag. Ein Wert, der um
    10^6 FÄLLT, ist derselbe Befund wie einer, der um 10^6 steigt, und genau
    darin unterscheidet sich dieses Verfahren von `robust_z` (Docstring 1a).

    `floor` ist die Wesentlichkeitsschwelle: liegen BEIDE Werte darunter, ist
    der Quotient kein Befund, sondern Rauschen zwischen zwei effektiven Nullen.
    Die AIB Group meldet in 67.01.A 0,0008 EUR und ein halbes Jahr später
    5·10^-23 EUR — 19,2 Grössenordnungen, und beide Seiten sind nichts. Das ist
    exakt dieselbe Falle, die im Modul-Docstring unter (1a) steht.

    Die Schwelle hängt vom Datentyp ab und kommt deshalb vom Aufrufer, nicht
    von hier: für Beträge ist eine Währungseinheit die natürliche Untergrenze,
    für Quoten wäre sie verheerend, weil dort ein Wert unter 1 der Normalfall
    ist. Die Zahlen stehen bei MATERIALITAET.
    """
    if not v1 or not v2:
        return None
    if floor and abs(v1) < floor and abs(v2) < floor:
        return None
    return abs(math.log10(abs(v2)) - math.log10(abs(v1)))


def median(werte):
    """Median einer nichtleeren Folge, ohne numpy und ohne quantile_cont."""
    s = sorted(werte)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2


def time_findings(pairs, min_jump=TIME_JUMP_MIN, break_share=TIME_BREAK_SHARE,
                  break_min_cells=TIME_BREAK_MIN_CELLS):
    """Zeitpaare -> (Einzelsprünge, Strukturbrüche).

    pairs: Iterable von Dicts mit mindestens
        report (irgendein Schlüssel für das Report-PAAR — typisch
                (lei, scope, d1, d2)), zelle (beliebig), v1, v2.

    Liefert zwei Listen. Ein Report-Paar landet in GENAU EINER davon:

      * Springt ein kleiner Teil seiner Zellen, sind das Einzelbefunde —
        dort ist die Zelle auffällig, nicht der Report.
      * Springt ein grosser Teil, ist der REPORT auffällig, und dann wäre es
        irreführend, 1.152 Zellen einzeln zu melden. Die Deutsche
        Pfandbriefbank stellt zwischen dem 30.06. und dem 31.12. 79,9 % ihrer
        vergleichbaren Zellen um; 1.038 der 1.178 Sprünge liegen bei exakt
        sechs Grössenordnungen. Das ist ein Einheitenwechsel, eine einzige
        Tatsache — und sie gehört einmal gemeldet.

    Deshalb führt der Strukturbruch `sprung_median` mit: liegt er bei ~3 oder
    ~6, war es ein Faktorwechsel; streut er, ist es eher ein echter Bruch
    (Verkauf, Entkonsolidierung, Fusion). Die Prüfung entscheidet das nicht,
    sie legt die Zahl daneben.

    Zellen ohne messbaren Sprung (Null auf einer Seite) zählen weder im Zähler
    noch im Nenner des Anteils — sonst verwässerte eine nullreiche Vorlage den
    Anteil beliebig.
    """
    je_report = {}
    for p in pairs:
        s = jump_orders(p["v1"], p["v2"], p.get("floor", 0.0))
        if s is None:
            continue
        je_report.setdefault(p["report"], []).append((s, p))

    sprünge, brüche = [], []
    for rep in sorted(je_report, key=lambda r: tuple(map(str, r))):
        messbar = je_report[rep]
        über = [(s, p) for s, p in messbar if s >= min_jump]
        anteil = len(über) / len(messbar)
        if (len(messbar) >= break_min_cells and anteil >= break_share and über):
            brüche.append({
                "report": rep, "n_vergleichbar": len(messbar),
                "n_sprung": len(über), "anteil": anteil,
                "sprung_median": median([s for s, _ in über]),
                "sprung_max": max(s for s, _ in über),
            })
            continue
        for s, p in über:
            sprünge.append({**p, "sprung": s,
                            "richtung": "auf" if abs(p["v2"]) > abs(p["v1"]) else "ab",
                            "vorzeichenwechsel": p["v1"] * p["v2"] < 0})
    return sprünge, brüche


BRIDGE = ROOT / "codebook" / "framework_bridge.csv"


def lade_framework_bruecke(pfad=None):
    """Framework-Brücke 4.1 -> 4.2 (#26) -> (umbindung, unsicher).

    `umbindung`  {dp_42: dp_41} für Zellen, die beim Wechsel auf einen NEUEN
                 datapoint-Code umgebunden wurden (`rebound`). Ohne diese
                 Übersetzung reissen genau diese Zeitreihen am 31.03.2026 ab —
                 still, denn eine fehlende Zeitreihe sieht aus wie ein Institut
                 ohne Historie. Gemessen entstehen **1.055 Zeitpaare erst
                 durch die Übersetzung**; das ist die Gegenprobe dafür, dass
                 die Brücke hier etwas tut.

    `unsicher`   {(template, row, col)} für Zellen, bei denen die Brücke KEINE
                 eindeutige Übersetzung hergibt. Paare über den Bruch werden
                 dort nicht geprüft, sondern gezählt und im Bericht genannt.

    ## Warum `ambiguous` in der Brücke hier nichts sperrt

    Die Brücke ist auf (template, row, col) gebaut, und `ambiguous` heisst
    dort „mehrere dp-Codes je Version beobachtet". Nachgemessen gilt aber für
    **alle 123** solchen Zellen dp_41 == dp_42: es sind Koordinaten, auf denen
    mehrere Datenpunkte liegen (74.00.A r0010 c0010 trägt vier), und nicht
    Zellen, deren Bedeutung sich geändert hätte. Auf dem dp-Code — dem
    Schlüssel, den diese Prüfung benutzt — sind sie eindeutig.

    Das darf nicht zur Annahme werden. Die Brücke wächst mit jeder 4.2-Welle,
    und eine `ambiguous`-Zeile, deren dp-Mengen sich UNTERSCHEIDEN, wäre eine
    echte Mehrdeutigkeit. Genau die landet in `unsicher`. Die Menge ist heute
    leer, und ein Test hält fest, dass sie sich füllt, sobald es so weit ist —
    eine Prüfung, die auf Abwesenheit „bestanden" meldet, wäre hier besonders
    verführerisch.
    """
    pfad = Path(pfad or BRIDGE)
    if not pfad.exists():
        return {}, set()
    # Ein dp_42 steht mehrfach in der Brücke, wenn mehrere Koordinaten
    # denselben Datenpunkt tragen (63.01.B/C/D r0070 teilen sich einen). Das
    # ist keine Mehrdeutigkeit, solange alle auf DASSELBE dp_41 zeigen — und
    # genau das ist heute bei allen drei Mehrfachnennungen der Fall. Eine
    # Zuordnung per Überschreiben würde den Unterschied nicht merken, deshalb
    # wird er hier ausdrücklich gesucht.
    kandidaten, unsicher = {}, set()
    with pfad.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            koord = (r["template_id"], r["cell_row"], r["cell_col"])
            dp41, dp42 = r.get("dp_41", ""), r.get("dp_42", "")
            if r.get("status") == "rebound" and "|" not in dp41 and "|" not in dp42:
                kandidaten.setdefault(dp42, {})[dp41] = koord
            elif dp41 != dp42:
                unsicher.add(koord)          # mehrdeutig oder unerwartete Form
    umbindung = {}
    for dp42, ziele in kandidaten.items():
        if len(ziele) == 1:
            umbindung[dp42] = next(iter(ziele))
        else:
            unsicher.update(ziele.values())  # ein Code, zwei Vorgänger: nicht raten
    return umbindung, unsicher


FREQUENZ = ROOT / "processed" / "disclosure_frequency.csv"


def lade_frequenzmodell(pfad=None):
    """{(institution_type, template_id): Frequenz} aus #34.

    Trägt einen VORBEHALT an den Befund, keinen Filter. Der Gedanke aus #36
    war, Stichtage verschiedener Frequenz gar nicht erst zu vergleichen — ein
    Jahreswert gegen einen Quartalswert mischt zwei Offenlegungen. Nachgerechnet
    trägt das aber nicht: der grösste Effekt, den eine Frequenzverwechslung
    erzeugen kann, ist das Verhältnis Jahr zu Quartal, also Faktor 4 oder 0,6
    Grössenordnungen — weit unter TIME_JUMP_MIN. Eine Frequenz kann einen
    Dreier-Sprung nicht erklären.

    Ausserdem wäre der Filter teuer und blind: das Modell deckt nur 184 von
    ~900 (Institutstyp, Template)-Kombinationen ab (es verlangt >= 5
    Institute), und ein Filter auf Abwesenheit würde den grössten Teil der
    Prüfung stillschweigend abschalten — genau die Bauart, die in diesem Repo
    schon mehrfach ein Ausfall war, der sich als Erfolg meldete.

    Also: die bekannte Frequenz steht als `hinweis` am Befund, damit der Leser
    sie einbeziehen kann, und die Prüfung läuft über alle Paare.
    """
    pfad = Path(pfad or FREQUENZ)
    if not pfad.exists():
        return {}
    with pfad.open(encoding="utf-8") as fh:
        return {(r["institution_type"], r["template_id"]): r["frequenz"]
                for r in csv.DictReader(fh) if r.get("frequenz")}


def _rel(path):
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


SCALE_FLAGS = ROOT / "processed" / "scale_flags.csv"


def lade_skalenmarken(pfad=None):
    """{(lei, scope, refPeriod)} der Reports mit belegtem Skalenfehler (#83).

    Nur die REPORT-Ebene und nur das Urteil `skaliert`. Ein Verdacht reicht
    nicht, um jemanden aus der Grundgesamtheit zu nehmen, und die
    Templateebene betrifft ohnehin nur einzelne Zellen.

    Fehlt die Datei, wird nichts ausgeschlossen — dann verhält sich die
    Prüfung wie vorher, statt stillschweigend die halbe Population zu
    verlieren.
    """
    pfad = pfad or SCALE_FLAGS
    if not Path(pfad).exists():
        return set()
    with Path(pfad).open(encoding="utf-8") as fh:
        return {(r["lei"], r["scope"], r["refPeriod"]) for r in csv.DictReader(fh)
                if r.get("ebene") == "report" and r.get("urteil") == "skaliert"
                and r.get("lei")}


def main():
    import duckdb

    if not PARQUET.exists():
        print(f"ERROR: {PARQUET} fehlt — erst scripts/build_zweig_b.py")
        return 2

    con = duckdb.connect()
    CELLS_OUT.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_OUT.parent.mkdir(parents=True, exist_ok=True)

    # --- 1/2: Zellpopulationen. Nur geschlossene Achsen: bei offenen Achsen
    # ist (template,row,col) keine Zelle, sondern ein ganzes Gitter je
    # Dimensionswert (67.01.A hätte sonst 57.502 "Werte einer Zelle").
    # `comparable`: monetäre Werte in EUR (sonst misst der Test die Meldewährung,
    # siehe Docstring 1b), alle anderen Typen sind einheitenfrei und gehen roh ein.
    # Monetäre Fakten ohne FX-Kurs fallen damit heraus — richtig so, sie sind
    # institutsübergreifend schlicht nicht vergleichbar.
    COMPARABLE = ("CASE WHEN data_type='monetary' THEN fact_value_eur "
                  "ELSE fact_value END")
    # Skalierte Reports (#83) aus der STATISTIK nehmen, nicht aus der Prüfung.
    #
    # Wichtig ist, wem das nützt — nämlich NICHT den ausgeschlossenen Reports.
    # Ein Skalenfehler macht Werte immer zu klein und landet damit unter dem
    # Zellmedian, wo `robust_z` bewusst nicht hinsieht (Docstring 1a). Diese
    # Prüfung kann ihn also gar nicht finden, und das ist Absicht; dafür gibt es
    # scripts/build_report_scale.py und processed/scale_flags.csv.
    #
    # Der Schaden trifft die ANDEREN Institute derselben Zellen: ein Report, der
    # um 10^6 danebenliegt, weitet die Population genau der Zellen, in denen er
    # steht, über INCOHERENT_SPREAD. Die Zelle gilt dann als unbrauchbar, und
    # die Ausreisser aller übrigen Melder darin werden mitgedeckelt.
    # Gemessen sinken die unbrauchbaren Zellen dadurch von 592 auf 246.
    #
    # Ausgeschlossen wird nur aus dem Nenner. Die Reports werden weiterhin
    # geprüft — sonst verschwänden ihre übrigen Befunde mit dem Skalenurteil.
    ausschluss = lade_skalenmarken()
    if ausschluss:
        print(f"Aus der Zellstatistik ausgeschlossen (#83): {len(ausschluss)} Reports")
    ausschluss_sql = "TRUE"
    if ausschluss:
        paare = ",".join(
            "('%s','%s','%s')" % (l.replace("'", ""), sc.replace("'", ""), rp)
            for l, sc, rp in sorted(ausschluss))
        ausschluss_sql = f"(lei, scope, refPeriod) NOT IN ({paare})"
    cells = {}
    # any_value() -> max(): any_value() greift sich ein beliebiges Element und
    # ist damit zwischen Läufen instabil, sobald eine Zelle mehrere Labels
    # trägt. LIST() ist hier unschädlich, weil cell_stats() intern sortiert —
    # aber der Guard verlangt eine Sortierung, die das sichtbar macht.
    rows = ordered_query(con, f"""
        SELECT template_id, cell_row, cell_col,
               max(row_label), max(col_label), max(data_type),
               LIST({COMPARABLE} ORDER BY {COMPARABLE})
        FROM '{PARQUET}'
        WHERE {COMPARABLE} IS NOT NULL AND {COMPARABLE} <> 0
          AND cell_row IS NOT NULL AND cell_row <> ''
          AND data_type IN ('monetary', 'percentage', 'decimal', 'integer')
          AND {ausschluss_sql}
        GROUP BY 1, 2, 3
        HAVING count(DISTINCT lei) >= {MIN_INSTITUTES}
        ORDER BY 1, 2, 3
    """, "Zellstatistik")
    labels = {}
    for t, r, c, rl, cl, dt, vals in rows:
        st = cell_stats(vals)
        if st:
            cells[(t, r, c)] = st
            labels[(t, r, c)] = (rl or "", cl or "", dt or "")

    coherent = {k: v for k, v in cells.items() if not v["incoherent"]}
    print(f"Zellen mit >= {MIN_INSTITUTES} Instituten: {len(cells):,}")
    print(f"  davon auswertbar (Rumpfstreuung < {INCOHERENT_SPREAD:.0f} Größenordnungen): {len(coherent):,}")
    print(f"  unbrauchbar — keine Zuschreibung: {len(cells)-len(coherent):,}")

    # --- Einzelbefunde: Ausreißer in auswertbaren Zellen
    findings = []
    for lei, scope, rp, bank, t, r, c, val in ordered_query(con, f"""
        SELECT lei, scope, refPeriod, bank_name, template_id, cell_row, cell_col,
               {COMPARABLE}
        FROM '{PARQUET}'
        WHERE {COMPARABLE} IS NOT NULL AND {COMPARABLE} <> 0
          AND cell_row IS NOT NULL AND cell_row <> ''
        ORDER BY lei, scope, refPeriod, template_id, cell_row, cell_col,
                 {COMPARABLE}, bank_name
    """, "Einzelbefunde"):
        st = coherent.get((t, r, c))
        if st is None:
            continue
        z = robust_z(val, st)
        if z <= OUTLIER_Z:
            continue
        dev = math.log10(abs(val)) - st["median"]
        # Abstand in Rumpfbreiten der eigenen Zelle (#53). Bei spread ~ 0 ist
        # der Quotient nicht definiert — dann entscheidet der absolute Abstand
        # allein, wie schon bei mad == 0 in robust_z().
        rel = dev / st["spread"] if st["spread"] > 1e-9 else None
        findings.append({
            "lei": lei, "scope": scope, "refPeriod": rp, "bank_name": bank or "",
            "template_id": t, "cell_row": r, "cell_col": c,
            "rule": "cell_outlier", "value": val,
            "reference": 10 ** st["median"], "n_population": st["n"],
            "deviation_orders": dev, "spread_widths": rel, "robust_z": z,
            "severity": severity(dev, rel),
        })

    # --- 3: fachliche Ratio-Regeln
    for rule in RATIO_RULES:
        tpls = ",".join(f"'{t}'" for t in rule["templates"])
        pairs, meta = [], {}
        for lei, scope, rp, bank, t, col, num, den in ordered_query(con, f"""
            WITH num AS (
              SELECT DISTINCT lei, scope, refPeriod, template_id, cell_col,
                     max(bank_name) OVER (PARTITION BY lei) AS bank_name,
                     fact_value_eur AS v
              FROM '{PARQUET}'
              WHERE template_id IN ({tpls}) AND cell_row = '{rule["numerator_row"]}'
                AND fact_value_eur IS NOT NULL),
                 den AS (
              SELECT DISTINCT lei, scope, refPeriod, template_id, cell_col,
                     fact_value AS v
              FROM '{PARQUET}'
              WHERE template_id IN ({tpls}) AND cell_row = '{rule["denominator_row"]}'
                AND fact_value IS NOT NULL)
            SELECT num.lei, num.scope, num.refPeriod, num.bank_name,
                   num.template_id, num.cell_col, num.v, den.v
            FROM num JOIN den USING (lei, scope, refPeriod, template_id, cell_col)
            ORDER BY num.lei, num.scope, num.refPeriod, num.template_id,
                     num.cell_col, num.v, den.v, num.bank_name
        """, f"Ratio-Regel {rule['id']}"):
            key = (lei, scope, rp, t, col)
            pairs.append((key, num, den))
            meta[key] = bank or ""
        viol = ratio_violations(rule, pairs)
        print(f"\nRegel {rule['id']}: {len(pairs):,} Paare geprüft, {len(viol)} ausserhalb "
              f"[{rule['lo']:,.0f} .. {rule['hi']:,.0f}] {rule['unit']}")
        for v in viol:
            lei, scope, rp, t, col = v["key"]
            findings.append({
                "lei": lei, "scope": scope, "refPeriod": rp, "bank_name": meta[v["key"]],
                "template_id": t, "cell_row": rule["numerator_row"], "cell_col": col,
                "rule": rule["id"], "value": v["ratio"], "reference": v["center"],
                "n_population": len(pairs),
                "deviation_orders": v["deviation_orders"],
                # Der Korridor ersetzt hier die Population: eine Rumpfbreite
                # gibt es nicht, und der z-Wert auch nicht.
                "spread_widths": None, "robust_z": None,
                "severity": v["severity"],
            })

    # --- 4: Zeitvergleich (#36) --------------------------------------------
    # Der Zellschlüssel ist NICHT (template, row, col), obwohl #36 das so
    # vorschlägt. Nachgemessen ist diese Koordinate keine Zelle: auf 268 von
    # ihnen liegen mehrere Datenpunkte (74.00.B r0110 c0010 trägt vier). Über
    # (template, row, col) gepaart entstünden daraus 16.048 „Sprünge" zwischen
    # dem 30.06. und sich selbst — ein Vergleich über null Tage, der wie ein
    # Befund aussieht. Der Schlüssel ist deshalb der datapoint-Code, ergänzt um
    # die offene Achse, und über den Framework-Bruch durch die Brücke geführt.
    umbindung, unsichere_koord = lade_framework_bruecke()
    reb_sql = "datapoint_code"
    if umbindung:
        faelle = " ".join(f"WHEN '{a}' THEN '{b}'" for a, b in sorted(umbindung.items()))
        reb_sql = f"CASE datapoint_code {faelle} ELSE datapoint_code END"
    unsicher_sql = "TRUE"
    if unsichere_koord:
        paare = ",".join("('%s','%s','%s')" % k for k in sorted(unsichere_koord))
        unsicher_sql = f"(template_id, cell_row, cell_col) NOT IN ({paare})"

    # Dubletten: 4.079 Schlüssel stehen im selben Report doppelt (dieselbe
    # Meldezeile mehrfach im Paket). Sie tragen ausnahmslos denselben Wert —
    # `min()` ist deshalb keine Auswahl, sondern eine Identität, und ein Test
    # hält fest, dass das so bleibt. Ein leises `any_value()` wäre hier genau
    # die Sorte Griff, die der Determinismus-Guard verbietet.
    zeitzeilen = ordered_query(con, f"""
        WITH v AS (
          SELECT lei, scope, refPeriod, template_id, cell_row, cell_col,
                 coalesce(open_axis_dims, '') AS oad, {reb_sql} AS dpk,
                 max(bank_name) AS bank_name, max(institution_type) AS institution_type,
                 max(data_type) AS data_type, min({COMPARABLE}) AS val
          FROM '{PARQUET}'
          WHERE {COMPARABLE} IS NOT NULL
            AND cell_row IS NOT NULL AND cell_row <> ''
            AND data_type IN ('monetary', 'percentage', 'decimal', 'integer')
            AND {unsicher_sql}
          GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
        ), paar AS (
          SELECT lei, scope, bank_name, institution_type, template_id,
                 cell_row, cell_col, oad, data_type,
                 lag(refPeriod) OVER w AS d1, refPeriod AS d2,
                 lag(val) OVER w AS v1, val AS v2
          FROM v
          WINDOW w AS (PARTITION BY lei, scope, template_id, cell_row, cell_col,
                                    oad, dpk ORDER BY refPeriod)
        )
        SELECT lei, scope, bank_name, institution_type, template_id,
               cell_row, cell_col, oad, data_type, d1, d2, v1, v2
        FROM paar
        WHERE d1 IS NOT NULL
        ORDER BY lei, scope, template_id, cell_row, cell_col, oad, d1, d2,
                 v1, v2, data_type, bank_name, institution_type
    """, "Zeitpaare")

    frequenz = lade_frequenzmodell()
    zeitpaare, namen, ohne_mass, unwesentlich = [], {}, 0, 0
    for lei, sc, bank, it, t, r, c, oad, dtyp, d1, d2, v1, v2 in zeitzeilen:
        floor = MATERIALITAET.get(dtyp, 0.0)
        if jump_orders(v1, v2, floor) is None:
            if v1 and v2:
                unwesentlich += 1
            else:
                ohne_mass += 1
            continue
        rep = (lei, sc, d1, d2)
        namen[rep] = bank or ""
        zeitpaare.append({"report": rep, "lei": lei, "scope": sc,
                          "bank_name": bank or "", "template_id": t,
                          "cell_row": r, "cell_col": c, "oad": oad,
                          "d1": d1, "d2": d2, "v1": v1, "v2": v2, "floor": floor,
                          "frequenz": frequenz.get((it or "", t), "")})
    # Zwei Zählungen mit verschiedenem Zweck: `je_paar` ist die Population
    # EINES Report-Paars (steht als n_population am Befund), `zeitpaare_je_report`
    # zählt, wie oft ein einzelner Report überhaupt verglichen wurde — er geht
    # in den Nenner der Befundrate ein und muss deshalb beide Rollen zählen,
    # die ein Report im Paar einnehmen kann.
    je_paar, zeitpaare_je_report = {}, {}
    for p in zeitpaare:
        je_paar[p["report"]] = je_paar.get(p["report"], 0) + 1
        for rp in (p["d1"], p["d2"]):
            k = (p["lei"], p["scope"], rp)
            zeitpaare_je_report[k] = zeitpaare_je_report.get(k, 0) + 1

    sprünge, brüche = time_findings(zeitpaare)
    print(f"\nZeitvergleich (#36): {len(zeitzeilen):,} Zeitpaare, davon {ohne_mass:,} "
          f"mit einer gemeldeten Null (kein Sprungmaß) und {unwesentlich:,} "
          f"beidseitig unwesentlich")
    print(f"  {len(zeitpaare):,} messbar in {len(je_paar)} Report-Paaren · "
          f"{len(brüche)} Strukturbrüche · {len(sprünge):,} Einzelsprünge >= "
          f"{TIME_JUMP_MIN:.0f} Größenordnungen")
    if umbindung:
        print(f"  Framework-Brücke: {len(umbindung)} umgebundene dp-Codes übersetzt, "
              f"{len(unsichere_koord)} Koordinaten als unsicher ausgelassen")

    # Beide Reports bekommen den Befund, nicht nur einer. Welcher der zwei
    # falsch liegt, kann diese Prüfung nicht sagen — und die Pfandbriefbank
    # zeigt, dass die naheliegende Wahl die falsche wäre: dort ist der FRÜHERE
    # Report der skalierte (#83) und der spätere sauber. Wer den Sprung dem
    # jeweils neueren zuschriebe, markierte systematisch den richtigen.
    for b in brüche:
        lei, sc, d1, d2 = b["report"]
        for rp, partner in ((d1, d2), (d2, d1)):
            findings.append({
                "lei": lei, "scope": sc, "refPeriod": rp, "bank_name": namen[b["report"]],
                "template_id": "", "cell_row": "", "cell_col": "",
                "rule": "time_break", "value": b["anteil"],
                "reference": b["sprung_median"], "n_population": b["n_vergleichbar"],
                "deviation_orders": b["sprung_median"],
                "spread_widths": None, "robust_z": None,
                "severity": severity(b["sprung_median"]),
                "vergleich_refPeriod": partner,
                "hinweis": f"{b['n_sprung']}/{b['n_vergleichbar']} Zellen springen "
                           f"({b['anteil']*100:.1f} %), Median {b['sprung_median']:.2f}",
            })
    for s in sprünge:
        flags = [s["richtung"]]
        if s["vorzeichenwechsel"]:
            flags.append("vorzeichenwechsel")
        if s["frequenz"]:
            flags.append("frequenz=" + s["frequenz"])
        for rp, partner, hier, dort in ((s["d1"], s["d2"], s["v1"], s["v2"]),
                                        (s["d2"], s["d1"], s["v2"], s["v1"])):
            findings.append({
                "lei": s["lei"], "scope": s["scope"], "refPeriod": rp,
                "bank_name": s["bank_name"], "template_id": s["template_id"],
                "cell_row": s["cell_row"], "cell_col": s["cell_col"],
                "rule": "time_jump", "value": hier, "reference": dort,
                "n_population": je_paar[s["report"]],
                "deviation_orders": s["sprung"],
                # Es gibt hier weder Population noch Korridor: der Maßstab ist
                # der eigene Vorwert, und der hat keine Streuung.
                "spread_widths": None, "robust_z": None,
                "severity": severity(s["sprung"]),
                "vergleich_refPeriod": partner,
                "hinweis": "|".join(flags),
            })

    # --- Ausgabe: Zellstatistik
    with open(CELLS_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["template_id", "cell_row", "cell_col", "row_label", "col_label",
                    "data_type", "n_values", "median_log10", "mad_log10",
                    "spread_p10_p90", "status"])
        for k in sorted(cells):
            st, (rl, cl, dt) = cells[k], labels[k]
            w.writerow([*k, rl, cl, dt, st["n"], f"{st['median']:.3f}",
                        f"{st['mad']:.3f}", f"{st['spread']:.2f}",
                        "unbrauchbar" if st["incoherent"] else "auswertbar"])

    # --- Ausgabe: Einzelbefunde
    # Vollständiger Sortierschlüssel: 97 % der Befunde teilen sich ihren
    # deviation_orders-Wert (754 verschiedene Werte auf 5.969 Zeilen, größte
    # Gruppe 150). Allein danach sortiert entschied die Einfügereihenfolge —
    # also die Zufallsordnung aus SQL —, wie die CSV aussieht. Die Datei wird
    # von der Pipeline nach main committet; der Churn landete dort in der
    # Historie.
    # Sortiert nach Schweregrad, darin nach gemessenem Abstand.
    SEV_RANK = {"hoch": 0, "mittel": 1, "niedrig": 2}
    findings.sort(key=lambda f: (SEV_RANK[f["severity"]], -f["deviation_orders"],
                                 f["lei"], f["scope"], f["refPeriod"],
                                 f["template_id"], f["cell_row"], f["cell_col"],
                                 f["rule"], f.get("vergleich_refPeriod", "")))
    num = lambda v, fmt: "" if v is None else format(v, fmt)   # noqa: E731
    with open(FINDINGS_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lei", "scope", "refPeriod", "bank_name", "template_id",
                    "cell_row", "cell_col", "rule", "value", "reference",
                    "n_population", "deviation_orders", "spread_widths",
                    "robust_z", "severity", "vergleich_refPeriod", "hinweis"])
        for fi in findings:
            w.writerow([fi["lei"], fi["scope"], fi["refPeriod"], fi["bank_name"],
                        fi["template_id"], fi["cell_row"], fi["cell_col"], fi["rule"],
                        f"{fi['value']:.6g}", f"{fi['reference']:.6g}",
                        fi["n_population"], num(fi["deviation_orders"], ".2f"),
                        num(fi["spread_widths"], ".2f"), num(fi["robust_z"], ".1f"),
                        fi["severity"], fi.get("vergleich_refPeriod", ""),
                        fi.get("hinweis", "")])

    # --- Ausgabe: Profil je Institut/Report
    # Rohe Befundzahlen sind als Vergleich unfair: wer 136 Templates meldet,
    # hat mehr Gelegenheiten aufzufallen als wer 4 meldet. Deshalb zusätzlich
    # die Rate je 1.000 tatsächlich PRÜFBARER Fakten (= Fakten in auswertbaren
    # Zellen; Fakten in unbrauchbaren Zellen waren nie im Test und dürfen den
    # Nenner nicht aufblähen).
    checked = {}
    for lei, scope, rp, t, r, c, n in ordered_query(con, f"""
        SELECT lei, scope, refPeriod, template_id, cell_row, cell_col, count(*)
        FROM '{PARQUET}'
        WHERE {COMPARABLE} IS NOT NULL AND {COMPARABLE} <> 0
          AND cell_row IS NOT NULL AND cell_row <> ''
        GROUP BY 1, 2, 3, 4, 5, 6
        ORDER BY 1, 2, 3, 4, 5, 6
    """, "prüfbare Fakten"):
        if (t, r, c) in coherent:
            checked[(lei, scope, rp)] = checked.get((lei, scope, rp), 0) + n

    profile = {}
    for fi in findings:
        key = (fi["lei"], fi["scope"], fi["refPeriod"])
        p = profile.setdefault(key, {"bank_name": fi["bank_name"], "n": 0,
                                     "hoch": 0, "mittel": 0, "niedrig": 0,
                                     "templates": set(), "hoch_templates": set(),
                                     "max_dev": 0.0, "zeit": 0})
        p["n"] += 1
        p[fi["severity"]] += 1
        # Ein `time_break` gilt dem ganzen Report und nennt kein Template —
        # ohne diese Bedingung stünde ein leerer Eintrag in `templates`, und
        # der Viewer markierte im Zweifel alles oder nichts.
        if fi["template_id"]:
            p["templates"].add(fi["template_id"])
        # Templates MIT einem hoch-Befund getrennt (#53): der Viewer markiert
        # template-genau, und erst damit kann er auch abstufen, statt jeden
        # Befund gleich stark zu zeigen.
        if fi["severity"] == "hoch" and fi["template_id"]:
            p["hoch_templates"].add(fi["template_id"])
        if fi["rule"].startswith("time_"):
            p["zeit"] += 1
        p["max_dev"] = max(p["max_dev"], fi["deviation_orders"])

    with open(PROFILE_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["lei", "scope", "refPeriod", "bank_name", "n_findings",
                    "n_hoch", "n_mittel", "n_niedrig", "n_facts_checked",
                    "findings_per_1000", "n_templates", "templates",
                    "templates_hoch", "max_deviation_orders",
                    "n_zeitpaare", "n_zeitbefunde"])
        for (lei, scope, rp), p in sorted(profile.items(),
                                          key=lambda kv: (-kv[1]["n"], kv[0])):
            # Der Nenner zählt GELEGENHEITEN, auffällig zu werden, und seit #36
            # gibt es davon zwei Arten: jede prüfbare Zahl im Querschnitt und
            # jedes vergleichbare Zeitpaar. Wer nur den Querschnitt zählt,
            # rechnet die Zeitbefunde auf einen Nenner, in dem sie nie standen —
            # ein Institut mit vier Stichtagen bekäme dieselbe Rate wie eines
            # mit einem, obwohl es viermal so oft geprüft wurde.
            nchk = checked.get((lei, scope, rp), 0)
            npaare = zeitpaare_je_report.get((lei, scope, rp), 0)
            basis = nchk + npaare
            rate = f"{p['n'] / basis * 1000:.2f}" if basis else ""
            w.writerow([lei, scope, rp, p["bank_name"], p["n"], p["hoch"], p["mittel"],
                        p["niedrig"], nchk, rate, len(p["templates"]),
                        "|".join(sorted(p["templates"])),
                        "|".join(sorted(p["hoch_templates"])),
                        f"{p['max_dev']:.2f}", npaare, p["zeit"]])

    n_reports = con.execute(
        f"SELECT count(*) FROM (SELECT DISTINCT lei, scope, refPeriod FROM '{PARQUET}')").fetchone()[0]
    print(f"\nBefunde: {len(findings):,} in {len(profile)} von {n_reports} Reports")
    for sev in ("hoch", "mittel", "niedrig"):
        print(f"  {sev:8s} {sum(1 for f in findings if f['severity']==sev):,}")

    for regel in ("cell_outlier", "rem_per_head", "time_jump", "time_break"):
        n = sum(1 for f in findings if f["rule"] == regel)
        if n:
            print(f"  Regel {regel:13s} {n:,}")

    print("\nTop-8 Befunde (schwerste zuerst):")
    for fi in findings[:8]:
        print(f"  {str(fi['bank_name'])[:30]:30s} {fi['refPeriod']} "
              f"{fi['template_id']:8s} r{fi['cell_row']} c{fi['cell_col']}  "
              f"{fi['rule']:13s} {fi['deviation_orders']:5.1f} Größenordnungen")

    if brüche:
        print("\nStrukturbrüche (#36) — der Report springt, nicht die Zelle:")
        for b in sorted(brüche, key=lambda b: -b["anteil"])[:8]:
            lei, sc, d1, d2 = b["report"]
            print(f"  {namen[b['report']][:34]:34s} {d1} → {d2}  "
                  f"{b['n_sprung']:5,}/{b['n_vergleichbar']:<6,} = "
                  f"{b['anteil']*100:5.1f} %  Median {b['sprung_median']:.2f}")

    for path in (CELLS_OUT, FINDINGS_OUT, PROFILE_OUT):
        print(f"→ {_rel(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
