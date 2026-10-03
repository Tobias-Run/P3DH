# Erweiterte Peer-Gruppen und Recherche zur Trägerschaft

Stand: 3. Oktober 2026. Arbeitsstand zu [Issue #134](https://github.com/Tobias-Run/P3DH/issues/134), noch nicht produktiv veröffentlicht. Die Recherche ist **nicht abgeschlossen**. „Noch nicht verifiziert“ bedeutet nicht, dass die Information öffentlich fehlt.

## Stabile historische Peergruppen

[Stabile Peergruppen](STABLE_PEER_GROUPS.md) sind jetzt im Entwurfs-Viewer verfügbar: **42 feste Gruppen, davon 19 mit mindestens fünf Banken**, 237 Bank/Konsolidierungskreis-Zuordnungen. Mitglieder bleiben beim Wechsel des Meldestichtags gleich; Perzentile werden weiterhin innerhalb desselben Stichtags und Frameworks berechnet. Die explorative Referenzbildung verwendet zusätzlich 219 ausdrücklich gekennzeichnete externe Zuordnungen/Annahmen. Der geprüfte Registerstand bleibt 256/475; Annahmen zählen nicht als abgeschlossene Eigentümerrecherche. Gruppen werden nur durch ausdrücklichen Refresh neu gebildet.

## Rechercheergebnis

Von **475 unterschiedlichen Institutskennungen im Viewer** sind **256** mit Quellen eingeordnet: 94 genossenschaftlich, 96 aktionärsgetragen, 31 öffentlich, 15 mit gemischter Trägerschaft, 6 als Gegenseitigkeitsorganisation, 10 mit selbstständiger Sparkassenform und 4 stiftungskontrolliert. **219 benötigen weitere manuelle Prüfung**. Der Viewer hat 476 Institut/Scope-Karten; ein Institut kommt mit mehreren Konsolidierungskreisen vor. Der Registerbestand enthält 293 Einträge, einschließlich zusätzlicher Konzernträger und Katalogeinträge außerhalb des aktuellen Viewers.

Die [Recherche der 30 großen zuvor ungeprüften Institute](TOP30_OWNERSHIP.md) dokumentiert Bilanzsummen, Eigentümeranker, Quellen und Konzernketten. Die Auswahl umfasst die größten 30 unter 192 Fällen mit eindeutiger verfügbarer Bilanzsumme; 129 der ursprünglich 321 offenen Kennungen sind noch nicht priorisierbar. Diese Grenze wird ausdrücklich ausgewiesen.

Die weitere Recherche wird jetzt nach TREA priorisiert: [begrenzter Rechercheablauf](OWNERSHIP_WORKFLOW.md), [aktuelle Warteschlange](ownership_priority.csv) und [Vergleich TREA/Bilanzsumme](TREA_VS_ASSETS.md). Ein erster Cache-Pilot ergänzt Bank of America Europe DAC anhand schon archivierter Primärquellen ohne neue Netzwerkabrufe. [Batch 002](ownership_batches/batch_002.json) ergänzt Eurobank als aktionärsgetragen und Caixa Geral de Depósitos als öffentlich: 18 Quellenversuche, davon 17 neue Abrufe, bei höchstens vier Versuchen pro Bank. Bpifrance, RCI Banque und Crédit Agricole Italia bleiben mit konkreten nächsten Prüfschritten offen. Die Eurobank-Quelle beschreibt eine gestreute Aktionärsstruktur; dynamische Prozentwerte wurden nicht ausgelesen und eine Fairfax-Mehrheitskontrolle wird nicht behauptet. Die CGD-Satzung schreibt ausschließlich staatlichen Aktienbesitz vor.

Die [nächsten 70 TREA-Fälle](NEXT70_OWNERSHIP.md) wurden in den Paketen 003–016 geprüft: **20 neue Belege, 50 gezielte Nachprüfungen**. 235 Quellenversuche, davon 171 neue Abrufe; die übrigen waren Cache-Wiederverwendung. Auch falsch vermutete Seitenpfade (404/410), generische Seiten mit HTTP 200 und blockierte Quellen sind einzeln dokumentiert. Diese begrenzte Prüfung ist keine vollständige Eigentümerklärung aller 70. Der aktuelle Ledger enthält konkrete nächste Schritte. Für zwei norwegische Institute beschreibt `savings` die registrierte R71C-Sparkassenform mit eigentümerlosem Grundkapital; investierbares Eigenkapital über Zertifikate kann daneben bestehen. Das wird nicht auf die ASA-Form der SpareBank 1 Sør-Norge übertragen.

Die [zweite Fortsetzung mit weiteren 70 Instituten](NEXT70B_OWNERSHIP.md), Pakete 017–030, ergänzt **15 belegte Einordnungen**; 55 Fälle bleiben mit konkreten nächsten Quellenprüfungen offen. 128 Quellenversuche, davon 69 neue Netzwerkabrufe. Die aktuelle Eigentümerspalte im Banco-Cooperativo-Bericht wurde von der Vorjahresspalte getrennt; die ukrainische Websitezuordnung zur bulgarischen First Investment Bank wurde im aktuellen Ledger entfernt. Satzungslinks werden jetzt berücksichtigt, irreführende Produkt-/Datenschutzpfade ausgefiltert.

Die [dritte Fortsetzung mit weiteren 70 Instituten](NEXT70C_OWNERSHIP.md), Pakete 031–044, ergänzt **11 belegte Einordnungen**; 59 Fälle bleiben für gezielte Quellen-/Kontrollprüfung offen. 142 Quellenversuche, davon 76 neue Abrufe. Neu belegt sind unter anderem die stimmrechtsbeherrschende Stiftung von Bank Frick, die Mitglieder der Lægernes-Pensionskasse und vier selbständige Sparkassenformen. Coop Pank bleibt wegen der nur ausgewiesenen 41-%-Coop-Beteiligung und ungeklärter Kontrollrechte offen. FESTA wurde einer anderen Bank zugeordnet; ECCM führte zum Domainverkauf. Beide Kandidaten wurden entfernt.

Die [vierte Fortsetzung](NEXT70D_OWNERSHIP.md), Pakete 045–058, umfasst **19 verbleibende Erstprüfungen und 51 ausdrücklich gekennzeichnete Wiederaufnahmen** der größten offenen TREA-Fälle. Zehn dieser 70 Fälle wurden ergänzt, 60 behalten konkrete nächste Prüfungen. Zwei Konzernträger wurden mit aktuellen Eigentümerquellen ergänzt; Erste Group selbst ist eine zusätzliche Viewer-Kennung außerhalb der 70. Damit steigt die Viewer-Abdeckung um elf. 161 Quellenversuche / 76 neue Abrufe. Datierte Originaltabellen von Erste und PZU, Ibercajas vier Stiftungen und BCCs visuell geprüfter 97,41-%-Eigentümerpfeil liefern neue Belege. PPF bleibt wegen AMALAR/PPF-NV-Identitätsunterschieden offen; Piraeus Holdings ist inaktiv. Der unzutreffende ABLV-Kandidat für Atlantic Lux HoldCo wurde entfernt.

Die [fünfte Fortsetzung](NEXT70E_OWNERSHIP.md), Pakete 059–072, prüft **70 gezielte Wiederaufnahmen außerhalb der unmittelbar vorangegangenen Auswahl**. Zwölf belegte Einordnungen, 58 mit konkreten nächsten Schritten offen; sieben zusätzliche Konzernträger außerhalb des Viewers. 107 Quellenversuche / 35 neue Abrufe durch Wiederverwendung archivierter Quellen und selektive verlinkte Originalberichte. Abdeckung 244 → 256/475 (53,9 %), 219 offen. Wüstenrot Deutschland/Österreich unterscheiden sich in Stiftung bzw. Genossenschaft; Bank of China weist staatliche Mehrheitskontrolle nach. Bigbanks tatsächliche Eigentümer ersetzen falsche Suchhypothesen; Sparekassen-Danmark-Satzung visuell geprüft. OBOS-Bankkontrolle ist bankseitig dokumentiert. NIBC-Übernahmevollzug und vdk-Stimmrechte bleiben offen.

Für den gesamten Katalog mit 508 Kennungen wurden GLEIF-Daten gesucht; 505 Datensätze wurden gefunden. Drei Kennungen sind synthetische EBA-Gruppenkennungen. Für 436 der 475 Viewer-Institute wurden Websitekandidaten gefunden. Diese Kandidaten sind Recherchehinweise und kein Identitäts- oder Eigentumsnachweis. Zusätzlich wurden Konzernträger, aktuelle GLEIF-Konsolidierungsbeziehungen, Governance-Seiten und verlinkte Geschäftsberichte geprüft.

Der automatisierte Website-Durchlauf meldete 139 Fälle mit Texttreffern, 128 ohne gefundenen Eigentumspassus und 208 mit Zugriffsfehlern. Diese Zahlen beschreiben **den technischen Suchlauf**, nicht den abschließenden Erkenntnisstand: Navigationstext kann einen Treffer auslösen; eine spätere manuelle Quelle kann trotz eines Crawlfehlers eine Einordnung ermöglichen. HTTP 403, 429, 503, nicht parsebare PDFs und dynamisch geladene Aktionärstabellen sind keine Belege für fehlende öffentliche Informationen. 403-Sperren wurden nicht umgangen.

Die [Rechercheliste](ownership_research.csv) enthält jeden der 475 Fälle, die aktuelle Einordnung, Websitekandidaten, technischen Suchstatus und offene Nachprüfung. Die [kuratierte Klassifikation](../../codebook/bank_classification.csv) enthält Belegpassagen, Quellen, Prüfdatum und Quellhash. Eine automatische Suche nimmt **keine** Klassifikation vor.

## Beispiele aus Primärquellen

| Institut | Einordnung | Begründung und Quelle |
|---|---|---|
| Hypo Tirol | Öffentlich | [100 % im Eigentum des Landes Tirol](https://www.hypotirol.com/ueber-uns/) |
| Hypo Oberösterreich | Öffentlich | [Land Oberösterreich 50,57 %, Raiffeisen-Holding 48,59 %](https://www.hypo.at/de/die-bank/aktionaersstruktur.html) |
| Raiffeisen Bank International | Genossenschaftlich | [Regionale Raiffeisenbanken halten 61,17 %; die Quelle beschreibt die Mitgliedereigentümerschaft der Bankenkette](https://www.rbinternational.com/en/raiffeisen/rbi-group/about-us.html) |
| BPCE | Genossenschaftlich | [Mitglieder besitzen die Bankennetze; Banque Populaire und Caisses d’Épargne halten je 50 % der BPCE](https://www.groupebpce.com/en/the-group/organization/) |
| BiG | Privatwirtschaftlich | [Geschäftsbericht 2025: vollständig privat](https://www.big.pt/pdf/Relatorios/Annual_report_2025.pdf) |
| LGT | Privatwirtschaftlich | [Eigentum der Fürstenfamilie; kein staatlicher Träger](https://www.lgt.com/global-en/about-lgt) |
| Société Générale | Privatwirtschaftlich | [Aktionärstabelle: öffentliches Minderheitsengagement begründet keine öffentliche Kontrolle](https://investors.societegenerale.com/informations-financieres-extra-financieres/action/actionnariat) |
| Forenet Kredit / Nykredit | Gegenseitigkeit | [Demokratische Kreditnehmervereinigung als Mehrheitsaktionär](https://forenetkredit.dk/wp-content/uploads/2025/09/FK_Ejerskabspolitik_A5_160925.pdf) |

## Regeln für eine belastbare Einordnung

- AG, SA oder Börsennotierung allein belegen keine private Kontrolle. Namen und fehlende GLEIF-Mutterangaben begründen ebenfalls keine Trägerschaft.
- Eine registrierte banktypische genossenschaftliche, öffentlich-rechtliche oder norwegische Sparebank-Form ist ein verwendeter Nachweis; der Kontext der juristischen Person muss passen. Die niederländischen Coöperatie-Holdings Promontoria 19 und WP XII Financial Holdings bleiben ungeprüft: ihre Rechtsform belegt kein genossenschaftliches Bankgeschäft.
- Angaben zu Aktionärsanteilen und Stimmrechten werden zusammen gelesen. Öffentliches Minderheitseigentum allein führt nicht zur Kategorie „öffentlich“.
- Eine Einordnung entlang eines Konzerns wird nur als explizit kuratierter Datensatz gespeichert. 77 Übernahmen beruhen auf aktuellen, aktiven, veröffentlichten und vollständig corroborierten GLEIF-Konsolidierungsbeziehungen plus einer belegten Einordnung des Konzernträgers. Elf weitere Einordnungen verwenden explizit geprüfte Bankgeschäftsberichte/SEC-Tochterverzeichnisse (`reviewed_document_chain`) plus Eigentümerquellen des Konzernträgers. Die Laufzeitsoftware vererbt keine Klassifikation automatisch.
- Konsolidierungsbeziehungen sind Belege für Rechnungslegungskontrolle. Sie beschreiben nicht notwendigerweise die vollständige wirtschaftliche Eigentümerkette oder sämtliche gemeinsamen natürlichen Eigentümer. Bekannte Konzernbeziehungen ermöglichen eine konservative Dublettenbereinigung; unbekannte Gruppen bleiben eine Einschränkung.
- Das Prüfdatum beschreibt den **aktuellen Recherchestand**, nicht die historische Trägerschaft an jedem Berichtsstichtag. Eigentümerwechsel wie bei Saxo oder Santander Bank Polska erfordern datierte Nachprüfung; historische Zuordnung ist noch nicht umgesetzt.
- HTML-Tabellen und Fußnoten werden getrennt extrahiert: Bei BNP Paribas darf beispielsweise Fußnote 1 vor 7,1 % nicht zu 17,1 % verschmelzen. Dafür besteht ein Regressionstest.

89 akzeptierte GLEIF-Quelldatensätze sind in [accepted_gleif_records.json](accepted_gleif_records.json), 77 Konsolidierungsbeziehungen in [accepted_control_relationships.json](accepted_control_relationships.json) archiviert. Neue Website-Belegpassagen, Quellenhashes, Kontrollnachweise und Einordnungsbegründungen stehen in [top30_ownership_evidence.json](top30_ownership_evidence.json) sowie den [versionierten Recherchepaketen](ownership_batches). `canonical_gleif_record` bezeichnet SHA-256 des kanonisch serialisierten einzelnen JSON-Datensatzes; `http_response` bezeichnet SHA-256 der damals gelesenen HTTP-Antwort. Websites können sich ändern. Die vollständigen Websiteantworten werden nicht mitgeliefert; deren Hash ist eine Abrufkennung, kein unabhängig reproduzierbarer Archivnachweis. Die zitierte Passage und öffentliche URL bleiben einsehbar.

## Umsetzung im Benchmark

[Desktopansicht (EN)](desktop-en.png) · [Mobilansicht (DE)](mobile-de.png)

Die bestehende Standardgruppe bleibt der Startmodus. Zwei zusätzliche Modi laden eine kleine, hashgeprüfte Datei erst bei Bedarf:

1. **Banktyp:** Vergleich nach Größenklasse, Stichtag, Scope, Framework, Trägerschaft und Konzernrolle. Ungeprüfte Trägerschaft oder Rolle erhält keine Peer-Perzentile.
2. **Cluster:** Statistische Gruppen nach Größe, Risikoaufteilung, Trägerschaft und Rolle. Die Auswahl zeigt Modell, Datenabdeckung und Diagnosewerte.

Pro bekanntem Konzern, Stichtag, Scope und Framework wird eine Repräsentation verwendet. Mindestens fünf gültige Werte je Kennzahl sind für ein Perzentil nötig. Kleine Gruppen werden nicht automatisch erweitert. Quellen und aktuelle Trägerschaft sind im Viewer nachvollziehbar und im erweiterten CSV enthalten; die Auswahl lässt sich als Link teilen. Fehlende oder beschädigte Zusatzdaten zeigen einen Fehler mit Wiederholen und einer ausdrücklichen Rückkehr zur Standardgruppe. Ein nicht mehr verfügbares Cluster wird nicht stillschweigend ersetzt.

## Clusterverfahren und Grenzen

`complete-linkage-gower-caliper-v1`: deterministisches agglomeratives Complete-Linkage mit einer Gower-artigen gemischten Distanz. Es ist eine projektspezifische Distanz, keine unveränderte Standardimplementierung von Gower.

| Merkmal | Gewicht | Behandlung |
|---|---:|---|
| TREA | 25 % | Logarithmus, Normalisierung anhand 5./95. Quantil innerhalb des Fitblocks |
| Fünf OV1-Risikoanteile | 50 % | Mittel der absoluten Differenzen; Kredit, Gegenpartei, CVA, Markt, operationelles Risiko |
| Trägerschaft | 15 % | Gleiche bekannte Kategorie 0, verschiedene 1, ungeprüft 0,5 |
| Konzernrolle | 10 % | Gleiche bekannte Kategorie 0, verschiedene 1, ungeprüft 0,5 |

Fitblocks sind strikt nach Stichtag, Scope und Framework getrennt. Fehlende, widersprüchliche oder ungültige Risikowerte werden nicht durch Null ersetzt. Offene Scale-Befunde in KM1/OV1 schließen einen Bericht aus. Die Risikoanteile müssen nicht 100 % ergeben; überlappende Positionen werden nicht künstlich umverteilt.

Der maximale Abstand innerhalb eines Clusters ist 0,25. Zusätzlich darf das Verhältnis größter/kleinster TREA **10 nicht überschreiten**. Die reale Prüfung hatte zuvor Gruppen mit fast 27-facher Größenstreuung gezeigt; identische Risikomuster dürfen diesen Größenunterschied nicht vollständig kompensieren. Isolierte Institute bleiben ohne Cluster; die Clusteranzahl wird nicht erzwungen.

**Kapital- und Liquiditätsquoten sind keine Fitmerkmale.** Für TREA und Risikoanteile werden im Clustermodus keine Perzentile/Ausreißerränge gezeigt, weil deren Einordnung sonst durch die Gruppenbildung vorgegeben wäre. Die vorhandenen Kapital-/Liquiditätsvergleiche können dagegen explorativ genutzt werden.

Die Schwellenwerte 0,20/0,30 liefern eine Nachbarschafts-Jaccard-Sensitivität. Das ist keine Bootstrap-Stabilität oder Wahrscheinlichkeit. Silhouette beschreibt die Trennung im gewählten Modell, nicht die fachliche Validierung eines Bankgeschäftsmodells. TREA und Risikoanteile erfassen beispielsweise Finanzierung, Kundensegmente, Ertragsmodell und regionale Marktstruktur nur unvollständig. Die Gewichte und der 10-fache Größenrahmen sind transparente Ausgangsannahmen, keine empirisch belegten Optimalwerte.

## Messung und Tests

[Messwerte](data_validation.json): 529 Berichte haben vollständige Fitdaten, 353 sind ausgeschlossen; 84 Konzernrepräsentationsdubletten werden nicht gefittet. Es entstehen 67 Cluster, davon 43 mit mindestens fünf Mitgliedern. Größte tatsächliche TREA-Spanne: **9,57-fach**. Median der definierten Cluster-Silhouetten: **0,3458**; die Trennung ist mäßig und rechtfertigt noch keine pauschale Aussage „bessere Peers“. Vor den Paketen 045–058 lag der Wert bei 0,3542; die Veränderung durch zusätzliche Einordnungen ist eine Modelldiagnose, kein unabhängiger Nachweis einer besseren Nutzerentscheidung.

- 1.531 Unit-/Datentests bestanden, einschließlich fehlender Werte, Dimensionenkonflikte, Scale-Ausschlüsse, Frameworkgrenzen, Größe, Konzernbereinigung, Quellpflicht und Collectorfehlern.
- Echte Chromium-Prüfung bei 1280 px/Englisch und 390 px/Deutsch: Filter, Perzentile, CSV, Quellen, Sprachwechsel, geteilte Links, Neuladen, Risikoansicht, veraltetes Cluster, fehlende Datei und ältere Veröffentlichung ohne Manifest; keine JavaScript-Fehler.
- Standardstart lädt die Zusatzdatei nicht; die bisherige Standard-Perzentilberechnung bleibt gleich.
- Reale Artefakte geprüft auf disjunkte Mitgliedschaften, Datums-/Scopegrenzen, Konzernbereinigung, maximale Distanz, Größenrahmen sowie Quell- und Manifesthashes.
- Pipeline-Reihenfolge: 62 Abhängigkeiten überprüft, gültige Topologie.

## Offene Arbeit vor einer vollständigen Trägerschaftsabdeckung

Die 219 offenen Institutsfälle einzeln anhand verifizierter Bankidentität und offizieller Eigentümer-/Stimmrechtsquellen abarbeiten. Dynamische Aktionärstabellen und blockierte Websites erfordern alternative offizielle Berichte oder Register. Weitere Trägerketten müssen bis zur tatsächlichen Kontrolle geprüft werden. Insbesondere sind genossenschaftliche Holding-Rechtsformen, Stiftungen, selbstständige Sparkassen und historische Eigentümerwechsel keine pauschalen Kategorien.

Issue #134 bleibt offen. Dieser Stand ist ein überprüfbarer Entwurf mit belastbaren Teilbelegen und getesteter Funktion; vollständige Recherche und fachliche Modellvalidierung stehen aus.
