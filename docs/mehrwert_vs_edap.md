# Mehrwert gegenüber dem offiziellen EBA Pillar 3 Data Hub

**Der Unterschied ist nicht der Zugang. Es ist das Urteil.**

EDAP muss zeigen, was eingereicht wurde — auch wenn es falsch ist. Das ist
keine Schwäche, sondern die Aufgabe eines Renderers, und er erfüllt sie
kompetent. Wir haben diese Pflicht nicht. Genau darin liegt der einzige
Beitrag, den wir mit Aussicht auf Erfolg leisten können: an eine Zahl zu
schreiben, dass sie gegen die Population nicht plausibel ist.

Wer stattdessen auf besseren Zugang oder schönere Darstellung setzt, tritt
gegen ein gut finanziertes Portal an — auf dessen eigenem Feld. Das wäre weder
nötig noch zu gewinnen.

**Stand:** 2026-09-04. Datengeerdet — jede Idee unten ist gegen den tatsächlichen
Bestand geprüft (882 Reports, 2,30 Mio. platzierte Fakten, 474 Institute), nicht
aus der Fachliteratur abgeleitet. Prototypen-Zahlen stammen aus echten Abfragen;
ältere Zahlen im Fließtext sind als solche erkennbar und bewusst stehen geblieben,
wo sie eine damalige Beobachtung belegen.

## ⚠️ Korrektur (2026-08-28): EDAP kann mehr, als hier zuerst stand

Die erste Fassung dieses Dokuments beschrieb EDAP als „Archiv mit Suchmaske:
ein Institut, ein Stichtag, ein ZIP". **Das war falsch** und stützte sich auf
Recherche vom Projektstart, vor dem Live-Gang des Hubs am 26.01.2026.

Laut EBA bietet EDAP tatsächlich:
- **Template Rendering Report** — Darstellung im ITS-Template-Layout
- **Data Point Report** — Filter auf Zeilen/Spalten, Vergleich einzelner
  Datenpunkte *innerhalb* eines Instituts, **über Institute hinweg** und
  **auf aggregierter Ebene mit verschiedenen Aggregationsstufen**
- Filter nach Institut, Land, Stichtag, Report-Typ
- **Bulk-Download** sowie Export der gefilterten Sicht
- Download der Original-Einreichungen (PDF und XBRL-CSV)

Damit sind drei Behauptungen der ersten Fassung hinfällig: EDAP *kann*
Institute vergleichen, *kann* aggregieren und *bietet* Bulk-Zugang. Die
ursprüngliche „EDAP kann nicht"-Tabelle ist ersatzlos gestrichen.

## Wo der Mehrwert wirklich liegt

Die richtige Abgrenzung ist nicht Zugang oder Slicing, sondern:

> **EDAP ist ein originalgetreuer Renderer. Wir sind eine interpretierende
> Schicht.** Ein Renderer muss zeigen, was eingereicht wurde — auch wenn es
> falsch ist. Er darf nicht urteilen. Genau dort entsteht unser Beitrag.

Fünf Dinge, die ein originalgetreues Anzeige-Werkzeug **kategorisch nicht
leisten kann**, weil sie ein Urteil gegen die Population erfordern:

| Wir | warum ein Renderer das nicht kann |
|---|---|
| **Implausible Meldungen markieren** | Er muss anzeigen, was gemeldet wurde. „11,7 Bio. EUR Vorstandsvergütung für 9 Personen" ist originalgetreu — und unbrauchbar. Ein Plausibilitätsurteil braucht die Population als Maßstab (→ #17). |
| **Framework-Versionen semantisch brücken** | Inzwischen **63** Zellen wurden zwischen RF 4.1 und 4.2 auf neue dp-Codes umgebunden (u. a. KM1-Leverage-Puffer, 30 allein in PV1), dazu 125 mehrdeutige. Wer über dp-Code vergleicht, bekommt einen stillen Bruch — belegt in `phase3_framework_bridge.md`. 103 von 475 Instituten melden inzwischen beiderseits des Bruchs. |
| **Abgeleitete Kennzahlen über Templates** | Pivot-/Filterwerkzeuge aggregieren *dieselbe* Größe. NPL-Deckungsquote, Vergütung pro Kopf, Forbearance-Quote haben Zähler und Nenner in **verschiedenen Templates mit verschiedenen Bezugsgrößen**. |
| **Peer-Gruppen als fachliches Urteil** | „Vergleichbar" ist keine Filteroption. Unsere Perzentile sind nach Größenklasse × Konsolidierung × Stichtag geschichtet — sonst steht die Exportkreditagentur neben der Dorfsparkasse. |
| **Fallen in der Datenstruktur entschärfen** | `eba_GA:x1` ist die Summenzeile „Total". Ein Renderer zeigt sie korrekt als Zeile; wer sie mitsummiert, verdoppelt das Exposure. Wir kennzeichnen sie (belegt an 89 von 96 Instituten). |

Dazu zwei praktische Vorteile, die kein Urteil erfordern, aber real sind:
**freie Abfragbarkeit** (SQL über die Population statt vorgedachter Klickpfade)
und **Reproduzierbarkeit** (versionierter, zitierfähiger Stand statt „was der
Viewer heute zeigt") — letzteres ist für Forschung der eigentliche Knackpunkt.

**Was wir dagegen nicht behaupten sollten:** dass wir besseren *Zugang* oder
schönere *Darstellung* bieten. Beides macht EDAP kompetent, und dort zu
konkurrieren wäre weder nötig noch gewinnbar.

---

## Was im Bestand liegt und ungenutzt ist

Der Benchmark zieht aus **4 Templates**. Breit gemeldet, aber nirgends genutzt:

| Template | Reports | Inhalt |
|---|---|---|
| `21.01.A–F` | bis 420 | **CR1** — Kreditqualität in voller Tiefe |
| `80.00.A–E` | bis 383 | **CQ1** — forborne (gestundete) Kredite |
| `66.01.A` | 428 | **CC1** — Eigenmittel-Zusammensetzung |
| `30.01` | 351 | **REM1** — Vergütung |
| `73.00.C/D/E` | bis 323 | **LIQ1** — LCR-Detailstruktur |
| Modul `010000` | 475 | **IRRBB** — Zinsschock-Szenarien (→ #15) |

---

## A. Kreditverschlechterungs-Kette ⭐ stärkster Kandidat

**Die Idee:** Kreditrisiko ist keine Zustandsgröße, sondern eine Kette:
`performing → forborne (gestundet) → non-performing → ausgefallen`.
Jede Stufe steht in einem *anderen* Template, mit unterschiedlichen
Bezugsgrößen. Ein Pivot-/Filterwerkzeug aggregiert dieselbe Größe über
Dimensionen — es bildet keine Quotienten aus zwei Templates. Diese Kennzahl
entsteht erst durch einen Join, den man definieren muss.

**Prototyp gerechnet** (2025-12-31, Zeile „Loans and advances"):
**340 Institute** lassen sich über CQ3 (`82.00.A`) und CQ1 (`80.00.A`) verknüpfen.

- Median NPL-Quote: **2,36 %**
- Median „performing forborne"-Quote: **0,63 %** ← die Vorstufe *vor* dem Ausfall

Interessant wird die **Diskrepanz** zwischen beiden. Institute mit niedriger
NPL-Quote, aber hoher Vorstufe, haben ein Problem, das in der NPL-Zahl noch
nicht sichtbar ist:

| Institut | Land | NPL | Vorstufe |
|---|---|---|---|
| IKB Deutsche Industriebank | DE | 2,20 % | **4,76 %** |
| Aktia Bank Abp | FI | 2,36 % | 3,65 % |
| OP Osuuskunta | FI | 2,28 % | 2,88 % |
| Bank Handlowy w Warszawie | PL | 1,12 % | **2,64 %** |

IKB trägt mehr als das Doppelte seiner NPL-Quote in der Vorstufe. Das ist ein
echtes Frühwarnsignal — und es existiert in **keiner** offiziellen Darstellung,
weil es zwei Templates und die Population braucht.

**Ausbau:** ergänzt um CR1 (`21.01.D`, Wertberichtigungen) ergibt sich zusätzlich
die **NPL-Deckungsquote** (Provisions / NPE) — die klassische Aufsichtskennzahl,
die ebenfalls nirgends fertig vorliegt.

---

## B. Datenqualität als eigenes Produkt ⭐ originellste Achse

Wir haben in drei Tagen vier belegte Datenfehler in offiziellen Meldungen
gefunden — nicht in unserer Pipeline, sondern **in den Einreichungen selbst**:

1. **Gemischte Einheiten** (#9): Template `41.00`/`45.00.A`, Spaltenlabel sagt
   „Mln EUR", die Masse meldet in Währungseinheiten. Streuung `10^2`–`10^12`.
2. **`eba_GA:x1` ist die Summenzeile**, kein Land — wer sie mitsummiert,
   verdoppelt das Exposure (belegt an 89 von 96 Instituten).
3. **`x28`-Residualbucket** wird sehr unterschiedlich befüllt: Banco BPM legt
   101,4 Mrd dorthin gegen 0,9 Mrd im größten benannten Land.
4. **REM1 (`30.01`) streut über 14 Größenordnungen** — dazu unten mehr.

**Das Produkt:** ein **Plausibilitäts-/Qualitätsprofil je Institut**. Welche
Melder liefern Zahlen, die gegen die Population implausibel sind? Das ist
- für Analysten ein Filter („diesen Werten nicht trauen"),
- für die Institute selbst ein Hinweis,
- und eine Achse, die **niemand sonst anbietet**, weil sie die Population braucht.

Kein Werturteil über Institute, sondern ein reproduzierbarer Konsistenz-Check.

### ⚠️ Dabei aufgefallen: der #9-Scan hat einen blinden Fleck

Der Gap-Scan aus #9 sucht eine **saubere bimodale Lücke** (≥3 Größenordnungen,
≥3 Institute je Seite). REM1 `30.01` r0020/c0020 („Total fixed remuneration",
Vorstand) hat aber eine **verschmierte** Verteilung:

```
10^ 0: ############ 12          <- absurd klein (Werte 1, 3)
10^ 3: ##################### 21
10^ 5: ########################################## 42
10^ 6: ############################################# 188   <- plausibel
10^ 7: ###################################### 38
10^12: ## 2
10^13: # 1                       <- Rabobank: 11,7 Billionen EUR für 9 Personen
```

14 Größenordnungen, plausible Masse bei 10⁶ — und der Scan **flaggt die Zelle
nicht**, weil es keine einzelne scharfe Lücke gibt. Nötig ist ein zweites,
komplementäres Verfahren: **Plausibilitätsgrenzen auf abgeleiteten Verhältnissen**
(hier: Vergütung pro Kopf muss in einem sinnvollen Korridor liegen). Ratio-Checks
sind robuster als Verteilungsformen, weil sie fachliches Wissen einbringen.

---

## C. Vergütung (REM1) — umgesetzt (2026-09)

`30.01` liefert **Anzahl identified staff** *und* **fixe/variable Vergütung**,
getrennt nach Aufsichtsrat / Vorstand / Senior Management / übrige Risk-Taker —
für **~350 Institute**. Daraus wären unmittelbar ableitbar:
- Vergütung **pro Kopf** je Funktionsstufe
- **Variabel/Fix-Verhältnis** (Bonuskultur, aufsichtlich gedeckelt)
- Vergleich über Länder und Größenklassen

Das ist die öffentlich meistbeachtete Kennzahl im ganzen Datensatz und im Viewer
bislang **gar nicht vorhanden**.

**Der Vorbehalt hat sich bestätigt und ist abgearbeitet.** Ungefiltert führte
Rabobank die Rangliste mit 1,3 Bio. EUR pro Kopf an. Das Profil „Vergütung
(REM1)" filtert deshalb über ein **Plausibilitäts-Tor**: fällt eine
Funktionsstufe eines Reports aus dem Korridor 1.000–20.000.000 EUR pro Kopf,
fliegt der ganze Report aus der Liste. Gemessen sind das 57 von 359 Reports
(15,9 %) — bei 35 von ihnen liegen alle vier Stufen daneben, es ist also eine
falsche Meldeeinheit für das ganze Template.

Zwei Dinge, die das Tor tragen:

- **Ein Korridor, nicht zwei.** `metrics.REM_PER_HEAD` ist die einzige
  Definition; `check_plausibility.RATIO_RULES` prüft den Bestand damit, der
  Viewer filtert die Liste damit. Sonst filterte die Rangliste nach anderen
  Grenzen als die, gegen die geprüft wurde — und niemand sähe es.
- **Der Ausschluss ist sichtbar.** Quote, Anzahl und die ausgeschlossenen
  Institute stehen unter der Tabelle, jeweils mit dem Wert, der den Ausschluss
  ausgelöst hat. Ein stiller Filter wäre eine unbelegte Behauptung über
  Institute.

Nach dem Filter führt Mediobanca mit 5,69 Mio. EUR fixer Vergütung pro
Vorstandsmitglied; der Median liegt bei 403.381 EUR.

---

## D. Länder-Aggregate über die Population — abgewertet

Aus CCyB1 (`67.01.A`, seit #5/#10 mit aufgelösten Ländern): „Wie viel
EU-Bankexposure trägt Land X insgesamt?", summiert über alle meldenden Institute.

**Nach der Korrektur oben deutlich schwächer:** EDAPs Data Point Report bietet
Aggregation über Institute mit verschiedenen Aggregationsstufen — die reine
Summenbildung ist damit kein Alleinstellungsmerkmal mehr.

Was bleibt, ist der **Fallen-Teil**: Wer in CCyB1 naiv über Länder summiert,
zählt `eba_GA:x1` (die Summenzeile „Total") mit und verdoppelt das Ergebnis.
Der Wert liegt also nicht im Aggregat selbst, sondern in einem Aggregat, dem
man trauen kann — plus Abdeckungsgrad-Ausweis und `x28`-Qualitätsflag. Das ist
eine Ergänzung zu #12, kein eigenständiges Produkt.

---

## E. Datensatz-Release — abgewertet

Die ursprüngliche Begründung („EDAP bietet ausschließlich Roh-ZIPs") ist
**hinfällig** — EDAP hat Bulk-Download und gefilterten Export.

Der verbleibende Unterschied ist schmaler, aber real: unser Parquet ist bereits
**gejoint und angereichert** (DPM-Labels, EUR-Normierung, Instituts-Metadaten,
aufgelöste Länder, Qualitätsflags) und vor allem **versioniert und zitierfähig**
— ein fixer Stand, auf den sich eine Auswertung berufen kann. Ein Live-Viewer
zeigt immer den aktuellen Stand; für reproduzierbare Forschung ist das ein
echtes Problem.

Bleibt sinnvoll, aber als **Nebenprodukt der Pipeline**, nicht als eigenes
Wertversprechen.

---

## Bewertung

| Idee | Issue | Wert | Aufwand | Blockiert durch |
|---|---|---|---|---|
| **A** Kreditverschlechterungs-Kette | [#16](https://github.com/Tobias-Run/P3DH/issues/16) | hoch | mittel | — (Prototyp läuft) |
| **B** Datenqualitäts-Profil | [#17](https://github.com/Tobias-Run/P3DH/issues/17) | hoch | mittel | — |
| **C** Vergütung | [#18](https://github.com/Tobias-Run/P3DH/issues/18) | hoch (öffentlich) | klein | ~~#17~~ **umgesetzt** |
| **D** Länder-Aggregate | [#19](https://github.com/Tobias-Run/P3DH/issues/19) | ~~mittel–hoch~~ **niedrig** | klein | #12 |
| **E** Datensatz-Release | [#20](https://github.com/Tobias-Run/P3DH/issues/20) | ~~mittel~~ **niedrig** | klein | — |

D und E nach der EDAP-Korrektur abgewertet: Aggregation und Bulk-Download bietet
EDAP selbst. Beide bleiben sinnvoll, aber als Beiwerk — nicht als Wertversprechen.

**Empfohlene Reihenfolge:** A (eigenständiger Erkenntniswert, sofort) →
B (schaltet C frei und härtet alles andere) → C → D/E.

**Bewusst nicht vorgeschlagen:** „Transparenz-/Offenlegungs-Score" (misst
Regulierungskategorie, nicht Verhalten — siehe `phase4_analysis_ideas.md`),
Makro-Korrelationen (zu wenig Freiheitsgrade — siehe #11/#14), PDF-NLP
(Ingestionspfad existiert nicht).

---

## F. Der Viewer als *interpretierende* Oberfläche (2026-08-28 ergänzt)

EDAP hat einen kompetenten Webviewer (Template Rendering + Data Point Report).
Ihn im Rendern schlagen zu wollen wäre aussichtslos und sinnlos. Der Unterschied
muss derselbe sein wie oben: **er zeigt die Zahl, wir zeigen die Zahl im Urteil.**

Konkrete Ansatzpunkte, jeweils gegen unseren Ist-Stand geprüft:

### F1. „Fehlt ≠ Null" sichtbar machen ⭐ eklatante eigene Lücke — Issue #21

`processed/filing_indicators.csv` hat **~41.000 Zeilen** Coverage-Matrix — und
kommt im Viewer **nirgends** an (0 Treffer für `filing_indicator`/`template_reported`
in `viewer_json.html` *und* `build_zweig_a_shards.py`). Das ist ausgerechnet das
**erklärte Kernprinzip des Projekts** (`README.md`, Arbeitsprinzip 3), im
Datenlayer sauber umgesetzt und im Produkt unsichtbar.

Drei Zustände sind zu unterscheiden und werden heute alle als leere Zelle gezeigt:
- **nicht offengelegt** (Filing-Indicator `false` → bewusste Auslassung)
- **gemeldete Null** (echter Wert 0)
- **strukturell nicht anwendbar** (Template gehört nicht zum Meldeumfang des
  Instituts — siehe Geschäftsmodell-Befund in `phase4_analysis_ideas.md`)

Das ist die billigste große Verbesserung im ganzen Backlog: Daten liegen fertig,
es fehlt nur der Weg in die Shards und drei Zellzustände im Grid.

### F2. Zahl im Kontext statt Zahl allein ⭐ größter UX-Hebel — Issue #23

Ein Renderer zeigt `12,4 %`. Ein interpretierender Viewer zeigt `12,4 %` **und**
dass der Peer-Median 15,1 % ist und das Institut im 23. Perzentil liegt. Wir haben
die Perzentil-Logik bereits (geschichtet, `#4`) — aber nur im Benchmark-Tab, nicht
an der einzelnen Zelle im Report.

Für Nicht-Spezialisten ist das der Unterschied zwischen „eine Zahl" und „eine
Aussage". Technisch: Tooltip/Sekundärzeile je Zelle, gespeist aus den ohnehin
berechneten Peer-Statistiken.

### F3. Anomalien inline markieren — Issue #24

Sobald #17 steht: implausible Werte im Grid kennzeichnen statt sie wie normale
Zahlen zu rendern. EDAP *muss* „11,7 Bio. EUR" originalgetreu anzeigen — wir
dürfen dazuschreiben, dass der Wert um sechs Größenordnungen über dem Peer-Median
liegt. Hängt an #17.

### F4. Benannte Kennzahlen statt Zellkoordinaten — Issue #25

Wer die NPL-Quote sucht, weiß nicht, dass sie aus `82.00.A` Zeile 0020 Spalten
`0010`/`0040` entsteht. Ein Suchfeld über *Kennzahlen* (nicht über Templates)
wäre ein echter Zugangsgewinn — und ist die Oberflächen-Seite von #16.

### F5. Framework-Bruch in der Zeitreihe markieren — Issue #26

Der Viewer zeigt `framework` heute nur als Textlabel im Report-Kopf
(`viewer_json.html:452`). Die Brücke (`framework_bridge.csv`, 19 umgebundene
Zellen) wird in der Oberfläche **nicht** genutzt. In einer Sparkline über den
4.1→4.2-Wechsel gehört an genau dieser Stelle eine Markierung hin — sonst wirkt
ein Sprung wie eine Geschäftsentwicklung, obwohl er eine Taxonomie-Änderung ist.

### F6. Ähnliche Institute vorschlagen — Issue #27

Statt Peer-Gruppen manuell zu filtern: „diese Institute haben ein ähnliches
Exposure-Profil" — die Oberflächen-Seite von #13.

### Was wir *nicht* versuchen sollten

Vollständigkeit im Template-Rendering (EDAP kann das per Definition besser, es
hat alle Daten), oder EDAPs Data Point Report nachbauen. Unsere Stärke ist die
kuratierte, urteilende Sicht — nicht die vollständige.
