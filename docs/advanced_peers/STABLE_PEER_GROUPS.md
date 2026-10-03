# Stabile Peergruppen für historische Vergleiche

Die Mitglieder einer Peergruppe werden einmal festgelegt und beim Wechsel zwischen Meldestichtagen nicht neu berechnet. Es entstehen **42 feste Gruppen mit 237 Bank/Konsolidierungskreis-Zuordnungen**, davon **19 Gruppen mit mindestens fünf Banken** (168 Zuordnungen). Das sind keine zusätzlichen Institute oder unabhängige Beobachtungen pro Quartal.

## Festlegung und Zeitvergleich

Jede Bank/Konsolidierungskreis-Kombination wird am jüngsten technisch nutzbaren Stichtag einmal betrachtet. Cluster werden nur mit einem gemeinsamen Referenzstichtag und Framework gebildet. Banken ohne Meldung zum neuesten Stichtag können eine Gruppe am eigenen jüngsten nutzbaren Stichtag erhalten. Bereits betrachtete Banken werden an älteren Stichtagen nicht erneut eingruppiert; isolierte Banken werden nicht durch einen älteren günstigeren Fit aufgefüllt. Die Referenzgruppen stammen aus 2026-03-31 (13), 2025-12-31 (26), 2025-09-30 (2) und 2025-06-30 (1).

Die eingefrorene Mitgliederliste wird über LEI und Konsolidierungskreis auf historische Meldungen angewandt. Fehlende historische Meldungen oder Kennzahlen bleiben fehlend; es werden keine anderen Banken ergänzt. Historische Meldungen benötigen nicht erneut sämtliche Cluster-Eingangsgrößen, um zum festen Vergleichskreis zu gehören. Perzentile verwenden dennoch ausschließlich denselben Stichtag, Konsolidierungskreis und dasselbe aktuelle Melderahmenwerk der verglichenen Meldungen, mit mindestens fünf gültigen Kennzahlwerten. Ein Frameworkwechsel ändert die feste Liste nicht und führt nicht zum Vermischen von RF 4.1 und 4.2 innerhalb eines Perzentils.

Die Mindestgröße fünf bezieht sich auf den vollständigen Referenzkreis. Filter, fehlende Meldungen oder Kennzahlen können den tatsächlich verfügbaren historischen Vergleich unter fünf Werte reduzieren; dann gibt es kein Perzentil. Der zehnfache TREA-Abstand und die Silhouette beschreiben den Referenzfit, nicht jeden historischen Zustand.

## Einordnungen und Methode

Die vorhandenen 256 geprüften Einordnungen werden beibehalten. Für die feste explorative Clusterbildung kommen die 219 Zuordnungen aus dem externen Ergebnis hinzu: 74 vom anderen Agenten als belegt gemeldet, hier nicht unabhängig freigegeben, und 145 Annahmen. Sie stehen separat in `codebook/bank_classification_assumptions.csv`; das geprüfte Register und die Eigentümer-Recherchequeue werden nicht als erledigt umgeschrieben. Im Viewer und CSV-Export sind übernommene/angenommene Einordnungen erkennbar. Im normalen Trägerschaftsmodus gilt weiterhin das geprüfte Register.

Risikoprofil 50 %, logarithmisches TREA 25 %, Trägerschaft 15 %, Konzernrolle 10 %; Complete Linkage, Distanzgrenze 0,25, höchstens zehnfache TREA-Spanne am Referenzstichtag. Vorhandene Konzernidentitäten werden verwendet; unbestätigte externe Mutterangaben verändern sie nicht. Mediane Referenz-Silhouette 0,4638 ist eine explorative Diagnostik, keine unabhängige Validierung der angenommenen Kategorien.

## Eingefrorener Bestand und Aktualisierung

`codebook/stable_peer_groups.json` enthält Listen, Referenzmerkmale, Einordnungsstatus und Quellenfingerprints. Die normale Datenpipeline liest diesen Bestand, ohne ihn neu zu fitten. Fehlende spätere Meldungen ersetzen keine Mitglieder. Eine neue Liste entsteht nur ausdrücklich:

```bash
python scripts/stable_peer_groups.py --refresh
python scripts/build_zweig_a_shards.py
```

Ein Refresh ist eine neue Peergruppen-Version. Zwischen solchen Versionen kann die Zusammensetzung wechseln; innerhalb derselben Veröffentlichung bleibt sie über Meldestichtage stabil. Die aktualisierte Quelle und der eingefrorene Fit sind gesondert nachvollziehbar; Einordnungen sind keine historische Eigentümer-Zeitreihe.

[Mitgliederliste](stable_peer_groups.csv) · [Validierung](stable_peer_groups_validation.json)

**Validierung:** 1.531 Unit-/Datentests bestanden. Zusätzliche Tests prüfen historische und Frameworkwechsel, keine ältere Auffüllung isolierter Banken, Datenverlust ohne Ersatzmitglied, unveränderte geprüfte Einordnungen und Konsistenz zwischen Liste und Mapping. Chromium EN/1280px und DE/390px prüft echte Stichtagswechsel, feste IDs/Mitglieder, Trennung der Perzentilpopulationen, CSV-Herkunftsstatus, Quellen, Filter, geteilte URLs und Fehlerbehandlung; keine JavaScript-Fehler. Pipeline-Abhängigkeiten geprüft. Noch nicht gemergt oder produktiv veröffentlicht.
