# Kritischer Review der Scale-Befunde

Stand: 01.10.2026 UTC · Repository: Tobias-Run/P3DH

**Alpha Bank S.A., 23.00, 30.06.2025: Die Warnung ist sehr gut begründet. Die Daten sprechen für Millionenbeträge, die in der EBA-Datei als EUR-Beträge stehen. Andere Warnungen sind dagegen teilweise zu pauschal oder markieren den falschen Stichtag. Eine automatische Korrektur anhand des geschätzten Faktors wäre fachlich nicht vertretbar.**

## Ergebnis der vollständigen vorhandenen Befundliste

Geprüft wurden alle **119 bestehenden Befunde**: 54 Reportwarnungen `skaliert`, 17 Reportwarnungen `verdacht` und 48 Templatewarnungen `skaliert`. Die Einzelfallurteile stehen in [review_119_findings.csv](review_119_findings.csv).

| Bestehende Kategorie | Review | Zahl |
|---|---|---:|
| Report `skaliert` | Warnung gegen die Verwendung absoluter Beträge plausibel; kein Gegenbeleg gefunden | 54 |
| Template `skaliert` | Durch direkte Datenvergleiche gut gestützt | 35 |
| Template `skaliert` | Fehler in Teilen plausibel/belegt; Umfang bzw. Faktor zu pauschal | 9 |
| Template `skaliert` | Falscher Stichtag markiert | 2 |
| Template `skaliert` | Kein Skalensprung in den vergleichbaren Datenpunkten | 1 |
| Template `skaliert` | Wegen Datentyp-/Zuordnungsproblemen offen | 1 |
| Report `verdacht` | Verdacht bleibt plausibel, nicht abschließend bestätigt | 15 |
| Report `verdacht` | Kleine Bank ist eine plausible Erklärung; Skalierung nicht belegt | 2 |

Diese Urteile sind eine fachliche Sichtprüfung der eingefrorenen Daten. „Gut gestützt“ heißt nicht, dass für jede Bank ein veröffentlichter PDF-Bericht eine bestimmte Einheit unabhängig bestätigt hat. Die 54 Reportwarnungen sind auch kein Beweis, dass jede Zelle des Reports denselben Faktor braucht.

## Alpha Bank: belastbare Einzelprüfung

- LEI: **213800DBQIB6VBNU5C64**, konsolidiert `CON`.
- Stichtag: **30.06.2025**, Framework 4.1.
- Template: **23.00 / EU CR3 – CRM techniques overview**. Es geht um Buchwerte und Sicherheiten, nicht um eine Kapitalquote.
- [EBA-Originalmeldung Juni](https://errp.eba.europa.eu/public-documents/CODIS/input/213800DBQIB6VBNU5C64.CON_GR_PILLAR3020000_CODIS_2025-06-30_20260306044215000.zip).
- ZIP-Datei: `reports/k_23.00.csv`; `parameters.csv` nennt `baseCurrency=iso4217:EUR`, `decimalsMonetary=-6`.

| CR3-Zelle | Originalwert Juni | Hypothese: Juni × 1 Mio, in Mrd EUR | Gemeldeter Dezember, in Mrd EUR |
|---|---:|---:|---:|
| r0010 c0010: unbesicherte Kredite | 15.930,969975 | 15,931 | 18,822 |
| r0010 c0020: besicherte Kredite | 30.071,313248 | 30,071 | 30,448 |
| r0030 c0010: unbesicherter Gesamtbuchwert | 32.758,700541 | 32,759 | 36,111 |

Die Originaldatei enthält **21 monetäre Werte**, davon **15 positive und 6 Nullwerte**. Alle 15 positiven Datenpunkte können mit Dezember verglichen werden. Der Median von `log10(Dezember/Juni)` beträgt **6,014**, also ungefähr **1,033 Millionen**; alle Vergleichswerte liegen innerhalb Faktor 2 um die Millionenskala. Besonders aussagekräftig ist der besicherte Kreditbuchwert: Nach Multiplikation des Juni-Werts mit einer Million liegt Dezember nur rund **1,25 %** höher.

Unabhängiger Größenanker innerhalb desselben Juni-Reports: KM1-TREA **30.604.478.899,406 EUR**; OV1 enthält denselben Gesamtrisikobetrag. Der übrige Report ist damit nicht insgesamt in Millionen statt EUR gemeldet. Der Juni-CR3-Buchwert von nur einigen zehntausend EUR passt weder zu diesem Größenanker noch zu den Dezemberwerten.

**Urteil:** Die Warnung in 23.00 beibehalten und als wahrscheinliches Einheitenproblem um Faktor **10^6** erklären. Die Daten liefern sehr starke Evidenz; die intentionale Einheit aus einem gesonderten Bank-PDF wurde in diesem Review nicht zusätzlich bestätigt. Rohwerte nicht stillschweigend verändern. `decimalsMonetary=-6` beschreibt Genauigkeit und ist keine allgemeine Multiplikationsanweisung: KM1 liegt bereits in EUR vor.

Der bestehende Detektor nennt einen `zeitreihe_faktor` von **2.406.390**. Das ist kein exakt aus den Buchwerten gemessener Skalierungsfaktor, sondern eine Veränderung des Abstandes zur jeweiligen Zellpopulation. Der direkte Zellvergleich liefert die deutlich bessere Erklärung.

## Befunde, deren Urteil geändert werden sollte

### K&H: Juni ist zu groß, Dezember ist plausibel

**Kereskedelmi és Hitelbank csoport**, LEI `KFUXYFTU2LHQFQZDQG45`, Template **41.00**. Der aktuelle Detektor markiert **31.12.2025** als zu klein.

Die Zeile r0010 c0010 enthält im Juni **3.117.421.150.811.375 EUR**, im Dezember **3.273.209.108,27 EUR**. Juni-KM1-TREA liegt dagegen bei **7,592 Mrd EUR**. Die ursprünglichen HUF-Rohwerte zeigen denselben Bruch: rund **1,247 × 10^18 HUF** gegenüber **1,259 × 10^12 HUF**. Der Wechsel des EUR-Kurses erklärt keine sechs Größenordnungen.

**Empfehlung:** Warnung gegen den überhöhten **Juni** richten; Dezember nicht um eine Million erhöhen. Die zusätzliche Kennzeichnung `unit_ambiguous` für das ESG-Template beachten. Auch ein *zu großer* Betrag kann ein Skalenfehler sein.

### Citibank: historischer Betrag beweist die falsche Richtung

**Citibank Europe plc**, LEI `N1FBEDJ5J41VKZLO2475`, Template **68.00 / EU IRRBB1**, betrifft Zinsrisikoszenarien. Der Detektor markiert **Dezember**.

Juni r0010 c0010 meldet **−121.994.457.500 EUR**. Dezember meldet aktuell **−113.081.622 EUR** und als Vorperiode **−121.994.458 EUR**. Der als Vorperiode wiederholte Juni-Betrag unterscheidet sich vom Juni-Original praktisch exakt um Faktor **1.000**. Juni-KM1-CET1 beträgt nur **14,450 Mrd EUR**. Diese Wiederholung ist wesentlich stärker als ein bloßer Vergleich zweier veränderlicher Portfolios.

**Empfehlung:** Juni als um Faktor 1.000 überhöht kennzeichnen, die Dezemberwarnung entfernen. Dezemberbeträge in der Größenordnung von Millionen sind hier plausibel.

### BBVA 83.01.C: Populationswechsel statt eigener Skalierung

**BBVA**, LEI `K8MS7FD7N5Z2WQ51AZ71`, **30.06.2025**, **83.01.C / EU CQ4**.

Bei **15 direkt vergleichbaren Datenpunkten**, einschließlich gleicher negativer Vorzeichen, beträgt der Median des Dez./Juni-Logverhältnisses nur **0,048**; alle liegen innerhalb Faktor 2 um die unveränderte Skala. Das Template enthält im Juni Beträge bis **227,857 Mrd EUR**, im Dezember bis **248,774 Mrd EUR**. Der Juni enthält mehr kleinere Teilpositionen; der Median über die jeweils vorhandenen Zellen ist deshalb kein identischer Vergleichskorb.

**Empfehlung:** Die pauschale Juni-Skalierungswarnung ist durch diesen Befund nicht gestützt. Eine kleine Teilposition ist kein Einheitenfehler. Andere Plausibilitätsprüfungen können unabhängig davon berechtigt sein.

## Berechtigte Warnung, aber falscher Umfang oder Faktor

Die vollständigen Einzelurteile stehen in der CSV. Besonders relevant:

| Bank / Template / Stichtag | Was die Warnung präzisieren muss |
|---|---|
| Rabobank / 61.00 / 03-2026 | CET1, TREA und Leverage sind in EUR plausibel. Nur Liquidität/Funding enthält kleine Werte wie HQLA **103.493** und ASF **469.754**. Millionenhypothese, keine Skalierung des Kapitalteils; bestehender Faktor **10^3** ist ungeeignet. |
| BRD / 61.00 / 06-2025 | Aktuelles Kapital und TREA sind plausibel. Liquiditäts-/Funding-Zeilen liegen etwa Faktor **1.000** unter Dezember. |
| UniCredit Bank Austria / 71.00 / 12-2025 | Aktuelle Spalte **0010** ist plausibel. Vorperiodenspalte **0020** enthält Millionenwerte, z.B. Leverage-Exposure **116.540** statt ungefähr **116,540 Mrd EUR**. |
| BPCE / 27.02.A / 12-2025 | Gesamt-Exposure **634.778,85** neben RWA **133.910.346.543,27 EUR**. Verschiedene Skalen im selben Template; kein einheitlicher Faktor. |
| BBVA / 74.00.A / 06-2025 | Unterschiedliche Datapoints und Perioden teilen sichtbare Koordinaten. Teile sind um etwa **1.000** kleiner, andere bereits in EUR. Historischer Kleinbetrag erscheint im Dezember wieder. |
| Société générale / 27.01 und 27.02.A / 06-2025 | Normal große Werte und etwa Faktor **1.000** kleine Teilbeträge nebeneinander. |
| Société générale / 27.02.B / 06-2025 | Vergleich enthält Cluster bei **10^6** und **10^9**; pauschales **10^9** wäre falsch. |
| BNP Paribas / 04.00.A / 06-2025 | Etwa **10^6** kleine Teile neben normal großen Vergleichszellen. |

Bei Banca Transilvania ist September für den Juni-Liquiditätsbefund die bessere Referenz: In 73.00.C stimmen **80** Vergleichspunkte nach einem Faktor von ungefähr **1.000** eng überein. Der Dezembervergleich mischt dagegen unterschiedliche Größenordnungen. Der größte Vergleichsstichtag ist somit nicht automatisch der sauberste.

## Offene und schwach begründete Fälle

**UniCredit Bank Czech Republic and Slovakia, 29.02.A, 12-2025:** Die acht direkt wiederkehrenden positiven Werte sind feste Risikogewichte wie **0,5**. Sie werden im Codebook als `monetary` geführt und mit dem CZK/EUR-Kurs umgerechnet, obwohl ihre sichtbare Bedeutung dimensionslos ist. Die eigentlichen Exposure-Datenpunkte wechseln zugleich ihre Belegung. Das ist ein Datentyp-/Semantikwiderspruch; der bestehende Faktor **10^3** ist kein belastbarer Reparaturfaktor. Ein echtes zusätzliches Skalenproblem bei Beträgen bleibt möglich. Zuerst Taxonomie, Datentyp und Periodenzuordnung prüfen.

**MERKANTI BANK LTD und BANCA PROMOS:** Beide weisen Kapital im zweistelligen Millionenbereich und TREA rund **18 Mio EUR** auf. Für kleine Banken sind solche Werte plausibel. Der Abstand zur gemischten Bankenpopulation rechtfertigt keine automatische Multiplikation um 1.000. „Verdacht“ ist hier keine bestätigte Fehlermeldung; unabhängige veröffentlichte Größenanker fehlen im geprüften Vergleich.

Die anderen **15 Reportverdachte** bleiben plausible Tausender-Hypothesen. Sie dürfen weiterhin nicht wie bestätigte uniforme Fehler behandelt werden. Beispiele: Slovenská sporiteľňa bleibt an allen vier Stichtagen auf derselben kleinen Skala; eine stabile Zeitreihe widerlegt deshalb einen durchgängigen Einheitenfehler nicht. Gorenjska enthält dagegen auch Milliardenwerte und könnte nur teilweise betroffen sein.

## Warum der Detektor diese Fehlurteile erzeugt

In `scripts/build_report_scale.py` vergleicht `template_spruenge()` den **Median des Abstands zu fremden Zellpopulationen** über Stichtage. Die Differenz wird anschließend als `template_sprung` stets mit Urteil `skaliert` ausgegeben. Dafür gibt es mehrere Schwachstellen:

1. Unterschiedliche befüllte Zellen, Perioden und Populationen verändern den Median, auch wenn die eigenen Beträge unverändert plausibel bleiben. BBVA 83.01.C ist der Gegenbeleg.
2. Der größte Betrag/Versatz wird automatisch als guter Vergleich angenommen. Bei K&H und Citibank ist gerade der größere Stichtag fehlerhaft.
3. Dieselbe sichtbare Koordinate kann mehrere Datapoints/Perioden enthalten. Die ursprüngliche Vergleichspopulation trennt weder Datapoint noch Scope/Institutionsart vollständig. Auch die Mindestzahl 20 zählt Fakten, nicht zwingend 20 unabhängige Institute.
4. `faktor_geschaetzt` aus Populationsabstand oder einem gemischten Template ist keine sichere Zellkorrektur.
5. `decimals` ist Genauigkeit. Kleine Werte widersprechen ihr nicht automatisch formal; das ist ein Indiz, kein alleiniger Beweis für Millionen-/Tausendereinheiten.
6. Die Behauptung, Skalenfehler machten Werte „immer zu klein“, ist durch K&H und Citibank widerlegt.
7. Reportverdacht unterdrückt weitere Templatebefunde. Ein insgesamt verdächtiger Report kann dennoch zusätzliche, anders skalierte Teilbereiche enthalten.

## Konkrete Empfehlung für die Weiterentwicklung

Priorität 1: Die drei oben genannten falschen Templateurteile fachlich korrigieren und die neun Teilfehler mit ihrer Reichweite erklären. **Alpha unverändert warnen**, aber den Faktor als Hypothese und mit konkreten Beispielzellen zeigen.

Priorität 2: Gleiche fachliche Datenpunkte und Perioden vergleichen; absolute Größenanker aus KM1/OV1 und historisch wiederholte Werte als Richtungsbeleg verwenden. Beide Fehlerrichtungen zulassen. Risikogewichte und andere dimensionslose Werte aus monetären Skalentests herausnehmen, sobald die Taxonomiezuordnung geklärt ist.

Priorität 3: Eine strukturierte Warnung führen: `Status`, `Richtung`, `betroffene Datenpunkte/Zeilen/Spalten`, `Referenz`, `vermuteter Faktor`, `Begründung`. Beispielsweise Rabobank „KM1-Liquidität vermutlich in Millionen; Kapitalteil plausibel“. Vergleiche nur für betroffene absolute Kennzahlen sperren; Quoten können bei gleichmäßig skaliertem Zähler/Nenner weiter brauchbar sein.

Vor produktiver Änderung die vollständige Kandidatenmenge neu prüfen. Ein strengerer Vergleich darf nicht stillschweigend berechtigte Mischfehler oder Institute ohne Referenzstichtag verlieren. Keine automatische Veränderung der EBA-Rohwerte.

## Einordnung der bestehenden GitHub-Issues

- [#9 Einheiten-QA](https://github.com/Tobias-Run/P3DH/issues/9): Die Entscheidung, `decimals` nicht als Multiplikator zu verwenden und Rohdaten unverändert zu lassen, bleibt richtig. Der Review erweitert sie um Fehler *nach oben* und um den Datentypwiderspruch in 29.02.A.
- [#83 Scale/Footprint](https://github.com/Tobias-Run/P3DH/issues/83): Der ursprüngliche Schutz gegen unplausibel kleine absolute Exposures ist weiterhin erforderlich. Der Abschluss dieses Issues beweist nicht, dass jeder spätere Templatebefund richtig ist. Richtungswahl, Teilfehler und direkte Zellvergleiche benötigen eine gezielte Folgekorrektur.

## Datenbasis und Verifikation

- Eingefrorener produktiver Daten-Snapshot: `f47ef2d32968e59188b4139ede3ccac1d9737f21`.
- [Parquet](https://raw.githubusercontent.com/Tobias-Run/P3DH/f47ef2d32968e59188b4139ede3ccac1d9737f21/state/p3dh_long.parquet), SHA-256: `8cc95fa2dd4a7d08c7502fb9e433bbe4f311d51ee50a17533730ee9db9fc6cdf`.
- Dieses Parquet enthält **2.295.224 Fakten**, **882 Reports mit Fakten**, **474 LEIs**. Metadaten-/Viewer-Zählungen können auch Institutionen oder Reports ohne Fakten enthalten.
- Die Befundliste wurde mit dem bestehenden Detektor aus diesem Parquet neu gebaut und stimmt **bytegenau** mit `processed/scale_flags.csv` überein, SHA-256 `14f96727f50f42e2b9a40e8d0f64e9e20abc48a486f643ed243b00badc5c4dbb`.
- **280 EBA-Original-ZIPs** heruntergeladen, einschließlich Referenzdateien; URLs, Parameter und SHA-256 in [raw_validation.json](raw_validation.json).
- **158.553 monetäre Datenzeilen** der 119 Befunde gegen Rohwert, Quelltemplate und Datapoint geprüft. Zusätzlich `float(raw)=fact_value` und `fact_value × gespeicherter fx_rate=fact_value_eur` geprüft: **0 Abweichungen**. Das prüft die Übernahme und Rechenoperation, nicht unabhängig jeden historischen FX-Kurs oder jede fachliche Datentypzuordnung.
- Direkte Vergleichsidentität: Entity/Scope + Template + Zeile + Spalte + offene Dimensionen + Datapoint. Nullwerte und Vorzeichenwechsel liefern keinen verlässlichen logarithmischen Vergleich und wurden dafür ausgelassen. Negative Werte gleichen Vorzeichens wurden berücksichtigt, besonders für IRRBB.
- Originalurteile, fachlicher Review und gemessene Vergleichsverhältnisse bleiben getrennt in der CSV und [findings.json](findings.json).
- **12 unabhängige Replay-Checks bestanden**: Snapshot-/Befundidentität, vollständige Liste, Originalübernahme, Alpha, K&H, Citibank, BBVA, Rabobank, Bank Austria und der CR10-Datentypwiderspruch. Sie sichern die beschriebenen Tatsachen ab, nicht jeden vermuteten Korrekturfaktor. Siehe [verify_review.py](verify_review.py) und [verification.txt](verification.txt).
- Die Originalmeldungen können nach dem geprüften Abruf erneut eingereicht werden. Die gespeicherten Hashes und Dateien sichern den hier geprüften Stand.

Dieser Bericht dokumentiert den ursprünglichen Auditstand vor der Korrektur. Die Umsetzung und der vollständige Vorher/Nachher-Vergleich stehen in [IMPLEMENTATION.md](IMPLEMENTATION.md), Folge-Issue [#122](https://github.com/Tobias-Run/P3DH/issues/122).
