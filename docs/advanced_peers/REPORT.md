# Erweiterte Peer-Gruppen und Recherche zur Trägerschaft

Stand: 2. Oktober 2026. Arbeitsstand zu [Issue #134](https://github.com/Tobias-Run/P3DH/issues/134), noch nicht produktiv veröffentlicht. Die Recherche ist **nicht abgeschlossen**. „Noch nicht verifiziert“ bedeutet nicht, dass die Information öffentlich fehlt.

## Rechercheergebnis

Von **475 unterschiedlichen Institutskennungen im Viewer** sind **184** mit Quellen eingeordnet: 86 genossenschaftlich, 62 aktionärsgetragen, 25 öffentlich, 7 mit gemischter Trägerschaft und 4 als Gegenseitigkeitsorganisation. **291 benötigen weitere manuelle Prüfung**. Der Viewer hat 476 Institut/Scope-Karten; ein Institut kommt mit mehreren Konsolidierungskreisen vor. Der Registerbestand enthält 212 Einträge, einschließlich zusätzlicher Konzernträger und Katalogeinträge außerhalb des aktuellen Viewers.

Die [Recherche der 30 großen zuvor ungeprüften Institute](TOP30_OWNERSHIP.md) dokumentiert Bilanzsummen, Eigentümeranker, Quellen und Konzernketten. Die Auswahl umfasst die größten 30 unter 192 Fällen mit eindeutiger verfügbarer Bilanzsumme; 129 der ursprünglich 321 offenen Kennungen sind noch nicht priorisierbar. Diese Grenze wird ausdrücklich ausgewiesen.

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
- Eine registrierte banktypische genossenschaftliche oder öffentlich-rechtliche Form ist ein verwendeter Nachweis; der Kontext der juristischen Person muss passen. Die niederländischen Coöperatie-Holdings Promontoria 19 und WP XII Financial Holdings bleiben ungeprüft: ihre Rechtsform belegt kein genossenschaftliches Bankgeschäft.
- Angaben zu Aktionärsanteilen und Stimmrechten werden zusammen gelesen. Öffentliches Minderheitseigentum allein führt nicht zur Kategorie „öffentlich“.
- Eine Einordnung entlang eines Konzerns wird nur als explizit kuratierter Datensatz gespeichert. 55 Übernahmen beruhen auf aktuellen, aktiven, veröffentlichten und vollständig corroborierten GLEIF-Konsolidierungsbeziehungen plus einer belegten Einordnung des Konzernträgers. Vier weitere Einordnungen verwenden explizit geprüfte Bankgeschäftsberichte/SEC-Tochterverzeichnisse (`reviewed_document_chain`) plus Eigentümerquellen des Konzernträgers. Die Laufzeitsoftware vererbt keine Klassifikation automatisch.
- Konsolidierungsbeziehungen sind Belege für Rechnungslegungskontrolle. Sie beschreiben nicht notwendigerweise die vollständige wirtschaftliche Eigentümerkette oder sämtliche gemeinsamen natürlichen Eigentümer. Bekannte Konzernbeziehungen ermöglichen eine konservative Dublettenbereinigung; unbekannte Gruppen bleiben eine Einschränkung.
- Das Prüfdatum beschreibt den **aktuellen Recherchestand**, nicht die historische Trägerschaft an jedem Berichtsstichtag. Eigentümerwechsel wie bei Saxo oder Santander Bank Polska erfordern datierte Nachprüfung; historische Zuordnung ist noch nicht umgesetzt.
- HTML-Tabellen und Fußnoten werden getrennt extrahiert: Bei BNP Paribas darf beispielsweise Fußnote 1 vor 7,1 % nicht zu 17,1 % verschmelzen. Dafür besteht ein Regressionstest.

85 akzeptierte GLEIF-Quelldatensätze sind in [accepted_gleif_records.json](accepted_gleif_records.json), 55 Konsolidierungsbeziehungen in [accepted_control_relationships.json](accepted_control_relationships.json) archiviert. Neue Website-Belegpassagen, Quellenhashes, Kontrollnachweise und Einordnungsbegründungen stehen in [top30_ownership_evidence.json](top30_ownership_evidence.json). `canonical_gleif_record` bezeichnet SHA-256 des kanonisch serialisierten einzelnen JSON-Datensatzes; `http_response` bezeichnet SHA-256 der damals gelesenen HTTP-Antwort. Websites können sich ändern. Die vollständigen Websiteantworten werden nicht mitgeliefert; deren Hash ist eine Abrufkennung, kein unabhängig reproduzierbarer Archivnachweis. Die zitierte Passage und öffentliche URL bleiben einsehbar.

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

[Messwerte](data_validation.json): 529 Berichte haben vollständige Fitdaten, 353 sind ausgeschlossen; 84 Konzernrepräsentationsdubletten werden nicht gefittet. Es entstehen 58 Cluster, davon 38 mit mindestens fünf Mitgliedern. Größte tatsächliche TREA-Spanne: **8,68-fach**. Median der definierten Cluster-Silhouetten: **0,3542**; die Trennung ist mäßig und rechtfertigt noch keine pauschale Aussage „bessere Peers“. Der vorherige Stand lag bei 0,2873; der Anstieg durch zusätzliche Einordnungen ist eine Modelldiagnose, kein unabhängiger Nachweis einer besseren Nutzerentscheidung.

- 1.503 Unit-/Datentests bestanden, einschließlich fehlender Werte, Dimensionenkonflikte, Scale-Ausschlüsse, Frameworkgrenzen, Größe, Konzernbereinigung, Quellpflicht und Collectorfehlern.
- Echte Chromium-Prüfung bei 1280 px/Englisch und 390 px/Deutsch: Filter, Perzentile, CSV, Quellen, Sprachwechsel, geteilte Links, Neuladen, Risikoansicht, veraltetes Cluster, fehlende Datei und ältere Veröffentlichung ohne Manifest; keine JavaScript-Fehler.
- Standardstart lädt die Zusatzdatei nicht; die bisherige Standard-Perzentilberechnung bleibt gleich.
- Reale Artefakte geprüft auf disjunkte Mitgliedschaften, Datums-/Scopegrenzen, Konzernbereinigung, maximale Distanz, Größenrahmen sowie Quell- und Manifesthashes.
- Pipeline-Reihenfolge: 62 Abhängigkeiten überprüft, gültige Topologie.

## Offene Arbeit vor einer vollständigen Trägerschaftsabdeckung

Die 291 offenen Institutsfälle einzeln anhand verifizierter Bankidentität und offizieller Eigentümer-/Stimmrechtsquellen abarbeiten. Dynamische Aktionärstabellen und blockierte Websites erfordern alternative offizielle Berichte oder Register. Weitere Trägerketten müssen bis zur tatsächlichen Kontrolle geprüft werden. Insbesondere sind genossenschaftliche Holding-Rechtsformen, Stiftungen, selbstständige Sparkassen und historische Eigentümerwechsel keine pauschalen Kategorien.

Issue #134 bleibt offen. Dieser Stand ist ein überprüfbarer Entwurf mit belastbaren Teilbelegen und getesteter Funktion; vollständige Recherche und fachliche Modellvalidierung stehen aus.
