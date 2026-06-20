# Phase 0 — Decision-Memo: Zugangsweg, Format, Pilot-Scope

**Stand:** 2026-06-20 · live verifiziert gegen EBA-Website + EDAP-User-Guide.

---

## 1. Zugangsweg (die größte Unbekannte — jetzt geklärt)

**Befund: KEIN Bulk-Export, KEINE öffentliche API. Zugang = report-für-report.**

EDAP (European Data Access Portal) ist eine **Power-BI-basierte Frontend-App** mit zwei
Visualisierungs-Tools (Stand Januar-Go-live):
- **Template Rendering Report** — Templates nach Entity/Module/Template/Row/Column.
- **Data Point Report (DPR)** — granulare Data-Points je Entity–Module–Template.

Zugang öffentlich über *Access to EDAP*: <https://edap-public.eba.europa.eu/Report/index/MTE1>
Kein Login/MFA für das reine Lesen/Herunterladen der öffentlichen Daten erwähnt
(MFA betrifft die meldenden Institute beim Einreichen, nicht die Datennutzung).

### Drei Download-Wege (laut User Guide „EDAP visualisation tools for Pillar 3 reports")

| Weg | Was | Limit | Eignung |
|---|---|---|---|
| **(a) Original-Files** | Pro Submission `.zip` über Spalte *Official Data (Report File)* | keins | **Primärquelle für /raw** |
| (b) Tabellen-Export | Power-BI-Ellipsis-Menü → CSV/XLSX der angezeigten Tabelle | CSV ≤ 30 000 Zeilen, XLSX ≤ 150 000 | nur Ad-hoc, nicht reproduzierbar |
| (c) Bulk | **noch nicht verfügbar** | — | Zukunft: *„Future improvements … should allow for bulk downloads"* |

**Struktur des Original-`.zip`:**
- `META_INF/` — Submission-Metadaten.
- `reports/` — die Original-Templates (XBRL-CSV), Originalinhalt wie eingereicht.
- `parameters`-Excel — u. a. **Originalwährung** (Dashboards zeigen EUR-konvertiert,
  Original-Files können Fremdwährung sein).

### Technische Architektur (live verifiziert per URL-Discovery, 2026-06-20)

EDAP läuft auf der kommerziellen Plattform **„The Reporting Hub"** (.NET, `edap-public.eba.europa.eu`).
Die eigentliche Visualisierung ist ein **eingebetteter Power-BI-Report**:
- `app.powerbi.com/reportEmbed?reportId=f0de0c7c-c532-4b55-9bef-da99423cf672`
  `&groupId=c6c6fd8e-c413-4f0d-87da-502d2e29fa0a`
- Anonymer Zugang funktioniert, **sobald Session-Cookies persistiert werden**
  (`.AspNetCore.ReportingHub` + `.ReportingHub.Session`); ohne Cookie-Jar entsteht
  eine Redirect-Schleife Login ↔ Tenant. Kein Benutzerkonto nötig.
- Die **„Official Data (Report File)"-Download-Links sind Datenwerte IM Power-BI-Dataset**,
  nicht als statische URLs im HTML vorhanden.

### Konsequenz für Ingestion (Phase 1) — kein REST-File-Endpoint

**Reiner HTTP-Client verifiziert NICHT möglich (Discovery 2026-06-20):**
- Embed-Token wird **absichtlich obfuskiert** in einem JS-Store gehalten
  (`window._trh`, `_rk()` erzeugt Zufallsschlüssel) — kein lesbares Token-Feld im HTML.
- `/Report/ExportFile` (server-seitig) = nur zeilenlimitierter Tabellen-Export, braucht
  einen Power-BI-**Bookmark** aus dem *live laufenden* Embed (`GetBookmarkValue`).
- Original-`.zip`-URLs sind Datenwerte im Power-BI-Dataset, nur über das gerenderte
  Visual erreichbar.
- → **Der Token-Store erzwingt eine JS-Runtime.** Ein `requests`-only-Downloader scheitert.

### DURCHBRUCH (Playwright-Recon 2026-06-20): Files liegen unter statischen Public-URLs

Beim Rendern des Power-BI-Embeds (Playwright headless) zeigt die „Official Data
(Report File)"-Spalte **direkte, öffentliche, vorhersagbare URLs** auf einen Blob-Store:

```
https://errp.eba.europa.eu/public-documents/CODIS/input/
   {LEI}.{CON|IND}_{Land}_PILLAR3{Modul}_CODIS_{Stichtag}_{SubmissionTimestamp}.zip
```

Beispiel (verifiziert, HTTP 200, **ohne Cookie/Token**, 44 KB):
`…/input/0W2PZJM8XOY22M4GG883.CON_DE_PILLAR3020000_CODIS_2025-06-30_20260211154609543.zip`

**Folge — Ingestion wird zweistufig und billig:**
1. **Katalog-Harvest (Playwright, selten):** Power-BI-Submissions-Tabelle rendern +
   durchscrollen → alle `errp…zip`-URLs + Metadaten (LEI, CON/IND, Land, Modul,
   Stichtag, Timestamp) ernten → Manifest. Tabelle ist virtualisiert → scrollen nötig.
2. **Download (reines HTTP, schnell, parallelisierbar):** GET je `errp…zip` → `/raw`.
   **Kein Power-BI-Token, kein Headless-Browser für den Download selbst.**

→ Das im Plan befürchtete „Ingestion zäh ohne Bulk" ist **entschärft**: die Files sind
de-facto frei adressierbar; nur die URL-Liste muss einmalig via Power-BI geerntet werden.

Dateiname-Schema (Manifest-Keys direkt ableitbar): `LEI` · Konsolidierung `CON`/`IND` ·
ISO-Land · Modulcode `PILLAR3020000`/`…0100` · `CODIS` · Referenzdatum · Submission-Timestamp.

Start-Katalog (20 sichtbare URLs) bereits geerntet: `interim/edap_recon/zip_urls_visible.txt`.

---

## 2. Format-Realität

- **Quantitativ:** XBRL-CSV (DPM 2.0 / semantisches Dictionary ab RF 4.2).
  Paket = mehrere CSVs, u. a. `parameters.csv`, `filing-indicators.csv`, Daten-CSVs.
- **Qualitativ:** data-extractable PDF-Reports.
- **Framework-Versionen:**
  - RF **4.1** → Referenzdaten bis Dezember 2025.
  - RF **4.2** → ab Referenzdatum ab Dez 2025 / März 2026; **DPM 1.0 entfällt**,
    vollständige Migration auf DPM 2.0 (xBRL-XML → xBRL-CSV abgeschlossen).
  - → Framework-Brücke 4.1↔4.2 für Zeitreihen nötig (Phase 3).

---

## 3. Referenzartefakte (Bezugsquellen, Download offen/„free public good")

| Artefakt | Quelle | Status |
|---|---|---|
| User Guide EDAP visualisation tools | EBA (PDF) | **lokal:** `docs/EBA_UserGuide_EDAP_visualisation_tools.pdf` |
| User Guide (Large & Other Institutions) | EBA (PDF) | URL bekannt, noch nicht geladen |
| DPM Data Dictionary (DPM 2.0, Release 4.0) | <https://www.eba.europa.eu/risk-and-data-analysis/reporting-frameworks/dpm-data-dictionary> | **lokal:** `codebook/DPM2.0_release_4.0_2024-12-10.accdb` (423 MB) + Doku-ZIP |
| `frequency_of_disclosures` (Excel) | EBA P3DH-Seite | zu laden — Disclosure-Pflichten je Institutstyp |
| Mapping-Tool RF 4.1 → 4.2 | EBA | noch zu lokalisieren |
| DPM known issues (Stand 01/06/2026) | EBA P3DH-Seite | zu laden — als Filter/Flag |
| Signposting tool (Excel) | EBA P3DH-Seite | optional |

**Status DPM-Codebook:** DPM 2.0 Release 4.0 (2024-12-10) beschafft. Liegt als Microsoft Access
Database vor; **Codebook-Extraktion (Phase 2) erfordert Access-Reader** (mdb-tools, pyodbc,
oder macOS-externe Maschine). Für RF 4.1 XBRL-CSV keine DPM-1.0-Abhängigkeit bekannt —
alle Sample-Reports nutzen DPM 2.0 Semantik.

---

## 4. Pilot-Scope-Entscheidung

- **EIN Modul:** Eigenmittel/Solvenz — Templates **KM1** (Key Metrics) + **OV1** (RWA-Übersicht).
- **EIN Stichtag:** erster öffentlich verfügbarer Referenzstichtag (RF-Version dabei festhalten).
- **Alle Institute** dieses Moduls/Stichtags.
- **Zweig A zuerst:** einen Report originalgetreu rekonstruieren (Layout + Labels +
  korrekte Größenordnungen) als Lackmustest für Parsing/DPM-Join. Skalierung + Zweig B
  erst danach.

---

## 5. Nächste konkrete Schritte

1. **Sample-Report ziehen:** 1 Original-`.zip` (KM1/OV1) aus EDAP laden → `raw/`.
   Voraussichtlich Browser-Automation (Power-BI-Download) nötig — Chrome MCP.
2. **Paket real inspizieren:** `parameters.csv`, `filing-indicators.csv`, Daten-CSVs,
   `decimals`-Semantik, Originalwährung.
3. **DPM-Version bestätigen** und passende DPM-2.0-Database (RF 4.1/4.2) laden → `codebook/`.
4. Erst dann Parser (Phase 2) gegen reales Format bauen.

## Offene Risiken

- Ingestion ohne Bulk/API ist zäh → Downloader-Strategie (URL-Discovery vs. Browser) ist
  der nächste kritische Entscheid.
- DPM-Mapping fummelig, Codebook wächst iterativ.
- RF 4.1→4.2-Wechsel bricht naive Zeitreihen — früh adressieren.

---

## 6. Phase 0 / 1 Transition: Scope-Split nach Abhängigkeiten

**Phase 0 Deliverables (abgeschlossen 2026-06-20):**
1. ✅ Zugangsweg geklärt: EDAP Power-BI-Embed, aber Files via öffentliche URLs erreichbar
2. ✅ Format inspiziert: XBRL-CSV, DPM 2.0, decimalsMonetary=-6, FilingIndicators
3. ✅ Pilot-Scope: KM1/OV1, 1 Stichtag, alle Institute, Zweig A Priorität
4. ✅ Sample-Report geladen + analysiert: DE, konsolidiert, RF 4.1 codis
5. ✅ DPM 2.0 beschafft: Access-DB lokal, bereit für Phase 2 Codebook-Extraktion

**Phase 1 (Ingestion) — UNABHÄNGIG vom Codebook:**
- Katalog-Harvester (Playwright): EDAP-Submissions-Tabelle durchscrollen → alle
  errp.eba.europa.eu-URLs ernten
- HTTP-Downloader: Manifest + Parallelisierung → alle .zip in `/raw/` + Metadata-CSV
- **Kein DPM-Lookup nötig** — nur Raw-Ingestion

**Phase 2 (Parsing + Codebook) — ABHÄNGIG von DPM-Extraktion:**
- Access-DB auslesen (via mdb-tools / pyodbc / ext. Maschine)
- DPM 2.0 Release 4.0: `dp<n>` → (Template, Zeile/Spalte, Label, Unit) extrahieren
- Codebook CSV aufbauen
- Long-Form-Parser implementieren (XBRL-CSV + Codebook → Long-Form Tidy CSV/Parquet)
- Zweig-A-Renderer: Long-Form → Template-Rekonstruktion XLSX/HTML

**Sequenz:** Phase 1 läuft parallel zur DPM-Extraktion (Phase 2 Prep). Vollständige
Data Science Exploration (Phase 2 fertig) braucht beide.
