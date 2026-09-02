# Offene empirische Fragen in der Literatur — und was unser Bestand dazu kann

Recherchestand 2026-09-01. Ausgangspunkt ist nicht „welche Analyse wäre schön",
sondern: **welche Frage ist in der Literatur offen, weil bisher die Daten
fehlten — und fehlen sie uns noch?**

Jede Einschätzung unten ist gegen den eigenen Bestand geprüft (882 Reports, 474
Institute, 31 Länder, 2,3 Mio. Fakten, 5 Stichtage).

---

## Der methodische Kern: warum diese Literatur datenarm ist

Die systematische Übersicht von Nobanee et al. (2024, *International Review of
Financial Analysis*) über zwanzig Jahre empirischer Forschung zur
Risikooffenlegung von Banken nennt drei Befunde, die zusammen das Bild ergeben:

1. Die Studien sind **überwiegend deskriptiv** mit begrenztem theoretischem
   Ertrag.
2. Sie konzentrieren sich auf **wenige entwickelte Länder**; vergleichende
   Länderstudien bleiben selten.
3. Die Forderung lautet, auf **unterrepräsentierte Settings** auszuweichen und
   die Methodik zu diversifizieren.

Der Grund dafür steckt in der Datenlage, nicht im Erkenntnisinteresse: Pillar-3-
Berichte waren bis 2026 **statische PDFs** — lang, uneinheitlich, schwer
auffindbar, ohne vergleichbare Struktur (so auch die Einschätzung von XBRL
International). Wer sie auswerten wollte, musste sie von Hand kodieren. Das
begrenzt jede Stichprobe auf einige Dutzend Institute und meist ein Land.

**Genau diese Beschränkung fällt mit dem P3DH weg** — und unser Bestand ist
derzeit die einzige uns bekannte maschinenlesbare Aufbereitung über die volle
Population. Die drei genannten Lücken sind damit keine Methodenfragen mehr,
sondern Verfügbarkeitsfragen, die beantwortet sind.

Wichtig für die Selbsteinschätzung: **wir sind keine Forschungsgruppe.** Der
sinnvolle Beitrag ist, den Datensatz so aufzubereiten und zu dokumentieren, dass
diese Fragen bearbeitbar werden — nicht, die Papers selbst zu schreiben.
Das spricht direkt für #20 (dokumentiertes Release).

---

## F1. Strategische Auslassung nach CRR Art. 432 ⭐ die klarste Lücke — Issue #43

**Der Regelungsrahmen.** Art. 432 erlaubt Instituten, Angaben wegzulassen, die
nicht *wesentlich* sind, sowie solche, die *proprietär oder vertraulich* sind —
Letzteres definiert als „würde die Wettbewerbsposition untergraben". Die EBA hat
dazu eigene Leitlinien erlassen, weil die Ermessensausübung uneinheitlich war.

**Der Befund der Recherche:** Zu diesem Ermessensspielraum finden sich
Regulierungstexte, Konsultationen und Leitlinien — **aber keine empirische
Studie**, die misst, wie er tatsächlich ausgeübt wird. Das ist bemerkenswert für
eine Vorschrift, die seit über einem Jahrzehnt in Kraft ist.

**Warum bisher niemand:** Man bräuchte für jede Bank die Aussage, *welche*
Angaben sie weglässt — nicht nur, was in ihrem Bericht steht. Aus einem PDF ist
das nicht rekonstruierbar: eine fehlende Tabelle kann Auslassung, Nichtanwendbarkeit
oder ein Layoutproblem sein.

**Was wir haben:** `processed/filing_indicators.csv`, **64.898 Zeilen** — die
Erklärung der Institute selbst, Template für Template, ob offengelegt wurde.
23.525 mal „ja", 41.373 mal „nein". Das ist keine Näherung und kein Index,
sondern die Aussage des Melders.

Damit werden erstmals messbar: Streuung der Auslassungsquote über Institute und
Länder, systematische Muster (welche Templates werden bevorzugt weggelassen?),
und — mit #34 — ob eine Auslassung dauerhaft ist oder wechselt.

**Anschluss im Backlog:** #21 (Sichtbarkeit im Viewer), #34 (Zeitdimension).

## F2. Wirkt die Proportionalität — und wie stark? ⭐ — Issue #44

**Die offene Frage.** Die CRD-V-Reform schuf für „kleine und nicht komplexe
Institute" erleichterte Offenlegungspflichten (Art. 433b: nur jährlich, für
nicht börsennotierte nur Schlüsselkennzahlen und ESG). Die politische Debatte um
die richtige Dosis läuft weiter — „small banking box", „soft landing",
Diskussionen nach dem Fall der Silicon Valley Bank. Was in dieser Debatte fehlt,
ist die schlichte Messung: **wie viel weniger legen erleichterte Institute
tatsächlich offen?**

**Was wir haben:** `entity_meta.csv` trägt die EBA-Klasse je Institut —

```
Large highest EEA     139 Institute
Other highest EEA     229
Large subsidiaries    103
```

kombiniert mit der Coverage-Matrix aus F1 und der Faktendichte je Report. Der
Geschäftsmodell-Befund aus `phase4_analysis_ideas.md` (4 bis 45 gemeldete
Templates je Institut) zeigt, dass die Spannweite real und groß ist.

Die Frage lässt sich damit direkt beantworten — deskriptiv, ohne
Kausalitätsanspruch, aber erstmals über die volle Population statt über eine
Handstichprobe.

**Caveat:** Die EBA-Klasse ist nicht deckungsgleich mit „klein und nicht
komplex" nach Art. 4(1)(145) CRR. Vor jeder Aussage ist die Abbildung zu
prüfen; sonst misst man die falsche Klasse.

## F3. RWA-Variabilität — der unerklärte Rest — Issue #45

**Stand der Forschung.** Die Streuung der Risikogewichte zwischen Banken ist
eines der meistuntersuchten Themen der Bankenregulierung; sie war der Anlass für
den Output-Floor von Basel IV (72,5 %, Einführung 2025 bis 2030). Die EBA
kommt in ihrer eigenen Benchmarking-Übung zu dem Schluss, dass sich der
**Großteil der Variabilität durch Fundamentaldaten erklären lässt** — rund 60 %
allein über Ausfallanteil und Portfoliomix.

**Was offen bleibt:** die restlichen ~40 %. Und eine methodische Einschränkung:
die EBA-Benchmarking-Übung deckt **IRB-Institute** ab und wird nicht auf
Institutsebene veröffentlicht.

**Was wir haben:** RWA-Dichte ist aus KM1 direkt rechenbar — TREA (`61.00`
r0040) geteilt durch die Gesamtrisikopositionsmessgröße der Leverage Ratio
(`61.00` r0210), verfügbar für 434 Institute:

```
Median 0,376   p10 0,231   p90 0,579
```

Eine Spannweite von Faktor 2,5 zwischen dem 10. und 90. Perzentil. Dazu kommen
der Risikomix aus OV1 (`60.00.A`, im Benchmark bereits als Profil verdrahtet)
und die PD-Bänder aus CR6 (`26.00.A`).

**Unser möglicher Beitrag ist nicht das bessere Modell**, sondern die breitere
Grundgesamtheit: eine deskriptive Zerlegung der RWA-Dichte über *alle* Melder,
inklusive Standardansatz-Instituten und kleiner Häuser, die in der
EBA-Übung nicht vorkommen — und auf Institutsebene nachvollziehbar.

**Caveat:** `26.00.A` ist genau das Template, in dem #17 die PD-Skalierungsfehler
gefunden hat (DNB meldet 100.000.000 statt 1,0; populationsweit 228 PD-Zellen
über 100 %). Ohne den Plausibilitätsfilter aus #17 wäre jede Auswertung dieser
Zellen wertlos — hier zahlt sich die Vorarbeit unmittelbar aus.

## F4. Marktdisziplin — die Kernfrage, die wir nur halb bedienen können — Issue #39

**Stand der Forschung: gemischt.** Es gibt Belege für positive Wirkung
(Offenlegung → höhere Kapitalpuffer; Risikooffenlegungsindex negativ korreliert
mit Risikoübernahme). Es gibt ebenso Befunde, dass das Pillar-3-Rahmenwerk sein
Ziel *nicht* erreicht und das Interesse der Adressaten selbst in Krisenzeiten
gering ist — eine Studie hat dafür sogar die Webzugriffe auf Pillar-3-Berichte
ausgewertet.

**Was wir beitragen können:** den Ereignisdatensatz. Wir besitzen den
Einreichungszeitpunkt auf die Sekunde über 4.278 Einreichungen — die Grundlage
für die Ereignisstudie in #39.

**Was uns fehlt:** Marktdaten. Das ist keine Fleißfrage, sondern eine
Lizenzfrage, und sie ist in #39 als Blockade benannt. Ohne sie können wir die
Frage vorbereiten, aber nicht beantworten.

## F5. Rechtzeitigkeit als eigene Dimension — Issue #33

In der gesichteten Literatur kommt **Zeit** fast nur als Berichtsjahr vor, nicht
als Verzögerung. Das liegt daran, dass ein PDF auf einer Bankwebsite kein
verlässliches Veröffentlichungsdatum trägt.

Der P3DH ändert das: der Katalog trägt `submission_ts`. Unsere Messung (#33) —
Median 252 Tage für 2025-06-30, 59 Tage für 2026-03-31 — zeigt einen
Regimewechsel, der mit dem Start des Hubs zusammenfällt.

**Das ist ein Naturexperiment.** Die Umstellung von dezentraler
Website-Veröffentlichung auf zentrale Einreichung ist eine exogene Änderung der
Offenlegungsinfrastruktur, und wir beobachten Institute davor und danach. Ob
sich daraus mehr als eine Deskription machen lässt, hängt an der Zahl der
Stichtage — mit fünf ist es zu früh, mit jeder weiteren Welle (#7) wird es
tragfähiger.

---

## Was unser Bestand *nicht* leistet

Ehrlichkeit an dieser Stelle entscheidet über die Glaubwürdigkeit des Rests:

- **Kein Panel im ökonometrischen Sinn.** 266 von 474 Entitäten haben genau
  einen Stichtag; 116 haben drei oder mehr. Für Fixed-Effects-Schätzungen ist
  das dünn. Deskription und Querschnitt tragen, dynamische Panelmodelle nicht.
- **Kein kausaler Identifikationsrahmen.** Wir haben keine exogene Variation in
  der Offenlegungspflicht — außer möglicherweise dem Hub-Start (F5).
- **Keine Bilanzdaten.** Wir sehen Offenlegung, nicht das aufsichtliche
  Meldewesen (COREP/FINREP). Wer Profitabilität, Refinanzierungskosten oder
  Bilanzstruktur braucht, muss extern verknüpfen — mit den Trefferquoten-
  Problemen aus `analysen_nach_vollload.md`.
- **Die Population ist nicht die EU-Bankenlandschaft.** Wer im Hub fehlt, fehlt
  auch bei uns; das ist genau die Frage in #42.

## Wo der Beitrag realistisch liegt

Nicht in einem eigenen Paper, sondern in **drei Vorleistungen**, die die
Bearbeitbarkeit dieser Fragen überhaupt erst herstellen:

1. **#20 — dokumentiertes Datensatz-Release.** Der größte Hebel. Die Literatur
   ist datenarm, weil das Aufbereiten teuer war; wir haben es getan.
2. **#17 + #36 — Plausibilitätsfilter.** Ohne sie ist F3 nicht rechenbar
   (PD-Skalierungsfehler) und jede Rangliste verzerrt.
3. **#32 — Konzerngraph.** Ohne ihn ist keine Aussage über die *Population*
   zulässig, weil Konzerne mehrfach zählen.

Die inhaltlich reizvollsten Fragen (F1, F2) sind zugleich die, die am wenigsten
zusätzliche Infrastruktur brauchen — beide sind mit dem heutigen Bestand
rechenbar.

## Quellen

- Nobanee et al. (2024): *Empirical research on banks' risk disclosure:
  Systematic literature review, bibliometric analysis and future research
  agenda*, International Review of Financial Analysis —
  https://www.sciencedirect.com/science/article/pii/S1057521924002898
- *Pillar 3: Does banking regulation support stakeholders' interest in banks
  financial and risk profile?*, PLOS One —
  https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0258449
- *Web usage analysis of Pillar 3 disclosed information by deposit customers in
  turbulent times*, Expert Systems with Applications —
  https://www.sciencedirect.com/science/article/pii/S0957417421009131
- EBA: *Assessment of Pillar 3 disclosures* —
  https://www.eba.europa.eu/sites/default/files/documents/10180/16166/7912edb8-6d57-4434-80c7-b9d610b8be2f/Assessment-of-Pillar-3-disclosures.pdf
- EBA: *Report on the 2025 credit risk benchmarking exercise* —
  https://www.eba.europa.eu/sites/default/files/2026-06/addc87e5-36b9-4eb5-bba7-d5168aa19819/EBA%20Report%20results%20from%20the%202025%20credit%20risk%20benchmarking%20exercise.pdf
- EBA: Leitlinien zu Wesentlichkeit, Proprietät und Vertraulichkeit (Art. 432) —
  https://www.eba.europa.eu/regulation-and-policy/single-rulebook/interactive-single-rulebook/15888
- XBRL International: *Pillar 3 Disclosures Need Further Improvement* —
  https://www.xbrl.org/news/pillar-3-disclosures-need-further-improvement/
- BCBS: *Pillar 3 — Market Discipline* (Working Paper 7) —
  https://bis.org/publ/bcbs_wp7.htm

**Zugriffshinweis:** ScienceDirect ist über den Egress-Proxy dieser Session
gesperrt; die dortigen Arbeiten sind über Suchergebnis-Zusammenfassungen
eingeflossen, nicht über den Volltext. Wer die Argumentation zu F1 und F3
belastbar machen will, sollte die Volltexte prüfen — insbesondere, ob zu Art. 432
doch eine empirische Arbeit existiert, die die Suche nicht gefunden hat.
