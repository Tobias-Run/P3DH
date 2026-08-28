# Mehrwert gegenüber dem offiziellen EBA Pillar 3 Data Hub

**Stand:** 2026-08-28. Datengeerdet — jede Idee unten ist gegen den tatsächlichen
Bestand geprüft (553 Reports, 1,55 Mio. Fakten, 445 Institute), nicht aus der
Fachliteratur abgeleitet. Prototypen-Zahlen stammen aus echten Abfragen.

## Was EDAP ist — und wo die Lücke entsteht

EDAP ist ein **Archiv mit Suchmaske**: ein Institut, ein Stichtag, ein ZIP zum
Herunterladen. Das ist für den regulatorischen Zweck (Offenlegung zugänglich
machen) korrekt und ausreichend. Es bedeutet aber strukturell:

| EDAP kann nicht | weil |
|---|---|
| Institute vergleichen | jede Einreichung ist ein separates Paket |
| Kennzahlen über Templates hinweg bilden | Zähler und Nenner liegen in verschiedenen Dateien |
| Aggregate über die Population | kein Quer-Zugriff |
| Zeitreihen zeigen | Stichtage sind separate Pakete |
| Datenqualität bewerten | kein Vergleichsmaßstab ohne Population |

**Unser struktureller Vorteil ist nicht „schöner", sondern kategorisch:** Wir haben
die Population in *einer* abfragbaren Fläche (Parquet/DuckDB), mit aufgelösten
Labels, EUR-Normierung, Peer-Schichtung und Framework-Brücke. Alles unten folgt
aus genau dieser einen Eigenschaft.

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
Jede Stufe steht in einem *anderen* Template. EDAP kann sie prinzipiell nicht
verbinden — wir schon.

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

## C. Vergütung (REM1) — hohe öffentliche Relevanz, aber blockiert

`30.01` liefert **Anzahl identified staff** *und* **fixe/variable Vergütung**,
getrennt nach Aufsichtsrat / Vorstand / Senior Management / übrige Risk-Taker —
für **~350 Institute**. Daraus wären unmittelbar ableitbar:
- Vergütung **pro Kopf** je Funktionsstufe
- **Variabel/Fix-Verhältnis** (Bonuskultur, aufsichtlich gedeckelt)
- Vergleich über Länder und Größenklassen

Das ist die öffentlich meistbeachtete Kennzahl im ganzen Datensatz und im Viewer
bislang **gar nicht vorhanden**.

**Aber:** ohne den Einheiten-Fix aus B ist es unbrauchbar — mein Prototyp
lieferte „1,3 Mrd. TEUR pro Kopf" für Rabobank. **Strikte Reihenfolge: B vor C.**
Eine Vergütungs-Rangliste mit falschen Zahlen wäre der schädlichste denkbare
Fehler in diesem Projekt.

---

## D. Länder-Aggregate über die Population

Aus CCyB1 (`67.01.A`, seit #5/#10 mit aufgelösten Ländern): **„Wie viel
EU-Bankexposure trägt Land X insgesamt?"** — summiert über alle meldenden
Institute. Diese Zahl existiert öffentlich nirgends; sie entsteht erst aus der
Population.

Anwendungen: Konzentrations-Hotspots, Klumpenrisiken gegenüber Drittstaaten,
Kontext für geopolitische Fragestellungen. Baut direkt auf #12/#13 auf.

---

## E. Der Datensatz selbst als Produkt

Das Parquet auf dem `data`-Branch ist bereits ein öffentlich abrufbares,
analysefertiges Artefakt — mit aufgelösten Labels, EUR-Normierung und
Qualitätsflags. EDAP bietet ausschließlich Roh-ZIPs.

Ausbaufähig zu: dokumentiertem Daten-Release mit Versionierung, Schema-Beschreibung
und Zitierhinweis. Geringer Aufwand, weil die Substanz existiert — es fehlt nur
die Verpackung.

---

## Bewertung

| Idee | Issue | Wert | Aufwand | Blockiert durch |
|---|---|---|---|---|
| **A** Kreditverschlechterungs-Kette | [#16](https://github.com/Tobias-Run/P3DH/issues/16) | hoch | mittel | — (Prototyp läuft) |
| **B** Datenqualitäts-Profil | [#17](https://github.com/Tobias-Run/P3DH/issues/17) | hoch | mittel | — |
| **C** Vergütung | [#18](https://github.com/Tobias-Run/P3DH/issues/18) | hoch (öffentlich) | klein | **#17** |
| **D** Länder-Aggregate | [#19](https://github.com/Tobias-Run/P3DH/issues/19) | mittel–hoch | klein | #12 |
| **E** Datensatz-Release | [#20](https://github.com/Tobias-Run/P3DH/issues/20) | mittel | klein | — |

**Empfohlene Reihenfolge:** A (eigenständiger Erkenntniswert, sofort) →
B (schaltet C frei und härtet alles andere) → C → D/E.

**Bewusst nicht vorgeschlagen:** „Transparenz-/Offenlegungs-Score" (misst
Regulierungskategorie, nicht Verhalten — siehe `phase4_analysis_ideas.md`),
Makro-Korrelationen (zu wenig Freiheitsgrade — siehe #11/#14), PDF-NLP
(Ingestionspfad existiert nicht).
