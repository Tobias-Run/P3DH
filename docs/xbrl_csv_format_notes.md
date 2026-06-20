# XBRL-CSV-Paketformat — verifizierte Notizen (Sample-Inspektion 2026-06-20)

Basis: 1 realer Report aus `/raw`
(`0W2PZJM8XOY22M4GG883.CON_DE_PILLAR3020000_CODIS_2025-06-30_…zip`, DE, konsolidiert,
Stichtag 2025-06-30). Entpackt nach `interim/sample_DE/`.

## Paketstruktur (xBRL-CSV Report Package 2023)

```
<submission>/
├── META-INF/reportPackage.json     # documentType: xbrl.org/report-package/2023
└── reports/
    ├── report.json                 # Taxonomie-Bindung + Generator-Software
    ├── parameters.csv              # Kontext: Entity, Periode, Währung, decimals
    ├── FilingIndicators.csv        # je Template: reported true/false
    └── k_<NN.NN>[.a|.b|…].csv       # ein CSV je (Template[,Sheet]), Daten
```

## report.json — Taxonomie-Bindung (Framework-Erkennung)

- `documentInfo.extends`: `…/crr/fws/pillar3/4.1/mod/codis.json`
  → **Framework-Version (hier 4.1) und Modul (`codis`) stehen hier**, nicht im Dateinamen
    (Dateiname hat nur `PILLAR3020000`). Für die 4.1↔4.2-Brücke (Phase 3) **diese**
    Quelle nutzen.
- Generator-Software wird mitgeliefert (`eba:generatingSoftwareInformation`, hier
  Regnology) — als Metadatum ins Manifest.

## parameters.csv — Kontext (zwingend fürs Parsing)

| name | Beispielwert | Bedeutung |
|---|---|---|
| `entityID` | `rs:0W2PZJM8XOY22M4GG883.CON` | LEI + Konsolidierungsebene (`.CON`/`.IND`) |
| `refPeriod` | `2025-06-30` | Referenzstichtag |
| `baseCurrency` | `iso4217:EUR` | **Originalwährung** des Reports (kann ≠ EUR sein!) |
| `decimalsMonetary` | `-6` | Genauigkeit monetär: 10^6 = auf Mio genau |
| `decimalsPercentage` | `4` | Genauigkeit Prozent |
| `decimalsInteger` | `0` | — |
| `decimalsDecimal` | `-6` | Genauigkeit sonstige Dezimalwerte |

**Wert-Semantik (kritisch, bestätigt):** factValues stehen in **Währungseinheiten**,
nicht in Tsd/Mio. Beispiel `dp3526977 = 206403359.17` = **€206,4 Mio**. `decimals=-6`
ist nur die *Genauigkeit/Rundung*, kein Skalierungsfaktor. Niemals zusätzlich
multiplizieren.

## FilingIndicators.csv — „fehlt ≠ Null"

- Spalten: `reported,templateID` (z. B. `true,K_03.00` / `false,K_01.00`).
- `false` = Template **nicht offengelegt/eingereicht** → analytisch **NULL/NA**, nicht 0.
- Beobachtung im Sample: **K_01.00 (KM1) = `false`** trotz großer DE-Gruppe →
  für KM1-Pilot ein Institut mit `K_01.00=true` wählen (oder anderes Modul prüfen).
- Mapping Dateiname `k_01.00.csv` ↔ Indicator `K_01.00`: lowercase-Datei, Punkt-Notation;
  Sub-Sheets als `.a/.b/.c…` im Dateinamen, der Indicator gilt für das ganze Template.

## Daten-CSVs `k_<NN.NN>.csv` — der DPM-Join (Kern Phase 2)

- Format: `datapoint,factValue` mit **Datapoint-Codes `dp<nummer>`**
  (z. B. `dp3526977`, `dp456098`). Codes sind kryptisch und template-übergreifend.
- **Auflösung nur über DPM Dictionary:** `dp<n>` → (Template, Zeile/Spalte, Label,
  Datentyp, Einheit, Vorzeichen). Das ist das Codebook (Phase 2, Deliverable).
- Unterschiedliche Code-Größenordnungen (`dp3526977` vs `dp456098`) im selben Paket →
  Datapoints aus verschiedenen DPM-Generationen; DPM-Release muss zur Taxonomie aus
  `report.json` (RF 4.1) passen.

## Offene To-dos für Phase 2

1. **DPM-2.0-Dictionary für RF 4.1 (Modul codis)** beschaffen → `codebook/`. Ohne das
   kein `dp`→Label. **Blocker für Zweig A (menschenlesbarer Report).**
2. Prüfen, wie Zeilen/Spalten-Koordinaten (z. B. KM1 r0010/c0010) im DPM an `dp`-Codes
   hängen — bestimmt die Layout-Rekonstruktion in Zweig A.
3. Währungsfall: Sample ist bereits EUR; ein Nicht-EUR-Report (`baseCurrency≠EUR`) als
   zweiten Testfall ziehen, um die EUR-Normalisierung (Phase 2) real zu prüfen.
