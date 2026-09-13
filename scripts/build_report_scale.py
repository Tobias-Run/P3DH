"""Skalenfehler auf REPORT-Ebene erkennen (#83).

Ausgabe: processed/scale_flags.csv

## Warum der vorhandene Detektor diese Fehler nicht finden KANN

Die Deutsche Pfandbriefbank meldet am 2025-06-30 einen Report, in dem 67 von 69
Templates um rund 10^6 danebenliegen — und `check_plausibility.py` (#17) findet
darin **null** Befunde. Das hat zwei Ursachen, und nur die zweite sah zunächst
nach der ganzen Geschichte aus.

**Erstens ist der Ausreisstest einseitig, absichtlich.** `robust_z()` misst nur
den Abstand ÜBER dem Zellmedian; die untere Flanke einer Exposure-Verteilung ist
natürlich (sehr viele Institute haben nahe null Exposure zu einer gegebenen
Kategorie), und symmetrisch geprüft lagen 9.750 von 12.744 Befunden unter dem
Median. Diese Entscheidung ist richtig — aber ein Skalenfehler macht Werte
IMMER zu klein. Er landet damit genau dort, wo nicht hingesehen wird. Gemessen
liegen 1.524 der 1.966 prüfbaren Fakten der pbb mindestens drei Grössenordnungen
UNTER ihrem Zellmedian, und kein einziger löst etwas aus.

Ein Skalenfehler ist deshalb auf Zellebene nicht zu finden, ohne die Regel
aufzugeben, die die Zellebene überhaupt brauchbar macht. Er braucht eine eigene
Ebene — den Report.

**Zweitens vergiften die skalierten Reports die Populationen, in denen sie
stehen.** #17 nimmt Zellen vom Ausreisstest aus, deren Population über mehr als
`INCOHERENT_SPREAD` Grössenordnungen streut; die skalierten Reports weiten genau
diese Zellen. Der Schaden trifft nicht sie selbst (siehe erstens), sondern die
ANDEREN Institute in denselben Zellen: deren Ausreisser nach oben werden
mitgedeckelt.

Schliesst man die hier erkannten Reports aus der Populationsstatistik aus,
fallen die unbrauchbaren Zellen von 592 auf 246 — **354 Zellen werden wieder
prüfbar** —, und die Median-Rumpfbreite sinkt von 3,85 auf 3,15 Grössenordnungen.
In den Einzelbefunden sind das 110 neue und 40 weggefallene.

Die Lösung ist deshalb beides: ein eigener Detektor auf Reportebene (dieses
Skript) UND eine Reihenfolge — erst die Reports, dann die Zellen.

## Drei Klassen, nicht zwei

Die Annahme, der Defekt sitze entweder im ganzen Report oder in einer Zelle,
hat der Detektor selbst widerlegt: ING Bank Slaski steht in der Fundliste von
#83, wird aber reportweit NICHT auffällig (Versatz -0,15). Nachgemessen sind bei
ihm genau zwei Templates skaliert — `67.01.A` und `67.01.B`, also CCyB1 und
damit die Quelle von `footprint.csv` — während 56 Templates sauber sind.

    A   Report     pbb, Bank of Valletta      fast alle Templates
    B   Template   ING Bank Slaski            67.01.*, der Rest sauber
    C   Einzelzelle National Bank of Greece   eine LR-Zelle

Klasse B fällt durch beide Netze: der Reportdetektor sieht sie nicht, und die
Zellprüfung ist in genau diesen Zellen abgeschaltet — dieselbe Selbstabschaltung
eine Ebene tiefer. Deshalb wird der Versatz auf BEIDEN Ebenen gerechnet, und die
Ausgabe trägt eine Spalte `ebene`.

Die Ebene ist auch dann nötig, wenn das Signal von der Reportebene KOMMT. Die
Untergrenze liest eine einzelne Zelle (`61.00` r0040) und schliesst daraus auf
den ganzen Report — was falsch ist, sobald dessen Rumpf messbar sauber ist.
Axa banque meldet am 2025-12-31 KM1 in Millionen (CET1 540,72 · TREA 2.998,88 ·
Verschuldungsmass 10.832,93) und die übrigen 317 monetären Werte in Einheiten.
Der Befund bleibt, er wandert auf `61.00`; die Reportzeile führt das Signal als
`untergrenze_widerlegt`. Siehe `rumpf_widerspricht()`.

## Warum eine einzelne Schwelle nicht reicht

Die Verteilung des TREA über die Reports ist ein Tal, keine leere Lücke:

    < 10^6 EUR      50 Reports    fachlich unmöglich
    10^6 – 10^8     25 Reports    Grauzone — ein sehr kleines Institut kann
                                  dort echt liegen
    > 10^8         723 Reports    unauffällig

Unterhalb der Untergrenze ist die Sache entschieden; in der Grauzone braucht es
ein zweites Signal. Deshalb trägt jede Zeile, **welche** Signale gefeuert haben,
nicht nur ein Ja/Nein.

Und die Untergrenze setzt voraus, dass ein TREA überhaupt GEMELDET ist. 84 der
882 Reports melden keinen — dort greift sie nicht, und eine Prüfung, die genau
deshalb schweigt, hat sich selbst abgeschaltet (derselbe Fehlertyp wie
„Fehlt = Null"). Deshalb entscheidet auch ein sehr grosser Versatz allein, siehe
`VERSATZ_ALLEIN`.

## Die vier Signale

    untergrenze   TREA unter der fachlichen Untergrenze. Eine Säule-3-pflichtige
                  Bank mit 446 EUR Gesamtrisikobetrag gibt es nicht. Setzt
                  voraus, dass ein TREA gemeldet wurde.
    versatz       Median über alle Zellen des Reports von
                  log10(eigener Wert / Populationsmedian derselben Zelle).
                  MUSS in EUR gerechnet werden: in Meldewährung zeigen
                  ungarische Institute +2,6 — das ist der HUF-Kurs, kein Defekt.
                  Bis `VERSATZ_ALLEIN` (-4) von der Institutsgrösse mitverursacht
                  und deshalb nur Zweitsignal; darunter entscheidet er allein.
    zeitreihe     Faktor >= 100 gegen den GRÖSSTEN eigenen anderen Stichtag.
                  Nicht gegen den Median: der folgt der Mehrheit und verstummt,
                  sobald die meisten Stichtage daneben liegen.
    decimals      Der Melder erklärt `decimals = -6`, aber nichts im Report ist
                  auch nur eine Million. Ein Selbstwiderspruch.

## Was hier ausdrücklich NICHT passiert

**Korrigiert wird nichts.** `decimals_monetary` sagt formal etwas anderes als
„in Millionen gemeldet"; wer das geraderückt, entscheidet eine Auslegungsfrage
still und erfindet Daten, falls die Vermutung falsch ist.

**Der Report wird nicht verworfen.** Ein Verhältnis überlebt einen
gleichmässigen Skalenfehler: die RWA-Dichte der Deutschen Pfandbriefbank ist mit
0,43 **richtig**, obwohl Zähler und Nenner beide zu klein sind. Das Urteil sagt
deshalb „absolute Grössen unbrauchbar", nicht „Report unbrauchbar" — sonst gehen
Quoten verloren, die stimmen.

**Und es ist nicht durchgängig.** Bei der Deutschen Pfandbriefbank sind 67 von
69 Templates skaliert, `64.03.B` und `68.00` aber nicht. „Der ganze Report" wäre
zu absolut; das Urteil gilt der überwiegenden Mehrheit der Zellen.

Aufruf: python3 scripts/build_report_scale.py
"""

from pathlib import Path
import collections
import csv
import math
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

PARQUET = ROOT / "processed" / "long" / "p3dh_long.parquet"
OUT = ROOT / "processed" / "scale_flags.csv"

# Fachliche Untergrenze für den Gesamtrisikobetrag. Unterhalb davon gibt es
# keine Säule-3-pflichtige Bank; der kleinste beobachtete Wert ist 446 EUR.
TREA_UNMOEGLICH = 1e6
# Obergrenze der Grauzone: darüber ist auch ein sehr kleines Institut nicht mehr
# erklärungsbedürftig.
TREA_GRAUZONE = 1e8
# Die Zelle, aus der `trea_eur` und damit die Untergrenze stammt: KM1 r0040 c0010.
TREA_TEMPLATE = "61.00"

VERSATZ_SCHWELLE = -2.0     # log10; Zweitsignal, von der Institutsgrösse mitverursacht
# Ab hier trägt der Versatz ALLEIN. Begründung und Eichung:
#
# Der Versatz ist Zweitsignal, weil die Institutsgrösse ihn mitverursacht — aber
# sie verursacht ihn nicht beliebig weit. Gemessen über 816 Reports mit
# messbarem Versatz liegt p10 bei -1,6 und p5 bei -4,2; dazwischen liegt eine
# dünne Zone (8 Reports zwischen -2 und -3, 21 zwischen -3 und -4). Ein Haus,
# das vier Grössenordnungen unter dem Median seiner Zellen meldet, wäre
# zehntausendmal kleiner als der Median der Säule-3-Melder.
#
# Ohne diese Schwelle bleiben Reports unentdeckt, bei denen einfach KEIN TREA
# gemeldet ist: dann greift die Untergrenze nicht, es bleibt bei einem Signal,
# und die Prüfung erklärt sich für zufrieden, WEIL die Kennzahl fehlt. Die
# beiden belegten Fälle:
#
#   DLR Kredit A/S, 2025-12-31 — 598 monetäre Werte, Median 23 EUR, Maximum
#     29.712 EUR, bei einer dänischen Realkreditbank. Versatz -6,21. Nur ein
#     Stichtag, also auch kein Zeitreihensignal.
#   Banco Santander Totta, 2025-06-30 — Median 31.776 EUR gegen 29,8 Mio. am
#     eigenen 2025-12-31. Versatz -5,43.
VERSATZ_ALLEIN = -4.0
ZEITREIHE_FAKTOR = 100      # gegen den grössten eigenen anderen Stichtag
MIN_ZELLEN = 50             # weniger tragen keinen belastbaren Versatz
# Je Template sind es naturgemäss weniger Zellen als je Report. Zehn reichen für
# einen Median, unter dem ein einzelner Ausreisser nicht mehr durchschlägt.
MIN_ZELLEN_TEMPLATE = 10
# Auf Templateebene trennt der Versatz ALLEIN nicht zwischen „skaliert" und
# „für dieses Institut echt klein" — genauso wenig wie auf Reportebene. Dort
# löst ein UNABHÄNGIGES Signal das Problem (die fachliche Untergrenze); hier ist
# es der Sprung gegen die eigenen anderen Stichtage desselben Templates.
#
# Zwei Versuche vorher waren falsch und stehen hier, damit sie nicht
# wiederkommen: eine blosse Schwelle von -2 markierte 376 Templates, darunter
# 13 mit geschätztem Faktor 10^9 — den es als Meldeskala nicht gibt. Eine
# Verschärfung auf „nahe an einer Tausenderpotenz" warf dafür ING Bank Slaski
# hinaus, den einzigen belegten Fall dieser Klasse: dessen Versatz ist -6,672,
# und 0,672 war mehr als die Toleranz. Eine Regel, die den bekannten Fall
# verliert, ist keine Verschärfung, sondern eine Fehlkalibrierung.
TEMPLATE_SPRUNG = 2.5
# Ein Report, dessen Rumpf innerhalb einer Grössenordnung um den
# Populationsmedian liegt, ist NICHT reportweit skaliert — egal was die
# Untergrenze sagt. Sie liest eine einzelne Zelle (`61.00` r0040), und ein
# einzelner Wert trägt kein Urteil über 300 andere.
#
# Der Fall, der das erzwungen hat: Axa banque meldet am 2025-12-31 in KM1
# CET1 540,72 · TREA 2.998,88 · Verschuldungsmaß 10.832,93 — alles in
# Millionen. Die übrigen 317 monetären Werte desselben Reports haben Median
# 2,65 Mio. und Maximum 12,4 Mrd., stehen also in Einheiten. „Der ganze Report
# ist skaliert" wäre für 317 von 318 Werten schlicht falsch. Der Befund bleibt
# — er wandert nur auf die Ebene, auf die er gehört.
VERSATZ_SAUBER = -1.0
# Erreichen weniger als 1 % der Fakten die erklärte Genauigkeit, widerspricht
# sich der Report selbst. Nicht 0 %: einzelne grosse Posten kann es geben.
DECIMALS_ANTEIL = 0.01

FELDER = ["ebene", "entityID", "lei", "scope", "refPeriod", "template_id",
          "bank_name", "country",
          "trea_eur", "versatz_log10", "zeitreihe_faktor", "decimals_deklariert",
          "anteil_erreicht_genauigkeit", "n_zellen", "signale", "urteil",
          "faktor_geschaetzt"]


def _sig(x, n=4):
    if not x or not math.isfinite(x):
        return 0
    return round(x, -int(math.floor(math.log10(abs(x)))) + (n - 1))


def sammle(con):
    """Alle Bausteine je Report in EINEM Durchgang durch das Parquet."""
    from determinism import ordered_query as ordered

    # `any_value()` und `quantile_cont()` sind nicht reproduzierbar — der
    # Determinismus-Guard lehnt sie ab, zu Recht. `max()` liefert für die je
    # Report konstanten Felder dasselbe, und die decimals-Prüfung wird durch die
    # Umformulierung sogar schärfer: statt eines Perzentils zählt sie, wie viele
    # Fakten die erklärte Genauigkeit überhaupt ERREICHEN.
    kopf = ordered(con, """
        SELECT entityID, refPeriod,
               max(lei) AS lei, max(scope) AS scope,
               max(bank_name) AS bank_name, max(country) AS country,
               median(decimals_monetary) AS dec,
               count(*) AS n_monetaer,
               sum(CASE WHEN decimals_monetary IS NOT NULL
                         AND decimals_monetary < 0
                         AND abs(fact_value_eur) >= pow(10, -decimals_monetary)
                        THEN 1 ELSE 0 END) AS n_erreicht,
               max(CASE WHEN template_id='61.00' AND cell_col='0010'
                        AND cell_row='0040' THEN fact_value_eur END) AS trea
        FROM p
        WHERE data_type='monetary' AND fact_value_eur IS NOT NULL
          AND abs(fact_value_eur) > 0
        GROUP BY entityID, refPeriod
        ORDER BY entityID, refPeriod
    """, "Reports / Kopfdaten")

    # Populationsmedian je Zelle UND Stichtag — ein Vergleich über Stichtage
    # hinweg wäre zugleich ein Zeitvergleich.
    versatz = ordered(con, f"""
        WITH med AS (
          SELECT template_id, cell_row, cell_col, refPeriod,
                 median(log10(abs(fact_value_eur))) AS m
          FROM p
          WHERE data_type='monetary' AND fact_value_eur IS NOT NULL
            AND abs(fact_value_eur) > 0
          GROUP BY 1,2,3,4 HAVING count(*) >= 20
        )
        SELECT p.entityID, p.refPeriod,
               median(log10(abs(p.fact_value_eur)) - med.m) AS versatz,
               count(*) AS n
        FROM p JOIN med USING (template_id, cell_row, cell_col, refPeriod)
        WHERE p.data_type='monetary' AND p.fact_value_eur IS NOT NULL
          AND abs(p.fact_value_eur) > 0
        GROUP BY p.entityID, p.refPeriod
        HAVING count(*) >= {MIN_ZELLEN}
        ORDER BY p.entityID, p.refPeriod
    """, "Reports / Populationsversatz")

    # Dieselbe Rechnung je (Report, Template) — für Klasse B.
    je_template = ordered(con, f"""
        WITH med AS (
          SELECT template_id, cell_row, cell_col, refPeriod,
                 median(log10(abs(fact_value_eur))) AS m
          FROM p
          WHERE data_type='monetary' AND fact_value_eur IS NOT NULL
            AND abs(fact_value_eur) > 0
          GROUP BY 1,2,3,4 HAVING count(*) >= 20
        )
        SELECT p.entityID, p.refPeriod, p.template_id,
               median(log10(abs(p.fact_value_eur)) - med.m) AS versatz,
               count(*) AS n
        FROM p JOIN med USING (template_id, cell_row, cell_col, refPeriod)
        WHERE p.data_type='monetary' AND p.fact_value_eur IS NOT NULL
          AND abs(p.fact_value_eur) > 0
        GROUP BY p.entityID, p.refPeriod, p.template_id
        HAVING count(*) >= {MIN_ZELLEN_TEMPLATE}
        ORDER BY p.entityID, p.refPeriod, p.template_id
    """, "Templates / Populationsversatz")

    return (kopf, {(e, d): (v, n) for e, d, v, n in versatz},
            [(e, d, t, v, n) for e, d, t, v, n in je_template])


def zeitreihen_faktor(trea_je_report):
    """{(entityID, refPeriod): Faktor} gegen den GRÖSSTEN eigenen Stichtag.

    Gegen den Median zu prüfen war der erste Entwurf und er war falsch — aber
    anders falsch, als hier zunächst stand. Der Median folgt der MEHRHEIT: liegen
    drei von vier Stichtagen daneben, sitzt er im kaputten Bereich, und die Regel
    meldet gar nichts mehr. Sie verstummt also genau dort, wo der Defekt am
    ausgeprägtesten ist. Nachgerechnet für {10^4, 10^4, 10^4, 10^10}: das Maximum
    markiert die drei kleinen Stichtage, der Median keinen einzigen.

    Der Skalenfehler macht den Wert immer zu KLEIN, also ist der grösste eigene
    Stichtag der einzige Bezug, der nicht mitwandert.

    Das erklärt zugleich, warum `zeitreihe` nur 5-mal feuert: wer wie Zagrebačka
    banka an ALLEN Stichtagen skaliert meldet, hat keinen sauberen Bezug mehr.
    Solche Fälle fängt die fachliche Untergrenze, nicht dieses Signal.
    """
    je_institut = collections.defaultdict(dict)
    for (eid, rp), trea in trea_je_report.items():
        if trea and trea > 0:
            je_institut[eid][rp] = trea
    out = {}
    for eid, werte in je_institut.items():
        if len(werte) < 2:
            continue
        groesster = max(werte.values())
        for rp, v in werte.items():
            out[(eid, rp)] = groesster / v
    return out


def template_spruenge(je_template):
    """{(entityID, refPeriod, template): (versatz, sprung, n)} — Klasse B.

    Dasselbe Institut, dasselbe Template, ein Sprung von `TEMPLATE_SPRUNG`
    Grössenordnungen gegen den besten eigenen Stichtag. Das Signal ist
    unabhängig von der Institutsgrösse: ein kleines Haus ist an allen
    Stichtagen klein, ein skaliertes nur an einem.

    Braucht mindestens zwei Stichtage für dieses Template. Mit nur einem gibt
    es keine Vergleichsgrundlage — dann steht hier nichts, nicht „sauber".
    """
    je = collections.defaultdict(dict)
    for eid, rp, tid, v, n in je_template:
        if v is not None:
            je[(eid, tid)][rp] = (v, n)
    out = {}
    for (eid, tid), werte in je.items():
        if len(werte) < 2:
            continue
        hoechster = max(v for v, _ in werte.values())
        for rp, (v, n) in werte.items():
            if hoechster - v >= TEMPLATE_SPRUNG:
                out[(eid, rp, tid)] = (v, hoechster - v, n)
    return out


def rumpf_widerspricht(versatz):
    """Liegt der Rumpf des Reports messbar nahe an der Population?

    Dann kann er nicht reportweit skaliert sein, und die Untergrenze — die eine
    EINZELNE Zelle liest — ist als Aussage über den Report widerlegt.

    `None` heisst „nicht messbar" (zu wenige vergleichbare Zellen) und ist
    ausdrücklich KEIN Widerspruch: vier der sechs betroffenen Reports haben
    n_zellen = 0. Fehlendes Wissen als Entlastung zu lesen wäre „Fehlt = Null".
    """
    return versatz is not None and versatz > VERSATZ_SAUBER


def urteil_von(signale, trea, versatz=None):
    """Sicher, Verdacht, oder unauffällig — mit dem Grund in `signale`.

    Die Untergrenze allein entscheidet, wenn sie greift — ausser der Rumpf des
    Reports widerspricht ihr. `versatz` ist dieser Widerspruch: liegt er über
    `VERSATZ_SAUBER`, steht das Urteil gegen 300 gemessene Zellen, und dann
    gewinnen die Zellen. Der Befund geht nicht verloren, er wandert auf die
    Templateebene (siehe `nur_km1`).

    In der Grauzone braucht es zwei unabhängige Signale, weil dort ein sehr
    kleines Institut echt liegen kann.

    Ein Versatz jenseits von `VERSATZ_ALLEIN` entscheidet ebenfalls allein.
    Ohne das bleibt die Prüfung stumm, sobald KEIN TREA gemeldet ist: dann
    greift die Untergrenze nicht, es bleibt bei einem Signal — und die Prüfung
    erklärt sich für zufrieden, WEIL die Kennzahl fehlt, an der sie hängt. Das
    ist derselbe Fehlertyp wie „Fehlt = Null", nur eine Ebene höher.
    """
    if rumpf_widerspricht(versatz):
        # Nicht früh zurückkehren: die übrigen Signale gelten weiter, nur die
        # Untergrenze ist widerlegt.
        signale = [s for s in signale if s != "untergrenze"]
    if "untergrenze" in signale:
        return "skaliert"
    if versatz is not None and versatz <= VERSATZ_ALLEIN:
        return "skaliert"
    if trea is not None and trea < TREA_GRAUZONE:
        if len(signale) >= 2:
            return "skaliert"
        if signale:
            return "verdacht"
    elif len(signale) >= 2:
        return "verdacht"
    return "unauffaellig"


def faktor_von(versatz, zr):
    """Geschätzter Faktor, auf die nächste Tausenderpotenz gerundet.

    Melder skalieren in Tausend oder Million, nicht in beliebigen Faktoren.
    Ein gerundeter Schätzer sagt deshalb mehr als drei Nachkommastellen einer
    Grösse, die von der Institutsgrösse mitverursacht ist.

    Gemessen bleiben 10^3 (62x) und 10^6 (56x) — und ein einziges 10^9:
    Société générale, `27.02.B`, 2025-06-30. Dort liegen alle 27 Beträge
    zwischen 1 und 954 EUR, am 2025-12-31 dieselben Zellen zwischen 0,9 Mio.
    und 131 Mrd. Der SPRUNG ist also real und das Urteil `skaliert` richtig;
    nur die Zahl 10^9 ist als Meldeskala unplausibel. Die Spalte heisst deshalb
    `faktor_geschaetzt` und nicht `faktor` — sie ist ein Hinweis, keine
    Feststellung, und wird nirgends zum Rechnen benutzt.
    """
    kandidat = None
    if zr and zr >= ZEITREIHE_FAKTOR:
        kandidat = math.log10(zr)
    elif versatz is not None and versatz <= VERSATZ_SCHWELLE:
        kandidat = -versatz
    if kandidat is None:
        return ""
    stufe = round(kandidat / 3) * 3
    return f"10^{int(stufe)}" if stufe >= 3 else ""


def build():
    import duckdb
    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM '{PARQUET.as_posix()}'")
    kopf, versatz, je_template = sammle(con)

    trea_je = {(e, d): trea for e, d, _, _, _, _, _, _, _, trea in kopf}
    zr = zeitreihen_faktor(trea_je)

    zeilen, km1 = [], []
    for eid, rp, lei, scope, nm, land, dec, n_mon, n_err, trea in kopf:
        v, n = versatz.get((eid, rp), (None, 0))
        f = zr.get((eid, rp))
        signale = []
        if trea is not None and 0 < trea < TREA_UNMOEGLICH:
            signale.append("untergrenze")
        if v is not None and v <= VERSATZ_SCHWELLE:
            signale.append("versatz")
        if f is not None and f >= ZEITREIHE_FAKTOR:
            signale.append("zeitreihe")
        # Selbstwiderspruch: der Melder erklärt Millionen- oder
        # Tausendergenauigkeit, aber so gut wie nichts im Report erreicht sie.
        anteil = (n_err / n_mon) if n_mon else None
        if dec is not None and dec <= -3 and anteil is not None and anteil < DECIMALS_ANTEIL:
            signale.append("decimals")
        zeilen.append({
            "ebene": "report", "template_id": "",
            "entityID": eid, "lei": lei or "", "scope": scope or "",
            "refPeriod": rp, "bank_name": nm or "", "country": land or "",
            "trea_eur": _sig(trea) if trea else "",
            "versatz_log10": round(v, 3) if v is not None else "",
            "zeitreihe_faktor": round(f) if f else "",
            "decimals_deklariert": dec if dec is not None else "",
            "anteil_erreicht_genauigkeit": round(anteil, 4) if anteil is not None else "",
            "n_zellen": n,
            # Ein widerlegtes Signal wird nicht verschwiegen, sondern als
            # widerlegt geführt. Sonst stünde in der Zeile `untergrenze` neben
            # `unauffaellig`, und wer nach Signalen filtert, liest einen
            # Widerspruch, den er nicht auflösen kann.
            "signale": "|".join(s + "_widerlegt" if s == "untergrenze"
                                and rumpf_widerspricht(v) else s for s in signale),
            "urteil": urteil_von(signale, trea, v),
            "faktor_geschaetzt": faktor_von(v, f),
        })
        # Der von `rumpf_widerspricht` entkräftete Fall geht nicht verloren, er
        # wandert auf die Ebene, auf die er gehört: die Untergrenze liest eine
        # Zelle in `61.00`, und wenn der Rumpf des Reports sauber ist, ist genau
        # dieses Template skaliert — nicht der Report.
        if "untergrenze" in signale and rumpf_widerspricht(v):
            km1.append({
                "ebene": "template", "template_id": TREA_TEMPLATE,
                "entityID": eid, "lei": lei or "", "scope": scope or "",
                "refPeriod": rp, "bank_name": nm or "", "country": land or "",
                "trea_eur": _sig(trea) if trea else "", "versatz_log10": round(v, 3),
                "zeitreihe_faktor": round(f) if f else "",
                "decimals_deklariert": dec if dec is not None else "",
                "anteil_erreicht_genauigkeit": "", "n_zellen": n,
                "signale": "untergrenze", "urteil": "skaliert",
                "faktor_geschaetzt": "",
            })
    zeilen.extend(km1)

    # Klasse B: skalierte EINZELNE Templates in einem sonst sauberen Report.
    # Wo der Report schon markiert ist, waere die Template-Zeile nur Rauschen —
    # sie sagte dasselbe noch einmal, nur kleinteiliger.
    schon = {(z["entityID"], z["refPeriod"]) for z in zeilen
             if z["urteil"] in ("skaliert", "verdacht")}
    kopfdaten = {(z["entityID"], z["refPeriod"]): z for z in zeilen}
    sprung = template_spruenge(je_template)
    for (eid, rp, tid), (v, hoch, n) in sorted(sprung.items()):
        if (eid, rp) in schon:
            continue
        k = kopfdaten.get((eid, rp), {})
        zeilen.append({
            "ebene": "template", "template_id": tid,
            "entityID": eid, "lei": k.get("lei", ""), "scope": k.get("scope", ""),
            "refPeriod": rp, "bank_name": k.get("bank_name", ""),
            "country": k.get("country", ""),
            "trea_eur": "", "versatz_log10": round(v, 3),
            "zeitreihe_faktor": round(10 ** hoch), "decimals_deklariert": "",
            "anteil_erreicht_genauigkeit": "", "n_zellen": n,
            "signale": "template_sprung", "urteil": "skaliert",
            "faktor_geschaetzt": faktor_von(None, 10 ** hoch),
        })

    zeilen.sort(key=lambda z: (z["ebene"], z["entityID"], z["refPeriod"],
                               z["template_id"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, FELDER)
        w.writeheader()
        w.writerows(zeilen)

    print(f"✓ {OUT}  ({len(zeilen)} Zeilen)")
    for s in bericht(zeilen):
        print("  " + s)
    return zeilen


def bericht(zeilen):
    eb = collections.Counter(z["ebene"] for z in zeilen)
    u = collections.Counter(z["urteil"] for z in zeilen if z["ebene"] == "report")
    aus = ["Ebenen: " + "  ".join(f"{k}={v}" for k, v in sorted(eb.items())),
           "Report-Urteil: " + "  ".join(f"{k}={v}" for k, v in sorted(u.items()))]
    tpl = [z for z in zeilen if z["ebene"] == "template"]
    if tpl:
        wo = collections.Counter(z["template_id"] for z in tpl)
        aus.append(f"einzeln skalierte Templates in sonst sauberen Reports: {len(tpl)}"
                   f"  (haeufigste: " +
                   "  ".join(f"{k}={v}" for k, v in wo.most_common(5)) + ")")
    s = collections.Counter()
    for z in zeilen:
        for sig in z["signale"].split("|"):
            if sig:
                s[sig] += 1
    aus.append("Signale: " + "  ".join(f"{k}={v}" for k, v in s.most_common()))
    f = collections.Counter(z["faktor_geschaetzt"] for z in zeilen if z["faktor_geschaetzt"])
    aus.append("geschätzter Faktor: " + "  ".join(f"{k}={v}" for k, v in sorted(f.items())))
    sk = [z for z in zeilen if z["urteil"] == "skaliert"]
    if sk:
        aus.append("als skaliert eingestuft (bis zu 12):")
        for z in sorted(sk, key=lambda z: z["bank_name"])[:12]:
            aus.append(f"  {z['bank_name'][:34]:36} {z['refPeriod']}  "
                       f"{z['faktor_geschaetzt']:>5}  [{z['signale']}]")
    return aus


if __name__ == "__main__":
    build()
