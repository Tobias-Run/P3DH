# Das Korrekturspiel

**Sollte ein Institut einen selbst entdeckten Fehler in einer bereits
veröffentlichten Säule-3-Meldung proaktiv korrigieren — oder schweigen und
darauf hoffen, dass es niemand merkt?**

Die Frage klingt nach Ethik, ist aber eine Entscheidung unter Unsicherheit mit
einem Gegenspieler. Damit ist sie spieltheoretisch zu behandeln, und das
Ergebnis ist schärfer als der moralische Appell: **Korrigieren ist die bessere
Strategie — aber aus einem anderen Grund, als üblicherweise dafür angeführt
wird.** Nicht weil der Markt Ehrlichkeit belohnt (das können wir nicht
belegen, siehe Abschnitt 7), sondern weil die Entdeckungswahrscheinlichkeit
durch den Data Hub selbst gestiegen ist.

Dieses Dokument entwickelt das Modell, prüft es gegen die Zahlen dieses Repos
und benennt, was es **nicht** entscheiden kann.

> **Kein Werturteil über ein einzelnes Institut.** Es geht um die Anreizlage,
> nicht um Vorwürfe. Wo unten Zahlen aus unseren Artefakten stehen, sind es
> Befunde *unseres* Prüfverfahrens, keine festgestellten Meldefehler.

---

## 1. Warum das überhaupt ein Spiel ist

Ein Spiel liegt vor, wenn der Ertrag einer Entscheidung davon abhängt, was ein
anderer tut. Genau das ist hier der Fall:

| | |
|---|---|
| **Spieler 1** | das Institut, das einen Fehler in einer veröffentlichten Meldung kennt |
| **Spieler 2** | die Aufsicht und die Datennutzer — Analysten, Presse, Wettbewerber, Projekte wie dieses |
| **Private Information** | nur das Institut weiss, dass der Fehler existiert |
| **Züge des Instituts** | **K** (korrigieren, sichtbar nachmelden) oder **S** (schweigen) |
| **Zug der Gegenseite** | prüfen oder nicht prüfen — mit welcher Gründlichkeit, weiss das Institut nicht |

Der entscheidende Punkt: **eine Korrektur ist öffentlich und dauerhaft.** Der
EDAP-Katalog führt jede Fassung mit Zeitstempel; eine Nachmeldung verschwindet
nicht wieder. Wer korrigiert, gibt damit zu, dass die erste Fassung falsch war.
Das ist der Preis der Korrektur — und deshalb ist S nicht von vornherein
irrational.

---

## 2. Das Grundmodell

Ein Zug, zwei Handlungen. Die Auszahlungen aus Sicht des Instituts, wenn der
Fehler existiert:

```
U(K) = −c              c = Aufwand + sichtbares Eingeständnis
U(S) = −p · D          p = Wahrscheinlichkeit, dass es ein anderer findet
                       D = Schaden, wenn es ein anderer findet
```

Korrigieren lohnt sich genau dann, wenn `c < p · D`, also:

> **Korrigiere, wenn p > c / D.**

Die Schwelle hängt an *einem* Verhältnis: Kosten der Korrektur zum Schaden der
Entdeckung.

| c / D | Schwelle p\* | Lesart |
|---|---:|---|
| 0,50 | 50 % | Korrektur fast so teuer wie Entdeckung — nur bei sicherer Aufdeckung lohnend |
| 0,20 | 20 % | |
| 0,10 | 10 % | |
| 0,05 | 5 % | |
| 0,01 | 1 % | Korrektur billig gegen den Schaden — praktisch immer korrigieren |

**Die ganze Frage ist damit: wo liegt c/D wirklich, und wo liegt p?** Beides
ist zu diskutieren, und für p haben wir ein Argument aus diesem Projekt.

---

## 3. Warum c/D klein ist: Schweigen macht aus einem Fehler eine Entscheidung

Der Schaden D ist keine feste Grösse. Er hängt daran, ob das Institut den
Fehler **kannte**:

- Ein entdeckter, unkorrigierter Fehler, den niemand bemerkt hatte, ist ein
  Qualitätsmangel.
- Ein entdeckter, unkorrigierter Fehler, den das Institut **kannte**, ist etwas
  anderes. Art. 431(3) CRR verlangt eine förmliche Leitlinie zur Angemessenheit
  der Offenlegung; eine bewusst stehen gelassene Falschangabe stellt nicht die
  Zahl in Frage, sondern das Verfahren.

Das ist der eigentliche Hebel. **S verwandelt ein Versehen in eine
Entscheidung** — und Entscheidungen sind teurer als Versehen, weil sie den
Verweis auf das eigene Kontrollsystem zerstören. Wer korrigiert, kann auf
funktionierende interne Kontrolle verweisen; die Korrektur *ist* der Beleg
dafür. Wer schweigt und ertappt wird, hat den Beleg gegen sich.

Damit ist D gross und c vergleichsweise klein: eine Nachmeldung kostet
Arbeitszeit und etwas Gesicht. Das Verhältnis c/D liegt plausibel im unteren
einstelligen Prozentbereich — die Schwelle p\* also ebenfalls.

---

## 4. Warum p gestiegen ist — und das ist die eigentliche Nachricht

Vor dem Data Hub stand Säule 3 in PDF-Anhängen von Geschäftsberichten. Wer 489
Institute gegeneinander prüfen wollte, musste sie abtippen. Die
Entdeckungswahrscheinlichkeit p war **nicht deshalb niedrig, weil niemand
hinsehen wollte, sondern weil Hinsehen zu teuer war.**

Mit maschinenlesbarem XBRL-CSV an einer zentralen Stelle ist dieser Preis
zusammengebrochen. Dieses Repo ist der Existenzbeweis:

| Was ein Nebenprojekt ohne Budget leistet | Artefakt |
|---|---|
| Plausibilitätsbefunde bei **273 von 489 Instituten**, davon **139 mit einem `hoch`-Befund** | `quality_profile.csv` (#17) |
| Nachrechnen der EBA-Länderaggregate: **60 % von 379 Punkten innerhalb 1 pp** | `eba_reconciliation.csv` (#37) |
| 2 Verdachtsfälle vertauschter Ländercodes aus 105 geprüften Stichtagspaaren | `country_swap.csv` (#59) |
| Konzernentdopplung über zwei unabhängige Graphen | `entity_groups.csv` (#32) |

> ⚠️ **Das misst nicht p.** p ist die Wahrscheinlichkeit, dass ein *bestehender*
> Fehler auffällt; wir kennen die Grundgesamtheit der Fehler nicht und können
> sie nicht kennen. Die Tabelle zeigt etwas anderes, das aber genügt: **die
> Kosten des Prüfens sind gefallen.** Und p ist eine Funktion dieser Kosten.

Daraus folgt die These dieses Dokuments:

> **Die Wirkung des Data Hub liegt weniger in der Transparenz für Investoren
> als in der Veränderung der Entdeckungstechnologie.** Kaum jemand liest
> XBRL-Dateien. Aber jeder *kann* sie jetzt prüfen, und einige tun es. In der
> Ungleichung `p > c/D` bewegt der Hub die linke Seite — und damit das
> Gleichgewicht.

Das gilt asymmetrisch zugunsten von K: p steigt über die Zeit, c nicht. Eine
Meldung, die heute unauffällig bleibt, kann in zwei Jahren von einem Skript
geprüft werden, das es heute noch nicht gibt. **S ist eine Wette gegen den
technischen Fortschritt der Gegenseite.**

---

## 5. Drei Verfeinerungen, die das Grundmodell zurechtrücken

### 5.1 Der Korrekturzähler ist selbst ein Spieler

Sobald ein Dritter Korrekturen **zählt** und die Zahl als Qualitätsrangliste
gelesen wird, steigt c: Korrigieren bringt einen auf eine Liste. Ein Zähler,
der das Korrigieren bestraft, verschiebt das Gleichgewicht in Richtung S und
zerstört damit genau die Information, die er messen will.

Das ist keine abstrakte Sorge. **Dieses Repo baut diesen Zähler**
(`submission_profile.csv`, Issue #31), und die Auflage des Issues — *„Kein
Werturteil. Eine Korrektur ist ein Zeichen von Sorgfalt, keine Schuld"* — ist
deshalb keine Höflichkeit, sondern eine **Konstruktionsbedingung**. Ein
Beobachter, der das Verhalten verändert, das er misst, misst am Ende sein
eigenes Echo.

### 5.2 Schweigen und Nichtwissen sehen von aussen gleich aus

Das Modell setzt voraus, dass das Institut den Fehler kennt. Ein grosser Teil
der Wirklichkeit ist aber: **niemand hat es intern bemerkt.** Das ist keine
Strategie, sondern eine Fähigkeitsgrenze — und von aussen erzeugt es **exakt
dieselbe Datenzeile**: keine Korrektur.

Kein Artefakt dieses Projekts kann die beiden trennen. Das ist derselbe
Grundsatz, an dem das Projekt auch sonst hängt: *Fehlt ≠ Null.* Eine fehlende
Korrektur belegt kein Kalkül.

### 5.3 Die Richtung des Fehlers verschiebt die Auszahlung

Ein Fehler, der das Institut **besser** aussehen lässt (überhöhte Kapitalquote,
zu niedrige RWA), ist strategisch etwas anderes als einer, der ihm schadet. Bei
einem schmeichelnden Fehler bedeutet K, eine gute Zahl öffentlich
zurückzugeben; der Anreiz zu S ist dort strikt stärker.

Daraus folgt eine **prüfbare Vorhersage**: Ist Schweigen strategisch, müssten
unkorrigierte Fehler systematisch in die schmeichelnde Richtung zeigen.
Abschnitt 8 sagt, wie das zu messen wäre.

---

## 6. Was die Daten dieses Projekts hergeben

Alle Zahlen aus `processed/submission_profile.csv` und
`interim/edap_recon/manifest_full.csv`, Stand des letzten Harvests.

### 6.1 Wie oft wird überhaupt korrigiert

```
Einreichungen gesamt        4.278
  davon Korrekturen           472   (11,0 %)
Meldungen (eindeutige Schlüssel) 3.806
  mit mehr als einer Fassung    376   (9,9 %)
Institute                     489
  die je korrigiert haben       162   (33,1 %)
meiste Fassungen einer Meldung   10
```

### 6.2 Die meisten Korrekturen sind gar keine Strategie

Der Abstand zur jeweils vorherigen Fassung:

| Abstand | Korrekturen | Anteil |
|---|---:|---:|
| unter 1 Stunde | 93 | 19,7 % |
| unter 1 Tag | 150 | 31,8 % |
| unter 7 Tagen | 257 | 54,4 % |
| unter 30 Tagen | 365 | 77,3 % |
| **über 30 Tagen** | **107** | **22,7 %** |
| über 90 Tagen | 18 | 3,8 % |

Median 4,2 Tage, Maximum 170 Tage.

**Ein Fünftel aller Korrekturen erfolgt binnen einer Stunde.** Das ist keine
Fehlerentdeckung, das ist ein missglückter Upload. Über die Hälfte liegt
innerhalb einer Woche — plausibel die eigene Endkontrolle, bevor überhaupt
jemand hingesehen hat.

> **Das Spiel wird auf einer viel kleineren Bühne gespielt, als die Rohzahl
> suggeriert.** Strategisch interessant sind die **107 Korrekturen nach mehr
> als 30 Tagen**: Fehler, die die interne Kontrolle überlebt haben. Nur dort
> stellt sich die Frage des Dokuments überhaupt.

### 6.3 Die naive Auslegung misst Grösse, nicht Verhalten

Issue #31 behauptete, Institute mit Plausibilitätsbefunden korrigierten
**1,5- bis 1,9-mal häufiger** je Einreichung — und wertete das als externe
Bestätigung des Prüfverfahrens. Nachgerechnet, geschichtet nach Meldeumfang:

| Einreichungen | mit Befund | ohne Befund | Faktor |
|---|---:|---:|---:|
| 1–3 | 0,000 (n=11) | 0,039 (n=56) | **0,00** |
| 4–8 | 0,059 (n=113) | 0,055 (n=133) | **1,07** |
| 9+ | 0,143 (n=149) | 0,135 (n=27) | **1,06** |

**Der behauptete Effekt reproduziert nicht.** Was stattdessen durchschlägt, ist
der Meldeumfang: der Anteil der Institute, die überhaupt je korrigiert haben,
steigt von **7,5 %** (1–3 Einreichungen) über **20,3 %** (4–8) auf **60,8 %**
(9+). Wer viel meldet, korrigiert irgendwann etwas — das ist Arithmetik, kein
Verhalten.

Für das Spiel heisst das: **eine rohe Korrekturzahl ist als Signal unbrauchbar.**
Sie rangiert Institute nach Grösse. Ein Beobachter, der sie als Qualitätsmass
liest, liest eine Bilanzsumme.

### 6.4 Der Befund, der bleibt

```
Institute mit mindestens einem hoch-Befund      139
  davon haben nie etwas korrigiert               73   (52,5 %)
  davon haben korrigiert                         66
```

`persistent_findings.csv` führt diese 73. Mit allen Vorbehalten aus 5.2 — es
sind unsere Befunde, keine festgestellten Fehler, und Nichtwissen ist nicht
ausgeschlossen — ist das die einzige Teilmenge, in der die Frage dieses
Dokuments empirisch etwas zu suchen hat.

---

## 7. Gleichgewichte — und warum der Signalweg hier ausfällt

**Pooling auf S** (p niedrig): niemand korrigiert, Korrekturen tragen keine
Information, und eine saubere Akte sagt nichts.

**Trennendes Gleichgewicht** (p hoch): wer einen Fehler hat, korrigiert; dann
wird **die ausbleibende Korrektur** zum aussagekräftigen Signal.

Unsere Zahlen sind mit keinem der beiden Reinformen verträglich: ein Drittel
der Institute hat je korrigiert, 52,5 % der Institute mit `hoch`-Befund nie.
Das Gleichgewicht lässt sich aus unseren Daten auch nicht identifizieren — dazu
müssten wir die Fehler kennen, nicht nur unseren Indikator für sie.

**Der klassische Signalisierungs-Ertrag fällt hier zusätzlich aus.** Das
Standardargument für K lautet: der Markt honoriert das Eingeständnis. Wir haben
versucht, das zu messen — Issue #39, Ereignisstudie auf den
Einreichungszeitstempeln — und es **geschlossen, ohne es beantworten zu
können**: Kursdaten sind keine offene Quelle. Und selbst mit ihnen träfe die
Antwort nur eine Minderheit: **von 489 Instituten sind 69 belegt börsennotiert**
(`equity_link.csv`). Vier von fünf haben gar keine handelbare Aktie —
Sparkassen, Genossenschafts- und Förderbanken. Für sie existiert der
Signalkanal zum Kapitalmarkt schlicht nicht.

> Wer K mit der Marktreaktion begründet, stützt sich auf einen Kanal, den wir
> **nicht gemessen haben** und der für die Mehrheit der Population **nicht
> existiert.** Das Argument für K muss ohne ihn tragen — und es tut es, über
> p und D.

---

## 8. Die eine Messung, die es entscheiden würde

Die Vorhersage aus 5.3 ist prüfbar, und zwar **mit Daten, die wir bereits
besitzen**: `manifest_full.csv` führt die URL **jeder** Fassung, auch der
überholten. Beide Fassungen sind herunterladbar und gegeneinander zu
rechnen.

Damit wären zwei Dinge messbar, die das Modell braucht:

1. **Die Richtung der Korrektur.** Bewegen Korrekturen die Kapitalquote nach
   oben oder nach unten? Systematisch nach unten hiesse: korrigiert wird, was
   geschmeichelt hat — ein Hinweis auf funktionierende interne Kontrolle.
   Systematisch nach oben wäre das Gegenteil.
2. **Freiwillig oder erzwungen.** Die 107 späten Korrekturen sind die
   interessanten. Ob sie aus eigener Prüfung oder auf Nachfrage der Aufsicht
   erfolgten, entscheidet über die ganze Auslegung — und **dafür fehlt uns das
   Datum der Beanstandung.** Das ist nicht öffentlich. Ein Näherungsmass wäre
   die zeitliche Häufung um Aufsichtstermine.

**Was auch das nicht sähe:** die dritte Strategie, die dieses Dokument bisher
übergangen hat — **den Fehler still in der nächsten regulären Meldung
richtigstellen**, ohne die alte Fassung zu korrigieren. Kein Eingeständnis,
keine zusätzliche Fassung im Katalog, kein Eintrag in irgendeiner unserer
Tabellen. Sie ist billiger als K und weniger riskant als S — und für einen
Beobachter von aussen praktisch unsichtbar. Wer Korrekturverhalten misst, misst
nur die Institute, die den sichtbaren Weg gewählt haben.

---

## 9. Die Antwort

**Korrigieren — und zwar aus drei Gründen, von denen keiner moralisch ist:**

1. **p ist gestiegen und steigt weiter.** Die Prüfkosten sind zusammengebrochen;
   was heute unauffällig bleibt, prüft übermorgen ein Skript, das es heute noch
   nicht gibt. S ist eine Wette gegen den technischen Fortschritt der
   Gegenseite, und die Wette läuft unbefristet weiter.
2. **D ist gross, weil Schweigen die Fehlerart wechselt.** Ein korrigierter
   Fehler belegt die interne Kontrolle. Ein bewusst stehen gelassener
   widerlegt sie — und das trifft Art. 431(3) CRR, nicht nur die Zahl.
3. **c ist klein und einmalig.** Eine Nachmeldung kostet Arbeitszeit und etwas
   Gesicht. Bei c/D im unteren einstelligen Prozentbereich liegt die Schwelle
   p\* dort ebenfalls — und diese Schwelle ist heute erreicht.

**Wann das Modell etwas anderes sagt — der Vollständigkeit halber:** Bei einem
unwesentlichen Fehler ohne aufsichtliche Folge ist D klein, und c ist nicht
null (jede zusätzliche Fassung entwertet die Arbeit der Datennutzer, die die
vorige verwendet haben). Dann ist die Richtigstellung in der nächsten regulären
Meldung die bessere Wahl als die sofortige Nachmeldung. Das Modell sagt nicht
„immer sofort korrigieren"; es sagt **„nie darauf setzen, dass es niemand
merkt"**. Das ist ein Unterschied.

---

## 10. Grenzen

- **Ein Modell ist ein Modell.** c, D und p sind hier nicht gemessen, sondern
  begründet eingeordnet. Die Richtung des Ergebnisses ist robust, die Schwelle
  p\* ist es nicht.
- **Unsere Befunde sind nicht Fehler.** `hoch` heisst: unser Verfahren hält den
  Wert für unplausibel. Zwischen Befund und Meldefehler liegt eine Prüfung, die
  wir nicht leisten können.
- **Kein Urteil über ein einzelnes Institut.** Die 73 aus
  `persistent_findings.csv` sind eine Liste zum Hinsehen, keine Liste von
  Verstössen.
- **Der Katalog ist ein Schnappschuss.** `manifest_full.csv` steht auf dem
  Stand des letzten Harvests; spätere Korrekturen fehlen. Alle Zahlen sind
  untere Schranken.
- **Die unsichtbare Strategie bleibt unsichtbar.** Siehe Abschnitt 8.

---

## Quellen im Repo

| Aussage | Artefakt |
|---|---|
| Korrekturzahlen, Schichtung nach Meldeumfang | `processed/submission_profile.csv` |
| 73 Institute mit `hoch`-Befund ohne Korrektur | `processed/persistent_findings.csv` |
| Plausibilitätsbefunde | `processed/quality_profile.csv` |
| Abstände zwischen Fassungen, URLs überholter Fassungen | `interim/edap_recon/manifest_full.csv` |
| Börsennotierung, 69 von 489 | `processed/equity_link.csv` |
| Nachrechnen der EBA-Aggregate | `processed/eba_reconciliation.csv` |

Methodische Einordnung der einzelnen Blätter: [`docs/datensatz.md`](datensatz.md).
