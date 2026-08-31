# Was der Voll-Load hergibt — Analyse-Ideen, datengeerdet

Stand nach dem Voll-Load (2026-08-31): 882 Reports, 474 Institute, 2.295.224
Fakten, 31 Länder, 5 Stichtage. Jede Zahl unten ist gemessen, nicht geschätzt;
die Prüfbefehle stehen dabei.

Die Leitfrage ist nicht „welche Kennzahl können wir noch rechnen" — davon gibt es
beliebig viele und EDAP zeigt sie besser. Sie lautet: **welche Dimension des
Datensatzes schaut sich sonst niemand an?**

---

## Der blinde Fleck: die Meta-Ebene

EDAP zeigt Einreichungen. Wir haben zusätzlich den **Katalog über die
Einreichungen** — 4.278 Zeilen mit Zeitstempel, Resubmission-Historie und
Filing-Indicators. Diese Ebene ist bislang komplett ungenutzt, und sie beschreibt
nicht die Bank, sondern **ihr Verhalten**. Drei Ideen daraus.

### A1. Korrekturverhalten als unabhängiges Qualitätssignal ⭐ stärkster Fund

Von 4.278 Einreichungen sind **472 Korrekturen**; 162 von 489 Instituten haben
mindestens einmal nachgemeldet, ein Report wurde **zehnmal** eingereicht.

Die interessante Frage ist nicht, wer korrigiert — sondern ob das Korrigieren mit
dem zusammenhängt, was wir unabhängig davon in den *Werten* gefunden haben (#17).
Gemessen:

| | Korrekturen/Institut | korrigiert überhaupt |
|---|---|---|
| mit Plausibilitätsbefunden (n=238) | **1,34** | **42 %** |
| ohne Befunde (n=251) | 0,61 | 25 % |

Der naheliegende Einwand ist Größe: große Melder haben mehr Fakten (also mehr
Befunde) und mehr Einreichungen (also mehr Korrekturen). Der Effekt überlebt die
Schichtung nach Meldeumfang — Korrekturen **je Einreichung**:

| Einreichungen | mit Befunden | ohne Befunde |
|---|---|---|
| 1–3 | 0,222 (n=15) | 0,120 (n=61) |
| 4–8 | 0,140 (n=124) | 0,079 (n=137) |
| 9+ | 0,151 (n=99) | 0,103 (n=53) |

In jeder Klasse 1,5–1,9×. **Das ist eine externe Validierung des #17-Verfahrens:
die Institute selbst bestätigen durch ihr Korrekturverhalten, dass dort etwas
nicht stimmte.** Wir haben damit ein Gütemaß für unsere eigene Methode, das nicht
aus derselben Quelle stammt wie die Methode.

Die Kehrseite ist die eigentliche Nachricht: **26 der 48 Institute mit
`hoch`-Befunden haben nie etwas korrigiert.** Das sind die persistenten Fehler —
und das ist eine Liste, die es sonst nirgends gibt.

Warum nur wir das können: es braucht den Katalog (Verhalten) *und* die
Wertanalyse (#17) gleichzeitig. EDAP hat beides, verknüpft es aber nicht.

### A2. Der Offenlegungs-Lag und seine Kompression

Abstand zwischen Stichtag und Einreichung, Median über alle Einreichungen:

```
2025-06-30   252 Tage   (p10 190, p90 351, max 482)
2025-09-30   162
2025-10-31   144
2025-12-31   135        (p10  71, p90 177)
2026-03-31    59        (p10  30, p90  85)
```

Das ist kein gleichmäßiger Trend, sondern ein **Regimewechsel**: P3DH ging am
26.01.2026 live, die älteren Stichtage wurden nachgereicht. Der 2026-03-31-Wert
(59 Tage) ist der erste, der den eingeschwungenen Zustand zeigt.

Daraus wird eine Kennzahl je Institut: **Rechtzeitigkeit**. Wer meldet regelmäßig
im letzten Dezil? Korreliert Verspätung mit Größe, Land, oder mit den
Plausibilitätsbefunden aus A1? Das ist eine Governance-Aussage, die kein
Geschäftsbericht enthält.

Vorsicht bei der Interpretation: die Rechtsfrist unterscheidet sich je
Institutstyp (CRR Art. 433a–c). Ein Vergleich ist nur *innerhalb* einer
Frequenzklasse zulässig — die lässt sich aus der Population lernen (siehe A3).

### A3. Offenlegungs-Umfang als Zeitreihe

199 von 209 Entitäten mit ≥2 Stichtagen ändern zwischen zwei Terminen, welche
Templates sie offenlegen: 4.594 Templates neu, 5.168 eingestellt.

**Das ist überwiegend kein Verhalten, sondern Melderhythmus** — Jahrestemplates
erscheinen nur zum Jahresende (belegt: 3.362 Fakten je Report am 31.12. gegen
375 am 31.03.). Genau das macht es zur interessanten Aufgabe:

1. Aus der Population das **erwartete Frequenzmuster je Template** lernen
   (jährlich / halbjährlich / quartalsweise).
2. Erst die Abweichung davon ist ein Signal: ein Institut, das ein Template
   einstellt, das seine Frequenzklasse weiter meldet.

Das ist CRR Art. 432 (Auslassung wegen Nicht-Wesentlichkeit) in Aktion —
beobachtbar, statt nur behauptet. Und es ist die zeitliche Erweiterung von #21:
dort zeigen wir *dass* etwas nicht offengelegt wird, hier *seit wann*.

---

## Struktur statt Kennzahl

### B1. Konzerngraph über GLEIF ⭐ methodisch am reizvollsten

Der Bestand hat eine merkwürdige Asymmetrie: **325 Institute melden konsolidiert
(CON), 148 auf Einzelinstitutsebene (IND) — und genau eines beides.** Die
IND-Melder sind also fast alle Töchter von irgendwem. Von wem, steht nicht in den
Daten.

GLEIF beantwortet das (API getestet, HTTP 200, Golden Copy vom 31.08.2026). Auf
einer Stichprobe von 25 unserer LEIs:

- 7 haben einen Ultimate Parent bei GLEIF
- **3 davon liegen selbst in unserem Bestand** → hochgerechnet ~57 Konzernkanten
  *innerhalb* unserer 474 Institute

Damit wird eine Prüfung möglich, die ohne LEI-Verknüpfung nicht existiert:
**Konsolidierungsabgleich.** Der CON-Report der Mutter muss sich zu den
IND-Reports ihrer Töchter plausibel verhalten — Exposures der Töchter können
nicht größer sein als die der Gruppe, das Länderprofil der Gruppe muss die
Töchter enthalten. Jede Verletzung ist entweder ein Meldefehler oder ein
Konsolidierungskreis-Unterschied, und beides ist berichtenswert.

Zweiter Nutzen: **Doppelzählung erkennen.** Wer heute Länder-Exposures über alle
474 Institute summiert, zählt Mutter und Tochter doppelt. Der Konzerngraph ist
die Voraussetzung dafür, dass Aggregate über die Population überhaupt
interpretierbar sind (betrifft #19 direkt).

### B2. Bank↔Land als bipartiter Graph

`67.01.A` (CCyB1) liefert Exposure je Land je Institut — 262 Institute, 1–203
Länder, Mediandomestizität 83,8 % (aus der #11-Analyse). Als Graph gelesen:

- **Konzentration je Land**: welche Länder hängen an wenigen Gläubigerbanken?
  Das ist die Gegenrichtung zur üblichen Frage (welche Bank hängt an welchem
  Land) und aufsichtlich mindestens so relevant.
- **Ansteckungspfade**: zwei Banken sind verbunden, wenn sie dieselben
  Auslandsmärkte tragen. Die Kantengewichte machen aus #13 (Ähnlichkeit) einen
  echten Risiko-Graphen statt einer Sortierung.
- ⚠️ Setzt B1 voraus, sonst zählen Konzerne mehrfach; und `eba_GA:x1` ist die
  Summenzeile, kein Land (belegt an 89 von 96 Instituten).

### B3. Intra-Instituts-Konsistenz über die Zeit

Prototypisch gemessen: 89.846 vergleichbare Zellpaare desselben Instituts über
zwei Stichtage, davon **6.111 Sprünge über ≥3 und 2.584 über ≥6
Größenordnungen**. Beispiel: Svensk Exportkredit meldet CVA-Risiko (`60.00.A`
r0120) mit 3,16·10⁷, dann −5,9·10⁻⁸, dann wieder 1,8·10⁷.

Dieser Test ist **stärker als der Querschnitt aus #17**, weil das Institut sein
eigener Maßstab ist — keine Peer-Gruppe, keine Größenannahme, keine
Währungsfrage. Erst der Voll-Load macht ihn tragfähig (Entitäten mit ≥2
Stichtagen: 88 → 209).

---

## Externe Daten: was trägt und was nicht

### C1. Abgleich gegen die EBA-eigenen Aggregate ⭐ höchster Erkenntniswert je Aufwand

Die EBA veröffentlicht selbst aggregierte Kennzahlen (Risk Dashboard,
Transparency Exercise). **Niemand prüft, ob die Summe der Pillar-3-Einreichungen
diese Aggregate trifft.** Wir können das — bottom-up gegen top-down.

Drei mögliche Ausgänge, alle wertvoll:
- Es stimmt → starke Validierung unserer gesamten Pipeline, extern belegt.
- Es weicht systematisch ab → Aussage über Abdeckung (wer fehlt in P3DH?).
- Es weicht sprunghaft ab → wir haben einen Fehler, und zwar einen auffindbaren.

Voraussetzung ist B1 (Doppelzählung) und eine saubere Grundgesamtheit.

### C2. Was ich NICHT verfolgen würde

Zwei Ideen wurden in diesem Projekt schon datenbasiert verworfen; sie sehen
attraktiv aus und sind es nicht:

- **EURIBOR als Regressor** (#11/#15): hat zu einem einzelnen Stichtag *null*
  Querschnittsvarianz. Auch nach dem Voll-Load haben 266 von 474 Entitäten nur
  einen Stichtag — für eine Zeitreihenregression bleibt zu wenig.
- **BIP als Regressor** (#14): länderkonstant, damit ~30 effektive
  Beobachtungen statt 474. Als deskriptive Kontextspalte in Ordnung, als
  erklärende Variable eine Scheinpräzision.

Die Lehre daraus gilt allgemein: **externe Makro-Indikatoren haben fast nie die
Granularität unseres Bestands.** Was trägt, sind externe Daten auf
*Instituts*-Ebene — GLEIF (B1) ist das Musterbeispiel, weil es je LEI eine
Aussage macht, nicht je Land.

### C3. Kandidaten in dieser Kategorie (ungeprüft)

Nach demselben Kriterium — Auflösung je Institut, nicht je Land — wären zu
prüfen: EZB-Liste der signifikanten Institute (SSM-Status je LEI), nationale
Handelsregister-Rechtsformen (Genossenschaft/Sparkasse/AG als
Geschäftsmodell-Proxy, ergänzend zum Template-Fingerabdruck), ISIN/Börsennotierung
über GLEIF (börsennotiert vs. nicht — Offenlegungsanreize unterscheiden sich).
Jeweils erst die Verknüpfungsquote messen, bevor eine Analyse darauf gebaut wird;
die GLEIF-Stichprobe oben (7 von 25) zeigt, warum.

---

## Reihenfolge

1. **A1** — fertig rechenbar, kein Netz, validiert #17 extern. Größter
   Erkenntnisgewinn je Aufwand.
2. **B1** — schaltet B2, C1 und #19 frei; braucht ~474 GLEIF-Abfragen (Netz).
3. **B3** — Daten liegen, Verfahren prototypisch belegt.
4. **A3** — braucht das Frequenzmodell als Vorarbeit.
5. **A2** — klein, aber erst nach A3 sauber interpretierbar.
6. **C1** — der Abschluss, sobald B1 die Doppelzählung löst.

## Reproduktion

Alle Zahlen oben aus `processed/long/p3dh_long.parquet`,
`processed/filing_indicators.csv`, `processed/quality_profile.csv` und
`interim/edap_recon/manifest_full.csv` — Letzteres ist die einzige Quelle für
Zeitstempel und Resubmissions und damit die Grundlage des ganzen Abschnitts A.

---

# Nachtrag: externe Quellen, die tatsächlich tragen

Geschrieben nach der Erkenntnis aus C2: externe Makro-Indikatoren scheitern an
der Auflösung. Das Auswahlkriterium lautet deshalb **„macht die Quelle eine
Aussage je Institut?"** — nicht je Land, nicht je Monat. Jede Quelle unten ist
auf Verknüpfbarkeit getestet, mit gemessener Trefferquote.

## D1. Der DISDOCS-Korpus — Text gegen Zahl ⭐ liegt bereits vor

Wir schließen ihn **absichtlich aus** (`build_parse_manifest.py`: `if "DISDOCS"
in r["url"]: continue`), weil er kein XBRL-CSV ist. Umfang:

```
1.073 PDF-Pakete im Katalog (von 4.278)
  424 von 489 Instituten haben mindestens eines
  je Stichtag: 190 / 125 / 4 / 658 / 96
```

Das sind die **qualitativen Pillar-3-Berichte** — der Fließtext, mit dem die
Institute ihre Zahlen erklären. Wir haben die URLs, und wir haben als einzige
beide Korpora über (LEI, Stichtag) verknüpfbar.

Die Analyse, die daraus folgt, gibt es nirgends: **sagt der Text, was die Zahlen
sagen?** Ein Institut mit einer NPL-Quote im obersten Dezil, dessen Bericht von
„solider Kreditqualität" spricht, ist ein Befund — und zwar einer, den weder ein
Zahlenwerk noch ein Textkorpus allein hergibt. Ebenso: Berichtslänge gegen Anzahl
tatsächlich offengelegter Templates (viel Text, wenig Substanz).

Aufwand: PDF-Extraktion (`pdf`-Werkzeuge vorhanden), keine neue Datenquelle.
Vorsicht: Sprachenvielfalt (31 Länder) macht eine naive Schlagwortsuche
unbrauchbar; der erste Schritt ist ein ehrlicher Test der Extraktionsqualität,
nicht gleich eine Auswertung.

## D2. Ereignisstudie: Einreichungszeitstempel × Marktdaten ⭐ originellste Idee

Wir besitzen den **Einreichungszeitpunkt auf die Sekunde** (`submission_ts`,
4.278 Zeilen). Das ist ein Ereignisdatum — und Ereignisdaten sind die Währung der
Kapitalmarktforschung.

Verknüpfbarkeit gemessen (GLEIF `/isins`): **14 von 20 Stichproben-Instituten
emittieren Wertpapiere (70 %)**, hochgerechnet ~331 von 474. Spannweite von 51
ISINs (CaixaBank) bis 42.124 (BNP Paribas).

Die Frage dahinter ist die Existenzfrage der Säule 3: **reagiert der Markt
überhaupt auf Offenlegung?** Und die schärfere Variante: reagiert er *stärker*,
wenn die Offenlegung etwas Unangenehmes enthält — hohe NPL-Quote, ein
`hoch`-Befund aus #17, eine spätere Korrektur (#31)? Wenn ja, ist Säule 3
informativ; wenn nein, ist sie Ritual. Das ist eine Aussage über das
Regulierungsinstrument selbst, nicht über eine Bank.

Warum das sonst niemand macht: EDAP zeigt die Datei, nicht den
Zeitstempel-Datensatz. Wir haben ihn als Tabelle.

Grenzen, ehrlich: ein Aktien-Ereignisfenster deckt nur die börsennotierten
Institute ab — Genossenschaftsbanken und Sparkassen fallen heraus, und die sind
in unserer Population zahlreich. Anleihe-ISINs decken mehr ab, sind aber illiquider.
Und Marktdaten selbst sind keine offene Quelle; das ist die eigentliche Hürde,
nicht die Verknüpfung.

## D3. Wikidata — die Institution als Organisation

Wikidata führt die LEI als Property `P1278`; **53.336 Entitäten** tragen sie.
Trefferquote auf unserem Bestand: **26 von 40 Stichproben-LEIs (65 %)**, mit
Gründungsjahr und Mitarbeiterzahl (z. B. Helaba 6.148, DZ Bank 24.642).

Die interessante Verknüpfung ist nicht „Bank ist alt", sondern eine Kennzahl, die
erst durch die Kombination entsteht: **Anteil der „identified staff" an der
Gesamtbelegschaft.** REM1 (`30.01` r0010) liefert die Zahl der Risikoträger,
Wikidata die Gesamtzahl der Mitarbeiter. Der Quotient sagt, wie breit ein Institut
den Kreis der Risikoträger zieht — eine Governance-Aussage, die in keiner
Einzelquelle steht und die aufsichtlich unmittelbar relevant ist (CRD Art. 92).

## D4. OpenStreetMap — physische gegen bilanzielle Präsenz (ungeprüft)

Bankfilialen sind in OSM mit `operator`-Tag erfasst. Die Idee: **stimmt der
physische Fußabdruck mit dem gemeldeten Länderexposure überein?**

Ein Institut mit Exposure in 40 Ländern und Filialen in zweien ist ein
grenzüberschreitender Wholesale-Kreditgeber; eines mit 500 Filialen in einem Land
ist Retail. Das ist ein **Geschäftsmodell-Klassifikator aus einer Quelle
ausserhalb der Aufsichtsdaten** — und damit eine unabhängige Gegenprobe zu den
Archetypen, die wir bisher nur aus dem Template-Fingerabdruck ableiten
(`phase4_analysis_ideas.md`).

Ungeprüft: die Verknüpfung läuft über den Namen, nicht über die LEI, und
OSM-`operator`-Tags sind uneinheitlich. Vor jeder Analyse steht eine gemessene
Trefferquote — dieselbe Disziplin wie bei D2/D3.

## D5. Die Negativmenge — wer fehlt? ⭐ am nächsten am Projektkern

Alle bisherigen Ideen fragen, was in den Daten steht. Diese fragt das Gegenteil
und ist damit „Fehlt ≠ Null" auf Populationsebene:

**Welche Institute müssten offenlegen und tauchen im EDAP-Katalog gar nicht auf?**

Die EZB veröffentlicht die Liste der signifikanten Institute (SSM), die nationalen
Aufseher ihre Listen der weniger signifikanten. Der Abgleich gegen unsere 489
Katalog-Institute liefert die Menge derer, die fehlen. Jeder Eintrag darin ist
entweder eine berechtigte Ausnahme (Proportionalität, CRR Art. 433a–c) oder eine
Lücke im Hub selbst.

Das ist die stärkste Form der Aussage, die dieses Projekt treffen kann: nicht
„diese Zahl ist auffällig", sondern **„hier fehlt eine ganze Bank"**. Und es ist
exakt Arbeitsprinzip 3, eine Ebene höher angewendet.

Voraussetzung: #32 (Konzerngraph), sonst hält man Töchter für fehlend, die über
die Mutter konsolidiert offenlegen — was legitim ist.

## Auswahlregel für künftige Quellen

Die drei Fehlschläge (BIP, EURIBOR, und beinahe die ISIN-Idee) und die vier
Treffer folgen derselben Regel:

> Eine externe Quelle trägt, wenn sie je **Institut** eine Aussage macht und über
> LEI oder Katalog-Metadaten verknüpfbar ist. Quellen mit Auflösung je Land oder
> je Monat erzeugen Scheinpräzision, weil unsere effektive Beobachtungszahl auf
> die Zahl der Länder bzw. Stichtage zusammenfällt.

Und: **erst die Trefferquote messen, dann die Analyse planen.** GLEIF-Parents
28 %, Wikidata 65 %, ISINs 70 %, DISDOCS 87 % — diese Zahlen entscheiden, ob eine
Idee ein Produkt oder eine Anekdote wird.
