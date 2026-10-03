# TREA oder Bilanzsumme als Größenmaß?

Stand: 2. Oktober 2026. Prüfung auf dem eingefrorenen Datenstand bbcb7aa von PR #135 (vor dem ersten Cache-Pilotpaket), ohne Umstellung der Anwendung oder Änderung der ursprünglichen Facts.

**Empfehlung: Die verbleibende Eigentümerrecherche primär nach TREA priorisieren. Im Peer-Modell TREA als Maß der regulatorischen Risikogröße beibehalten; für die wirtschaftliche Größe die Bilanzsumme ergänzend betrachten.** Die statistischen Peer-Cluster verwenden bereits logarithmiertes TREA mit einem maximal zehnfachen Größenverhältnis. Es ist dort kein Wechsel von Bilanzsumme auf TREA erforderlich.

## Messung am eigenen Datenbestand

Der ursprüngliche Bestand von 321 ungeprüften Kennungen bleibt eingefroren. Eine Kennung hat keine Facts. Verglichen werden positive, endliche EUR-Werte mit eindeutigem Rohbetrag und Dimensionssatz, ohne mehrdeutige Einheit. Gemeldete Scale-Befunde im jeweiligen Template oder Gesamtbericht werden konservativ ausgeschlossen. Zusätzlich ist Bank Millennium H1 2025 wegen des konkret belegten Währungsverdachts ausgeschlossen. Für Bilanzsummen gelten die vier bereits dokumentierten offiziellen Ergänzungen/Überlagerungen aus der früheren Recherche.

| Vergleich | TREA | Bilanzsumme |
|---|---:|---:|
| Ursprüngliche 321 Kennungen: jüngster technisch nutzbarer Wert je Kennzahl | 265 (82.6%) | 173 (53.9%) |
| Ursprüngliche 321: Wert genau im bevorzugten jüngsten Report | 257 | 114 |
| Verbleibende 291 ungeprüfte Kennungen: jüngster technisch nutzbarer Wert | 235 (80.8%) | 143 (49.1%) |
| Verbleibende 291: Wert genau im bevorzugten jüngsten Report | 228 | 105 |

„Technisch nutzbar“ ist keine abgeschlossene fachliche Quellvalidierung aller Werte. Es wird je Kennung und Kennzahl der jüngste gültige Stichtag verwendet, bei gleichem Datum CON bevorzugt. Ein Ausweichen auf einen älteren gültigen Report ist explizit von Abdeckung am tatsächlich jüngsten Report getrennt. Die Ranglisten enthalten deshalb unterschiedliche Stichtage; innerhalb einer Peer-Gruppe sind einheitlicher Stichtag, Scope und Framework weiterhin erforderlich.

Die frühere Bilanzsummenrecherche hatte 192 priorisierbare Fälle gezählt. Die hier verwendeten strengeren, gleichartigen Scale-Ausschlüsse reduzieren die Bilanzsummenabdeckung auf 173. Die 192 sind deshalb nicht der direkte Vergleichswert für die gefilterten TREA-Werte. Ganze Report-Sperren können einwandfreie Einzelzellen mit ausschließen; die konservative Zahl ist keine Feststellung, dass alle gesperrten Bilanzsummen falsch sind.

Für 106 Institute sind beide Größen im selben bevorzugten jüngsten Report vorhanden. Die Spearman-Rangkorrelation beträgt **0.920**. Die Ranglisten sind somit insgesamt ähnlich, aber einzelne Geschäftsmodelle unterscheiden sich deutlich. Datums-/Scope-Mischungen werden für diese Korrelation vermieden. Die Korrelation beweist keine Überlegenheit für einen Nutzerzweck.

Von den bisher recherchierten Bilanzsummen-Top-30 bleiben **25** auch in den TREA-Top-30 der ursprünglichen 321. Neu wären: **Bpifrance, Bank of America Europe Designated Activity Company, EUROBANK S.A., RCI Banque, Caixa Geral de Depósitos, S.A.**. Euroclear, Stadshypotek, Barclays Bank Ireland, Bankinter und BofA Securities Europe fallen aus diesen TREA-Top-30. Auch bei Beschränkung auf die 166 Institute mit beiden nutzbaren Größen überschneiden sich 25 der Top-30; der Unterschied ist also nicht allein fehlender Datenabdeckung zuzuschreiben. Vergleiche der Top-30 genau am jüngsten Report ergeben stärkere Unterschiede, weil Bilanzsummen in vielen jüngeren Meldungen nicht veröffentlicht werden. Das ist überwiegend ein Abdeckungs-/Zeitpunkteffekt und kein isolierter Geschäftsmodelleffekt.

## Was die Maße fachlich aussagen

| Maß | Aussage | Relevante Grenzen |
|---|---|---|
| Bilanzsumme | Volumen der bilanzierten Vermögenswerte nach Rechnungslegung | Enthält unterschiedliche Geschäftsmodelle und ggf. Versicherungsteile; Netting/Accounting und Konsolidierung beeinflussen das Volumen; nicht alle außerbilanziellen Risiken enthalten |
| TREA | Gesamtbetrag der regulatorischen Risikopositionen als Nenner der risikobasierten Kapitalquoten | Enthält neben Kreditrisiken auch Markt-, operationelle und weitere Risiken; hängt von Risikogewichten, Standard-/IRB-Ansatz, Modellen und regulatorischen Änderungen ab; kein ungewichtetes Geschäftsvolumen |

TREA passt damit besonders zum Vergleich von CET1-/Gesamtkapitalquoten und zur Suche nach ähnlich großen regulatorischen Risikobeständen. Es misst weder den aktuellen Kapitalbestand noch eine universelle wirtschaftliche Bankgröße. Gleiches TREA bei unterschiedlichen Risikogewichten kann stark unterschiedliche Kredit-/Bilanzvolumina bedeuten.

## Konkrete Unterschiede

Werte jeweils aus demselben Report; Mrd. EUR. Der Quotient ist hier tatsächlich TREA/Bilanzsumme, **nicht** die im bestehenden RWA-Dichte-Modul verwendete Größe TREA/Leverage-Exposure.

| Institut | Bilanzsumme | TREA | TREA/Bilanzsumme | Stichtag |
|---|---:|---:|---:|---|
| Euroclear Holding | 226.90 | 15.63 | 6.9% | 2025-12-31 |
| BNG Bank N.V. | 115.56 | 10.32 | 8.9% | 2025-12-31 |
| Stadshypotek AB | 147.47 | 32.50 | 22.0% | 2025-12-31 |
| ING Bank N.V. | 1054.51 | 340.19 | 32.3% | 2025-12-31 |

Euroclear und öffentlich finanzierende Banken können große Vermögensvolumina mit geringer regulatorischer Risikogröße verbinden. Bei Hypothekenbanken wirken Portfolioqualität und regulatorischer Ansatz auf die Risikogewichte. Eine geringe Quote darf nicht allein als Datenfehler oder als Beweis überlegener Sicherheit interpretiert werden. Euroclear gehört nach der früheren Bilanzsummenliste auf Platz 16, nach der hier geprüften TREA-Liste auf Platz 70; Stadshypotek wechselt von 26 auf 45.

## Qualität: TREA löst Währungsprobleme nicht

Der offizielle Bank-Millennium-Halbjahresbericht 2025 nennt im Kapitaladäquanzabschnitt **51.099,26 Mio. PLN** an risikogewichteten Aktiva. Der normalisierte Hub-KM1-Wert lautet **51.106.510.892 EUR**, mit EUR als Quellenwährung und FX = 1. Die Größenordnung passt zu PLN, nicht zur ausgewiesenen EUR-Währung. Zusätzlich besteht eine kleine Betragsabweichung zwischen den beiden Quellen. Deshalb wird der Hub-TREA-Wert hier bis zur Klärung ausgeschlossen und nicht stillschweigend durch einen umgerechneten Geschäftsberichtswert ersetzt.

Der Bericht stammt aus derselben [offiziellen H1-2025-Quelle](https://www.bankmillennium.pl/documents/10184/36276769/Semi-Annual-Report-of-the-Bank-Millennium-Group-1H2025.zip/1d9402c0-348f-8c22-5034-8ca4616b9eac?t=1753764414250), deren Quellhash bereits in `top30_selection.json` gespeichert ist. Passage: „Capital adequacy of the Group was as follows (PLN mn, %, pp): Capital adequacy 30.06.2025 31.12.2024 Risk-weighted assets 51 099.26 45 116.23“. Unveränderte Hub-Zelle: `61.00`, r0040, c0010, CON, 30.06.2025.

TREA aus KM1 lässt sich mit der OV1-Gesamtsumme gegenprüfen: 642 technisch nutzbare Reportpaare, Median-Abweichung 0 %, bei 11 Paaren mehr als 1 % Abweichung. Beide Templates können denselben falschen Währungsbezug übernehmen; Übereinstimmung beweist deshalb allein keine korrekte EUR-Normierung. Die Abweichungen sind Nachprüfungsfälle, keine automatisch korrigierten Daten.

## Empfohlenes Vorgehen

1. **Eigentümerrecherche:** TREA als primäre Priorität nutzen, weil es zur Kapital-/Risikoanalyse passt und wesentlich breiter verfügbar ist. Die bisher recherchierten 30 bleiben wertvoll. Kein erneutes Entfernen ihrer Eigentümerbelege nötig.
2. **Bankgröße im Produkt:** TREA als „regulatorische Risikogröße“ bezeichnen. Für eine Rangliste „größte Banken nach Bilanzvolumen“ weiterhin Bilanzsumme verwenden. Beide Größen dürfen nicht gleich benannt werden.
3. **Peer-Gruppen:** Das bestehende TREA-Merkmal beibehalten. Banktyp, Konzernrolle und Risikomix weiterhin berücksichtigen. Wo verfügbar, Bilanzsumme bzw. ungewichtetes Exposure als zweite Größenachse für eine spätere Sensitivitätsprüfung aufnehmen. TREA/Leverage-Exposure ist dabei eine eigene, breiter verfügbare Größe und kein Ersatz mit dem Namen „TREA/Bilanzsumme“.
4. **Vor einer Modellumstellung:** Gleiche Stichtage/Scopes/Frameworks, IRB-/Standardansatz und fehlende Größen prüfen. Eine zweite Achse kann Geschäftsmodelle besser unterscheiden, aber die Datenabdeckung verkleinern. Ohne gemessenen Nutzen sollten weder neue Gewichte noch ein Ausschluss aller Banken mit fehlender Bilanzsumme eingeführt werden.
5. **Datenqualität:** Bekannte Scale-/Währungsprobleme ausschließen und nachprüfen. Herkunft, verwendeten Stichtag und Qualitätsstatus der Priorität sichtbar halten. Niedrige TREA-Dichte allein ist kein Fehlerkriterium.

Diese Prüfung empfiehlt eine Priorisierung; sie hat weder den Viewer noch das Clusterverfahren geändert. Die Entscheidung zur Umstellung bleibt beim Projektverantwortlichen.

[Messwerte und Beispiele](trea_vs_assets_metrics.json) · [TREA-Rangliste des ursprünglichen Bestands](trea_research_priority_baseline.csv) · [Recherchepriorität der verbleibenden 291 Fälle](trea_research_priority_remaining.csv).
