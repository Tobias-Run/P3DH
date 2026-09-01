# Viewer: was zu einem modernen Analytics-Produkt fehlt

Bestandsaufnahme am gerenderten Ist-Zustand (Chromium, 1600×950, Voll-Load mit
882 Reports), nicht am Quelltext. Screenshots von Benchmark- und Report-Ansicht.

**Die unbequeme Vorbemerkung:** Was den Viewer heute von einem
State-of-the-art-Analytics-Tool trennt, ist überwiegend **nicht** die Optik.
Abgerundete Ecken, Farbverläufe und eine modernere Schrift würden ihn hübscher
machen und an keiner einzigen der fünf Stellen unten helfen. Die Reihenfolge
unten ist deshalb nach Wirkung sortiert, nicht nach Sichtbarkeit — die
Gestaltungsfragen kommen als R6, und sie kommen zuletzt, weil sie auf den
anderen aufbauen.

Was heute schon gut ist und erhalten bleiben muss: hohe Informationsdichte
(eine echte Analytics-Tugend, nicht ein Mangel), der prominente
Vergleichbarkeits-Caveat, Dark Mode, Ladezeit durch Lazy-Shards, und die
Zeitreihe mit Sparklines.

---

## R1. Die Navigation denkt in Reports, der Nutzer denkt in Instituten ⭐ größter Hebel

**Befund.** In der Seitenleiste steht dasselbe Institut mehrfach untereinander:

```
AB Artea bankas   Large   Lithuania · Consolidated · 2025-12-31 · 82 templates
AB Artea bankas   Large   Lithuania · Consolidated · 2026-03-31 ·  6 templates
ABN AMRO Bank N.V. Large  Netherlands · Consolidated · 2025-06-30 · 88 templates
ABN AMRO Bank N.V. Large  Netherlands · Consolidated · 2025-09-30 · 16 templates
ABN AMRO Bank N.V. Large  Netherlands · Consolidated · 2025-12-31 · 112 templates
```

Nach dem Voll-Load hat sich das verschärft: 882 Reports für 474 Institute, und
116 Entitäten haben drei oder mehr Stichtage. Die Liste ist damit fast doppelt
so lang wie die Zahl der Dinge, nach denen jemand sucht.

**Warum das mehr ist als Kosmetik.** Kein Analyst denkt „ich suche den
ABN-AMRO-Report vom 30.09." — er denkt „ich suche ABN AMRO". Der Stichtag ist
eine *Eigenschaft* des Instituts, keine eigene Entität. Die aktuelle Struktur
zwingt den Nutzer, die Datenmodellierung der Pipeline mitzudenken.

**Richtung:** Ein Eintrag je (Institut, Konsolidierungskreis), Stichtage als
Umschalter *innerhalb* des Eintrags. Das halbiert die Liste, macht die
Zeitdimension sichtbar statt implizit, und ist die Voraussetzung dafür, dass
der Bruch aus #26 überhaupt darstellbar wird.

## R2. Der Report hat keine Zusammenfassung — er hat 136 Tabellen

**Befund.** Nach der KM1-Zeitreihe und dem Coverage-Block folgt bei BNP Paribas
sofort:

```
01.00.A — EU CAE1 – Exposures to crypto-assets
  Row 0040  4. Total  |  0020 b. Risk weighted exposures amounts (RWEA)  |  –
02.00 — EU CCR1 – Analysis of CCR exposure by approach
  überwiegend „–"
```

Das Erste, was ein Leser nach dem Einstieg sieht, ist eine **fast leere Tabelle
über Krypto-Exposure**, alphabetisch an erster Stelle. Danach 135 weitere,
gleichrangig, in Codereihenfolge.

**Das ist genau die EDAP-Erfahrung, von der wir uns abgrenzen wollten**
(`mehrwert_vs_edap.md`: „unsere Stärke ist die kuratierte, urteilende Sicht —
nicht die vollständige"). Der Viewer rendert vollständig und kuratiert nicht.

**Richtung:** Progressive Offenlegung in drei Ebenen —
1. **Überblick**: 5–8 Kennzahlen, die für dieses Institut zählen, mit
   Peer-Einordnung (das ist #23), plus die Qualitätssignale aus #17/#31.
2. **Themenblöcke**: Kapital, Kredit, Markt, Liquidität, ESG, Vergütung —
   eingeklappt, mit Füllstandsanzeige.
3. **Rohtabellen**: auf Klick, unverändert. Sie bleiben, sie führen nur nicht.

Alphabetische Codereihenfolge ist eine Sortierung, keine Struktur.

## R3. Die Rangliste führt mit unplausiblen Werten

**Befund.** Der Benchmark-Tab öffnet mit:

```
Kommuninvest - Grupp   2025-09-30   CET1 387,6 %   T1 387,6 %   TotalCap 387,6 %
Kommuninvest - Grupp   2026-03-31   372,9 %
Kommuninvest - Grupp   2025-12-31   355,2 %
Kommuninvest - Grupp   2025-06-30   352,7 %
```

Vier Zeilen desselben Instituts mit CET1-Quoten um 370 %. Das mag für eine
schwedische Kommunalfinanzierungsagentur sogar stimmen — aber als *erster
Eindruck* einer Rangliste ist es ein Glaubwürdigkeitsproblem: der Nutzer denkt
„die Daten sind kaputt", bevor er irgendetwas anderes sieht.

**Das Bittere daran:** Wir haben die Daten, um das einzuordnen, und nutzen sie
nicht. `processed/quality_profile.csv` (#17) kennt 5.969 Befunde in 326
Reports; R1 würde die vier Zeilen zu einer zusammenfassen.

**Richtung:** Ausreißer nicht verstecken (das wäre Verfälschung), sondern
**markieren und einordnen** — ein Hinweis an der Zeile, ein Umschalter
„Sonderfälle einklappen", und eine Verteilungsansicht, in der ein Wert bei
370 % sichtbar am Rand liegt statt an der Spitze. Das ist die Oberflächenseite
von #17 und deckt sich mit #24.

## R4. Zahlen ohne visuelle Kodierung

**Befund.** Die Benchmark-Tabelle ist eine reine Zahlentabelle. Die einzige
Grafik ist die Trend-Sparkline ganz rechts. Ein Leser muss 15 Prozentwerte
lesen und im Kopf vergleichen.

Moderne Analytics-Werkzeuge kodieren *im* Feld: Balken hinter der Zahl,
Farbskala nach Perzentil, Verteilungsstreifen mit Positionsmarke. Das ist keine
Dekoration — es verschiebt Vergleichen von Lesen zu Sehen.

**Richtung:** In-Zellen-Balken für Größenspalten, Perzentil-Position für
Quotenspalten (speist sich aus derselben Statistik wie #23), und eine
Verteilungsspalte, die zeigt, wo das Institut in der Peer-Gruppe liegt. Farbe
sparsam und nur mit Bedeutung; nie Rot/Grün als Wertung — es sind
Offenlegungsdaten, keine Bewertung.

## R5. Keine Arbeitsflächen — nur Ansichten

**Befund.** Der Viewer kennt Filtern und Sortieren. Was ein Enterprise-Werkzeug
zusätzlich kann und hier fehlt:

- **Auswahl mehrerer Institute** und deren Vergleich (der „Vergleich"-Tab
  existiert, ist aber nicht aus der Liste heraus bedienbar)
- **Spaltenauswahl** — 8 feste Spalten je Profil, nicht konfigurierbar
- **Export** der aktuellen Ansicht (CSV/PNG); heute führt jeder Weg zurück zum
  Parquet
- **Teilbarer Zustand** — der URL-Hash trägt Report und Tab, aber nicht Filter,
  Sortierung und Auswahl. Ein Kollege kann keinen Blick weitergeben.
- **Gespeicherte Sichten** (localStorage reicht)

Das Teilbare ist der wichtigste Punkt: ein Analysewerkzeug, dessen Zustand sich
nicht verlinken lässt, erzeugt Screenshots statt Zusammenarbeit.

## R6. Und jetzt die Optik

Erst hier, und bewusst zuletzt. Der Ist-Zustand wirkt aus vier konkreten
Gründen älter, als er ist:

**Kopfzeile.** Kräftiges Vollton-Blau (`--thead: #0b3d91`) über die volle
Breite, darin Titel, zwei Status-Pillen, drei Tabs und vier Buttons — acht
konkurrierende Elemente. Moderne Werkzeuge halten den Kopf ruhig und neutral
und geben die Farbe an die Daten ab.

**Typografie.** Eine einzige Größe (13 px) trägt fast die gesamte Oberfläche;
Hierarchie entsteht nur über Fettung. Es fehlt eine Skala (z. B. 11/13/15/20/28)
und ein zweites Gewicht. Zahlenspalten haben `tabular-nums` — gut —, aber
Beschriftungen und Werte haben dieselbe optische Wertigkeit.

**Dichte.** Tabellenzeilen sind eng ohne Rhythmus; Abschnitte haben kaum
Weißraum zueinander. Dichte ist richtig, aber sie braucht Gliederung, sonst
liest sie sich als Wand.

**Flächen.** Alles sitzt auf einer Ebene, Trennung nur über 1-px-Linien. Ein
System aus zwei bis drei Flächenebenen (Hintergrund / Karte / erhöht) mit
minimalen Schatten schafft Ordnung ohne zusätzliche Farbe.

**Konkret vorschlagbar:**

```
Farbe      Kopf neutral (Grau statt Blau), Blau nur als Akzent
           Semantik: nur die drei Coverage-Zustände + Qualitätshinweis
Typo       Skala 11/13/15/20/28 px, Gewichte 400/500/600
           Zahlen tabular-nums (vorhanden), Labels eine Stufe leiser
Raum       4-px-Raster; Sektionsabstand 24, Tabellenzeile 32 px
Flächen    --bg / --card / --raised, Schatten max. 1 Stufe
Bewegung   nur Zustandswechsel, 120–160 ms; keine Einblend-Effekte
```

Barrierefreiheit gehört dazu und ist heute nicht geprüft: Kontrastverhältnisse,
Fokus-Sichtbarkeit bei Tastaturbedienung, und die Frage, ob die
Coverage-Symbole (⊘ ∅ ⚠) ohne Farbe verständlich bleiben.

---

## Reihenfolge

| | | Aufwand | Wirkung |
|---|---|---|---|
| R1 | Institutszentrische Navigation | mittel | hoch — betrifft jeden Einstieg |
| R2 | Überblick + Themenblöcke | hoch | hoch — löst das „136 Tabellen"-Problem |
| R3 | Ausreißer einordnen statt anführen | klein | hoch — Glaubwürdigkeit |
| R4 | Visuelle Kodierung in Tabellen | mittel | mittel |
| R5 | Teilbarer Zustand, Auswahl, Export | mittel | mittel |
| R6 | Gestaltungssystem | mittel | mittel — wirkt erst mit R1–R3 |

**R3 zuerst**, wenn schnell etwas Sichtbares her soll: kleiner Eingriff, und er
behebt den schlechtesten ersten Eindruck, den das Produkt heute macht.

## Was wir nicht tun sollten

Ein Dashboard-Framework einziehen (React, Tailwind-Build, Charting-Library).
Der Viewer ist heute **eine HTML-Datei ohne Build-Schritt**, die aus statischen
JSON-Shards lädt und über jsDelivr ausgeliefert werden kann. Das ist ein
Architekturvorteil, kein Rückstand — er macht das Produkt hostbar, versionierbar
und in fünf Jahren noch lauffähig. Alles oben ist ohne Build-Kette erreichbar.
