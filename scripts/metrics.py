"""Kuratierte Kennzahlen-Registry (#63, erster Teil von #25).

Der Überblick zeigte acht Zahlen ohne Erklärung. Wer nicht weiß, was eine NSFR
ist, erfuhr es dort nicht — und ob 12,6 % CET1 viel oder wenig ist, schon gar
nicht.

Diese Registry trägt zu jeder Kennzahl **Definition, Zweck, Schwelle und
Herkunft**. Sie wird von `build_zweig_a_shards.py` nach `codebook.json`
geschrieben; der Viewer liest sie und führt keine zweite Liste — dasselbe
Muster wie `template_themes.py`.

## Eine Registry für Überblick UND Benchmark (#25)

Zuerst deckte sie nur die acht Überblickskarten ab, während `BM_PROFILES` im
Viewer dieselben Kennzahlen ein zweites Mal definierte — die NPL-Quote stand an
drei Stellen. Jetzt führt sie **alle** Kennzahlen beider Ansichten, und die
Profile sind eine Reihenfolge von `id`s.

Die Rechenvorschrift steht **deklarativ** in `op`, nicht als Code:

    cell          eine gemeldete Zelle; `kind` entscheidet die Skalierung
    diff          cells[0] − cells[1]      (Headroom TC−OCR)
    share         cells[0] / cells[1]      (ESG- und OV1-Anteile)
    npl           cells[0] / (cells[0] + cells[1])
    shareOfSum    cells[0] / (cells[1] + cells[2])   (#16, Vorstufe)
    deckung       |cells[0]| / cells[1]               (#16, Deckungsquote)

Die letzten beiden kamen mit der Kreditverschlechterungs-Kette (#16) dazu, und
beide mussten es sein, damit Viewer und `credit_chain.csv` **dieselbe** Zahl
zeigen:

- Die Forbearance-Quote bezieht sich auf den GESAMTBESTAND, also auf die Summe
  aus bedient und notleidend. Mit `share` liesse sich nur ein einzelner Nenner
  ansprechen; die Quote auf die bedienten Kredite allein zu beziehen wäre eine
  zweite, abweichende Definition derselben Kennzahl — genau die Doppelung, vor
  der #25 warnt.
- Die Wertberichtigung wird **uneinheitlich vorzeichenbehaftet** gemeldet: 344
  von 364 Reports negativ, 20 positiv. `deckung` rechnet deshalb mit dem
  Betrag, wie `build_credit_chain.py` auch. Mit `share` wären 94 % der
  Deckungsquoten negativ.

Die Anteile am Gesamtrisikobetrag waren zuerst eine eigene Form, die den Nenner
(KM1 r0040) im Code versteckte. Sichtbar wurde das an der Herleitung: sie zeigte
eine einzige Zelle und schrieb darunter „hier wird nichts gerechnet", während
die Karte einen Prozentwert auswies. Jetzt steht der Nenner als zweite
Quellzelle da, wo er hingehört — und `share` genügt.

Der Viewer wertet diese vier Formen generisch aus. Damit gibt es keine
Kennzahl mehr, die an zwei Stellen definiert ist — genau die Doppelung, vor
der #25 warnt.

## Die Schwellen — der heikle Teil

Es gibt **zwei** Arten von Schwelle, und sie zu vermengen wäre irreführend:

1. **Pillar-1-Mindestanforderung.** Feste Rechtsgröße, für alle gleich
   (CRR Art. 92 usw.). Die darf angeschrieben werden, mit Fundstelle.
2. **Die tatsächlich bindende Anforderung ist institutsspezifisch** — Säule-2-
   Aufschlag plus kombinierte Pufferanforderung. Sie steht **im Report selbst**:
   KM1 r0190 „EU 11a. Overall capital requirements (%)". Eine Bank mit 12 %
   CET1 kann komfortabel oder knapp dastehen; das entscheidet ihr OCR, nicht
   die 4,5 %.

Deshalb trägt jede Kapitalkennzahl **beides**: `floor` (gesetzlicher Boden) und
`own_req` (die Koordinate der gemeldeten eigenen Anforderung). Nur den
Pillar-1-Wert zu zeigen wäre die schlechtere Hälfte der Wahrheit — er wird
praktisch nie zur bindenden Grenze.

Wo es **keine** Schwelle gibt, steht keine. Für die NPL-Quote existiert keine
aufsichtliche Grenze; die oft zitierten 5 % stammen aus den EBA-Leitlinien zum
Management notleidender Risikopositionen und lösen dort eine NPE-Strategie aus.
Das ist ein Auslöser, keine Grenze — und es steht als `note` dabei, nicht als
Linie.
"""


# `cells`: (template, row, col, rolle). Die Rolle benennt den Platz in der
# Formel und beschriftet die Herleitung im Viewer.
# `op`: cell | diff | share | npl | shareOfTrea  (siehe Modul-Docstring)
# `kind`: pct (Quote*100, Ausreisserschutz) | eur (Mrd, EZB-Kurs) | ratio | pp
# `ov`: True -> erscheint als Karte im Ueberblick
# `en`/`syn`: fuer die Kennzahlensuche

_KM1 = "61.00"
_OV1 = "60.00.A"
_CQ3 = "82.00.A"
_ESG = "41.00"
_REM = "30.01"
_CQ1 = "80.00.A"      # Gestundete Forderungen (forborne) — die Vorstufe
_CR1 = "21.01.D"      # Wertberichtigungen — Nenner der Deckungsquote

# Plausibilitätskorridor für "Vergütung pro identifiziertem Mitarbeiter", in EUR.
# EINE Definition für zwei Verwender: `check_plausibility.RATIO_RULES` prüft
# damit den Bestand, der Viewer schließt damit Meldungen aus der Rangliste aus
# (#18). Zwei Zahlenpaare an zwei Orten wären genau die Doppelung, die #25
# beseitigt hat — und hier wäre sie gefährlich: eine Rangliste, die nach einem
# anderen Korridor filtert als der, gegen den geprüft wurde.
#
# Beobachtet über 1.784 Paare: p25 46.500 · Median 142.516 · p75 305.537 EUR.
# Der Korridor ist bewusst weit ausserhalb dieser Perzentile gewählt: unten
# deckt er geringfügige Aufsichtsratsvergütungen ab, oben die höchstbezahlten
# Banker Europas. Was darunter oder darüber liegt, ist keine Gehaltsfrage mehr,
# sondern eine Einheitenfrage.
REM_PER_HEAD = (1_000.0, 20_000_000.0)

# Funktionsstufen in REM1: die vier Spalten des Templates.
_MB_SB, _MB_MB, _SM, _OT = "0010", "0020", "0030", "0040"

_REM_NOTE = (
    "**Keine Schwelle, und keine Gehaltsstatistik.** „Identified staff“ ist eine "
    "aufsichtliche Teilmenge (CRD Art. 92 (3)) — nicht die Belegschaft. Teilzeit "
    "und unterjährige Zu- und Abgänge sind nicht bereinigt, ein Kopf ist also "
    "nicht zwingend ein volles Jahr. Und der Konsolidierungskreis (CON/IND) "
    "entscheidet mit, wessen Vergütung überhaupt mitgezählt wird."
)
_OCR = [_KM1, "0190", "0010"]

# Gemeinsamer Hinweis der fünf OV1-Anteile. Zwei Dinge, die man dem Prozentwert
# nicht ansieht und die beide zu Fehlschlüssen einladen.
_SH_NOTE = (
    "Zusammensetzung, keine Anforderung: eine Schwelle gibt es nicht. Der "
    "Nenner ist der Gesamtrisikobetrag aus KM1 r0040 **derselben Meldung** — "
    "Zähler und Nenner stammen also aus einem Report. Die hier gezeigten fünf "
    "Kategorien ergeben zusammen **nicht** 100 %: OV1 führt weitere Zeilen "
    "(u. a. Abwicklungs-, Verbriefungs- und Großkreditrisiken im Handelsbuch), "
    "die dieses Profil nicht ausweist."
)

METRICS = [
    # ---- Kapital: Quoten aus KM1 ---------------------------------------
    {
        "id": "cet1", "label": "CET1-Quote", "en": "CET1 ratio", "unit": "%",
        "syn": ["hartes Kernkapital", "Common Equity Tier 1", "Kernkapitalquote"],
        "op": "cell", "kind": "pct", "ov": True,
        "cells": [[_KM1, "0050", "0010", "wert"]],
        "definition": "Hartes Kernkapital (CET1) im Verhältnis zum "
                      "Gesamtrisikobetrag (TREA).",
        "purpose": "Die zentrale Solvenzkennzahl: wie viel verlustabsorbierendes "
                   "Eigenkapital höchster Qualität steht hinter den gewichteten "
                   "Risiken?",
        "floor": 4.5, "floor_src": "CRR Art. 92 (1) (a) — Säule-1-Mindestquote",
        # BEWUSST kein `own_req`: KM1 r0190 ist die Anforderung an die
        # GESAMTkapitalquote. Neben die CET1-Quote gestellt suggeriert sie eine
        # Unterdeckung, wo keine ist — bei BNP Paribas 12,6 % CET1 gegen
        # 14,7 % OCR.
        "note": "Die für dieses Institut bindende CET1-Anforderung steht **nicht** "
                "als eine Zahl in KM1: sie setzt sich aus dem Säule-1-Boden, dem "
                "CET1-Anteil des Säule-2-Aufschlags und der kombinierten "
                "Pufferanforderung zusammen. Die gemeldete Gesamtanforderung "
                "(r0190) bezieht sich auf die **Gesamtkapitalquote** und gehört "
                "dorthin — siehe „Gesamtkapitalquote“ und „Headroom TC−OCR“.",
    },
    {
        "id": "t1", "label": "T1-Quote", "en": "Tier 1 ratio", "unit": "%",
        "syn": ["Kernkapital", "Tier 1"],
        "op": "cell", "kind": "pct",
        "cells": [[_KM1, "0060", "0010", "wert"]],
        "definition": "Kernkapital (CET1 + zusätzliches Kernkapital) im "
                      "Verhältnis zum Gesamtrisikobetrag.",
        "purpose": "Zeigt im Abstand zur CET1-Quote, wie stark ein Institut auf "
                   "AT1-Instrumente setzt — Kapital, das im laufenden Betrieb "
                   "haftet, aber erst nach dem harten Kernkapital.",
        "floor": 6.0, "floor_src": "CRR Art. 92 (1) (b) — Säule-1-Mindestquote",
    },
    {
        "id": "tc", "label": "Gesamtkapitalquote", "en": "Total capital ratio",
        "unit": "%", "syn": ["Eigenmittelquote", "Total capital", "Gesamtkapital"],
        "op": "cell", "kind": "pct", "ov": True,
        "cells": [[_KM1, "0070", "0010", "wert"]],
        "definition": "Gesamte Eigenmittel (CET1 + AT1 + Ergänzungskapital) im "
                      "Verhältnis zum Gesamtrisikobetrag.",
        "purpose": "Die weiteste Kapitalkennzahl — sie zählt auch nachrangige "
                   "Instrumente mit, die erst später als CET1 haften.",
        "floor": 8.0, "floor_src": "CRR Art. 92 (1) (c) — Säule-1-Mindestquote",
        # Hier passt r0190: die gemeldete Gesamtanforderung bezieht sich genau
        # auf diese Quote. Die einzige Karte mit zulässigem Direktvergleich.
        "own_req": _OCR,
    },
    {
        "id": "ocr", "label": "Gesamtanforderung (OCR)",
        "en": "Overall capital requirement", "unit": "%",
        "syn": ["OCR", "SREP", "Kapitalanforderung", "Pufferanforderung"],
        "op": "cell", "kind": "pct",
        "cells": [[_KM1, "0190", "0010", "wert"]],
        "definition": "Die für dieses Institut geltende Gesamtanforderung an die "
                      "Gesamtkapitalquote — Säule-1-Boden, Säule-2-Aufschlag und "
                      "kombinierte Pufferanforderung zusammen.",
        "purpose": "Die Zahl, gegen die sich die Gesamtkapitalquote wirklich "
                   "messen muss. Sie ist institutsspezifisch — deshalb sagt der "
                   "Vergleich zweier Institute anhand des Säule-1-Bodens allein "
                   "wenig.",
        "note": "Das ist eine **Anforderung**, keine Schwelle für sich selbst. "
                "In RF 4.2 auf einen neuen Datenpunkt umgebunden (#26).",
    },
    {
        "id": "hr", "label": "Headroom TC−OCR", "en": "Headroom to overall requirement",
        "unit": "pp", "syn": ["Puffer", "Abstand zur Anforderung", "Headroom"],
        "op": "diff", "kind": "pp", "ov": True,
        "cells": [[_KM1, "0070", "0010", "gesamtkapitalquote"],
                  [_KM1, "0190", "0010", "gesamtanforderung"]],
        "formula": "gesamtkapitalquote − gesamtanforderung",
        "definition": "Abstand der Gesamtkapitalquote zur Gesamtanforderung "
                      "dieses Instituts (OCR), in Prozentpunkten.",
        "purpose": "Die einzige Kapitalzahl im Überblick, die die "
                   "institutsspezifische Anforderung einbezieht statt des "
                   "gesetzlichen Bodens. Sie sagt, wie viel Luft wirklich da ist.",
        "floor": 0.0,
        "floor_src": "kein Rechtswert — bei 0 pp ist die eigene Gesamtanforderung "
                     "genau erfüllt",
        "note": "Beide Größen stammen aus demselben Template und derselben "
                "Meldung, kürzen sich also sauber. Die Gesamtanforderung ist in "
                "RF 4.2 auf einen neuen Datenpunkt umgebunden — Vergleiche über "
                "den Versionswechsel mit Vorbehalt (#26).",
    },
    {
        "id": "cet1_srep", "label": "CET1 nach SREP verfügbar",
        "en": "CET1 available after SREP", "unit": "%",
        "syn": ["freies CET1", "SREP"],
        "op": "cell", "kind": "pct",
        "cells": [[_KM1, "0200", "0010", "wert"]],
        "definition": "Anteil des harten Kernkapitals, der nach Erfüllung der "
                      "SREP-Eigenmittelanforderung noch zur Verfügung steht.",
        "purpose": "Der vom Institut selbst gemeldete Spielraum — ein zweiter, "
                   "unabhängiger Blick auf dasselbe wie „Headroom TC−OCR“, nur "
                   "auf CET1-Ebene und ohne die Pufferanforderung.",
        "note": "Größe ohne eigene Schwelle: die Anforderung, gegen die hier "
                "gerechnet wurde, steckt bereits im Wert.",
    },
    {
        "id": "lev", "label": "Verschuldungsquote", "en": "Leverage ratio",
        "unit": "%", "syn": ["Leverage", "Leverage Ratio", "Verschuldung"],
        "op": "cell", "kind": "pct", "ov": True,
        "cells": [[_KM1, "0220", "0010", "wert"]],
        "definition": "Kernkapital (T1) im Verhältnis zur Gesamtrisikoposition "
                      "der Verschuldungsquote — einer **ungewichteten** "
                      "Bezugsgröße.",
        "purpose": "Rückfalllinie gegen Modellrisiko: Sie ignoriert die "
                   "Risikogewichtung und fängt damit genau die Fälle, in denen "
                   "die gewichteten Quoten zu günstig aussehen.",
        "floor": 3.0, "floor_src": "CRR Art. 92 (1) (d) — Säule-1-Mindestquote",
    },
    # ---- Liquidität ------------------------------------------------------
    {
        "id": "lcr", "label": "LCR", "en": "Liquidity coverage ratio", "unit": "%",
        "syn": ["Liquiditätsdeckungsquote", "Liquidity Coverage Ratio", "Liquidität"],
        "op": "cell", "kind": "pct", "ov": True,
        "cells": [[_KM1, "0320", "0010", "wert"]],
        "definition": "Liquiditätsdeckungsquote: hochliquide Aktiva im "
                      "Verhältnis zu den Nettomittelabflüssen eines "
                      "30-Tage-Stressszenarios.",
        "purpose": "Übersteht das Institut einen Monat akuten Liquiditätsstress "
                   "aus eigener Kraft?",
        "floor": 100.0,
        "floor_src": "Delegierte Verordnung (EU) 2015/61 — Mindestquote 100 %",
    },
    {
        "id": "nsfr", "label": "NSFR", "en": "Net stable funding ratio", "unit": "%",
        "syn": ["strukturelle Liquiditätsquote", "Net Stable Funding Ratio",
                "Refinanzierung"],
        "op": "cell", "kind": "pct", "ov": True,
        "cells": [[_KM1, "0350", "0010", "wert"]],
        "definition": "Strukturelle Liquiditätsquote: verfügbare stabile "
                      "Refinanzierung im Verhältnis zur erforderlichen, über "
                      "einen Einjahreshorizont.",
        "purpose": "Das Gegenstück zur LCR auf lange Sicht — passt die "
                   "Fristigkeit der Refinanzierung zur Fristigkeit des Geschäfts?",
        "floor": 100.0, "floor_src": "CRR Art. 428b — Mindestquote 100 %",
    },
    {
        "id": "hqla", "label": "HQLA", "en": "High quality liquid assets",
        "unit": "Mrd EUR", "syn": ["liquide Aktiva", "Liquiditätspuffer"],
        "op": "cell", "kind": "eur",
        "cells": [[_KM1, "0280", "0010", "wert"]],
        "definition": "Bestand an hochliquiden Aktiva — der Zähler der LCR.",
        "purpose": "Trennt die beiden Wege zu einer hohen LCR: ein großer Puffer "
                   "ist etwas anderes als geringe erwartete Abflüsse.",
        "note": "Größe, keine Anforderung: eine Schwelle gibt es nicht.",
    },
    {
        "id": "outflow", "label": "Netto-Abflüsse", "en": "Net cash outflows",
        "unit": "Mrd EUR", "syn": ["Mittelabflüsse", "Abflüsse"],
        "op": "cell", "kind": "eur",
        "cells": [[_KM1, "0310", "0010", "wert"]],
        "definition": "Gesamte Netto-Zahlungsmittelabflüsse im 30-Tage-Szenario — "
                      "der Nenner der LCR.",
        "purpose": "Das Stressszenario in einer Zahl: wie viel Liquidität das "
                   "Institut binnen 30 Tagen als abfließend unterstellt.",
        "note": "Größe, keine Anforderung: eine Schwelle gibt es nicht.",
    },
    {
        "id": "asf", "label": "Verfügbare stabile Mittel",
        "en": "Available stable funding", "unit": "Mrd EUR",
        "syn": ["stabile Refinanzierung", "ASF"],
        "op": "cell", "kind": "eur",
        "cells": [[_KM1, "0330", "0010", "wert"]],
        "definition": "Verfügbare stabile Refinanzierung — der Zähler der NSFR.",
        "purpose": "Der langfristig belastbare Teil der Refinanzierung. Zusammen "
                   "mit der NSFR zeigt er, ob eine gute Quote aus viel stabiler "
                   "Refinanzierung oder aus wenig langfristigem Geschäft kommt.",
        "note": "Größe, keine Anforderung: eine Schwelle gibt es nicht.",
    },
    # ---- Größen ----------------------------------------------------------
    {
        "id": "trea", "label": "TREA", "en": "Total risk exposure amount",
        "unit": "Mrd EUR", "syn": ["Gesamtrisikobetrag", "RWA", "risikogewichtete Aktiva"],
        "op": "cell", "kind": "eur", "ov": True,
        "cells": [[_KM1, "0040", "0010", "wert"]],
        "definition": "Gesamtrisikobetrag: die Summe aller risikogewichteten "
                      "Positionsbeträge, umgerechnet zum EZB-Referenzkurs.",
        "purpose": "Der Nenner der Kapitalquoten und zugleich das gebräuchlichste "
                   "Größenmaß — er macht die übrigen Quoten erst einordenbar.",
        "note": "Größe, keine Anforderung: eine Schwelle gibt es nicht.",
    },
    {
        "id": "cet1_amt", "label": "CET1-Kapital", "en": "CET1 capital",
        "unit": "Mrd EUR", "syn": ["hartes Kernkapital", "Eigenkapital"],
        "op": "cell", "kind": "eur",
        "cells": [[_KM1, "0010", "0010", "wert"]],
        "definition": "Hartes Kernkapital als Betrag — der Zähler der CET1-Quote.",
        "purpose": "Zerlegt die CET1-Quote in ihre beiden Ursachen: eine hohe "
                   "Quote kann aus viel Kapital oder aus wenig gewichtetem Risiko "
                   "kommen. Erst mit dem TREA daneben wird sie lesbar.",
        "note": "Größe, keine Anforderung: eine Schwelle gibt es nicht.",
    },
    # ---- Risikoprofil: Anteile am Gesamtrisikobetrag (OV1) ---------------
    {
        "id": "sh_credit", "label": "Kreditrisiko", "en": "Credit risk", "unit": "%",
        "syn": ["Kreditrisiko-Anteil", "credit risk"],
        "op": "share", "kind": "shareOfTrea",
        "cells": [[_OV1, "0010", "0010", "Risikobetrag der Kategorie"],
                  [_KM1, "0040", "0010", "Gesamtrisikobetrag"]],
        "formula": "Risikobetrag der Kategorie / Gesamtrisikobetrag",
        "definition": "Anteil des Kreditrisikos (ohne Gegenparteiausfallrisiko) "
                      "am Gesamtrisikobetrag.",
        "purpose": "Der Kern des Geschäftsmodells in einer Zahl: ein klassischer "
                   "Kreditgeber liegt hoch, ein Handels- oder Verwahrhaus deutlich "
                   "tiefer.",
        "note": _SH_NOTE,
    },
    {
        "id": "sh_ccr", "label": "CCR", "en": "Counterparty credit risk", "unit": "%",
        "syn": ["Gegenparteiausfallrisiko", "Kontrahentenrisiko"],
        "op": "share", "kind": "shareOfTrea",
        "cells": [[_OV1, "0070", "0010", "Risikobetrag der Kategorie"],
                  [_KM1, "0040", "0010", "Gesamtrisikobetrag"]],
        "formula": "Risikobetrag der Kategorie / Gesamtrisikobetrag",
        "definition": "Anteil des Gegenparteiausfallrisikos am Gesamtrisikobetrag.",
        "purpose": "Misst das Gewicht des Derivate- und Wertpapierfinanzierungs"
                   "geschäfts — Risiko aus dem Ausfall des Vertragspartners, nicht "
                   "des Kreditnehmers.",
        "note": _SH_NOTE,
    },
    {
        "id": "sh_cva", "label": "CVA", "en": "Credit valuation adjustment", "unit": "%",
        "syn": ["Kreditbewertungsanpassung", "CVA-Risiko"],
        "op": "share", "kind": "shareOfTrea",
        "cells": [[_OV1, "0120", "0010", "Risikobetrag der Kategorie"],
                  [_KM1, "0040", "0010", "Gesamtrisikobetrag"]],
        "formula": "Risikobetrag der Kategorie / Gesamtrisikobetrag",
        "definition": "Anteil des Risikos aus Kreditbewertungsanpassungen am "
                      "Gesamtrisikobetrag.",
        "purpose": "Das Bewertungsrisiko des Derivatebuchs. Klein bei fast allen "
                   "Instituten — auffällig hoch nur dort, wo OTC-Derivate eine "
                   "tragende Rolle spielen.",
        "note": _SH_NOTE,
    },
    {
        "id": "sh_market", "label": "Marktrisiko", "en": "Market risk", "unit": "%",
        "syn": ["Handelsbuch", "market risk"],
        "op": "share", "kind": "shareOfTrea",
        "cells": [[_OV1, "0260", "0010", "Risikobetrag der Kategorie"],
                  [_KM1, "0040", "0010", "Gesamtrisikobetrag"]],
        "formula": "Risikobetrag der Kategorie / Gesamtrisikobetrag",
        "definition": "Anteil des Marktrisikos (Positions-, Fremdwährungs- und "
                      "Warenpositionsrisiko) am Gesamtrisikobetrag.",
        "purpose": "Zeigt, wie groß das Handelsbuch im Verhältnis zum "
                   "Gesamtgeschäft ist — die Risikoart, die am schnellsten "
                   "schwankt.",
        "note": _SH_NOTE,
    },
    {
        "id": "sh_op", "label": "Operationelles Risiko", "en": "Operational risk",
        "unit": "%", "syn": ["Op-Risiko", "operational risk"],
        "op": "share", "kind": "shareOfTrea",
        "cells": [[_OV1, "0320", "0010", "Risikobetrag der Kategorie"],
                  [_KM1, "0040", "0010", "Gesamtrisikobetrag"]],
        "formula": "Risikobetrag der Kategorie / Gesamtrisikobetrag",
        "definition": "Anteil des operationellen Risikos am Gesamtrisikobetrag.",
        "purpose": "Der Anteil, der nicht aus Kredit- oder Marktpositionen kommt, "
                   "sondern aus Prozessen, Systemen und Rechtsrisiken. Bei "
                   "gebührenlastigen Häusern regelmäßig der zweitgrößte Block.",
        "note": _SH_NOTE + " Alle Meldungen im Bestand liegen nach dem "
                "Anwendungsbeginn der CRR3, das operationelle Risiko wird also "
                "durchgehend über den Geschäftsindikator bestimmt — dieser Anteil "
                "ist zwischen den Instituten methodisch einheitlich.",
    },
    # ---- Kreditqualität (CQ3) -------------------------------------------
    {
        "id": "npl", "label": "NPL-Quote (CQ3)", "en": "NPL ratio", "unit": "%",
        "syn": ["notleidende Kredite", "non-performing", "NPE-Quote", "Kreditqualität"],
        "op": "npl", "kind": "ratio", "ov": True,
        "cells": [[_CQ3, "0020", "0040", "notleidend"],
                  [_CQ3, "0020", "0010", "bedient"]],
        "formula": "notleidend / (bedient + notleidend)",
        "definition": "Anteil notleidender Kredite und Forderungen am "
                      "Gesamtbestand, aus CQ3 Zeile „Loans and advances“.",
        "purpose": "Der direkteste Blick auf die Qualität des Kreditbuchs — und "
                   "die Kennzahl, die Kreditzyklen am frühesten zeigt.",
        "note": "**Keine aufsichtliche Schwelle.** Die oft zitierten 5 % stammen "
                "aus den EBA-Leitlinien zum Management notleidender "
                "Risikopositionen (EBA/GL/2018/06) und lösen dort die Pflicht zu "
                "einer NPE-Strategie aus. Das ist ein Auslöser, keine Grenze.",
    },
    {
        "id": "npl_hh", "label": "NPL-Quote Haushalte", "en": "NPL ratio households",
        "unit": "%", "syn": ["Privatkunden", "households"],
        "op": "npl", "kind": "ratio",
        "cells": [[_CQ3, "0090", "0040", "notleidend"],
                  [_CQ3, "0090", "0010", "bedient"]],
        "formula": "notleidend / (bedient + notleidend)",
        "definition": "NPL-Quote im Kreditbuch gegenüber privaten Haushalten.",
        "purpose": "Trennt Konsumenten- und Wohnungsbaukredite vom Firmenbuch. "
                   "Beide Teilquoten bewegen sich in verschiedenen Zyklen; die "
                   "Gesamtquote verdeckt das.",
        "note": "Wie bei der NPL-Quote gibt es **keine aufsichtliche Schwelle** — "
                "siehe „NPL-Quote (CQ3)“.",
    },
    {
        "id": "npl_corp", "label": "NPL-Quote Unternehmen",
        "en": "NPL ratio non-financial corporations", "unit": "%",
        "syn": ["Firmenkunden", "corporates"],
        "op": "npl", "kind": "ratio",
        "cells": [[_CQ3, "0070", "0040", "notleidend"],
                  [_CQ3, "0070", "0010", "bedient"]],
        "formula": "notleidend / (bedient + notleidend)",
        "definition": "NPL-Quote im Kreditbuch gegenüber nichtfinanziellen "
                      "Unternehmen.",
        "purpose": "Das Firmenkundenbuch reagiert früher und schärfer auf "
                   "Konjunktur als das Privatkundenbuch — hier zeigt sich eine "
                   "Eintrübung zuerst.",
        "note": "Wie bei der NPL-Quote gibt es **keine aufsichtliche Schwelle** — "
                "siehe „NPL-Quote (CQ3)“.",
    },
    {
        "id": "npe_amt", "label": "NPE Kredite", "en": "Non-performing loans",
        "unit": "Mrd EUR", "syn": ["notleidende Kredite Betrag"],
        "op": "cell", "kind": "eur",
        "cells": [[_CQ3, "0020", "0040", "wert"]],
        "definition": "Bestand notleidender Kredite und Forderungen als Betrag.",
        "purpose": "Setzt die Quote ins Verhältnis zur Größe: 3 % bei einem "
                   "kleinen Institut sind etwas anderes als 3 % bei einer "
                   "Großbank.",
        "note": "Größe, keine Anforderung: eine Schwelle gibt es nicht.",
    },
    {
        "id": "pe_amt", "label": "Performing Kredite", "en": "Performing loans",
        "unit": "Mrd EUR", "syn": ["bediente Kredite"],
        "op": "cell", "kind": "eur",
        "cells": [[_CQ3, "0020", "0010", "wert"]],
        "definition": "Bestand bedienter Kredite und Forderungen als Betrag.",
        "purpose": "Der Nenner der NPL-Quote — und zugleich das Maß dafür, wie "
                   "groß das Kreditbuch überhaupt ist.",
        "note": "Größe, keine Anforderung: eine Schwelle gibt es nicht.",
    },
    # ---- ESG (41.00, Zeile 0010 = Summe der klimarelevanten Sektoren) ----
    # Nur Quotienten: Spalte a ist als "Mln EUR" beschriftet, die Institute
    # melden aber ganz überwiegend in Währungseinheiten (10^2 bis 10^12).
    # Absolutbeträge sind hier institutsübergreifend NICHT vergleichbar;
    # Zähler und Nenner eines Quotienten stammen aus derselben Meldung.
    # ---- Kreditverschlechterungs-Kette (#16 Punkt 3) --------------------
    # performing -> forborne -> non-performing. Jede Stufe steht in einem
    # ANDEREN Template; genau das ist der Grund, warum EDAP diese Kette nicht
    # zeigen kann und wir schon.
    {
        "id": "forb_pe", "label": "Vorstufe (gestundet, bedient)",
        "en": "Performing forborne ratio", "unit": "%",
        "syn": ["forborne", "Stundung", "Forbearance", "Vorstufe"],
        "op": "shareOfSum", "kind": "ratio",
        "cells": [[_CQ1, "0020", "0010", "gestundet-bedient"],
                  [_CQ3, "0020", "0010", "bedient"],
                  [_CQ3, "0020", "0040", "notleidend"]],
        "formula": "gestundet-bedient / (bedient + notleidend)",
        "definition": "Anteil der Kredite, die gestundet wurden und (noch) "
                      "bedient werden, am Gesamtbestand \u2014 aus CQ1 Zeile "
                      "\u201eLoans and advances\u201c, bezogen auf denselben "
                      "Nenner wie die NPL-Quote.",
        "purpose": "Die Stufe **vor** dem Ausfall. Ein Institut mit niedriger "
                   "NPL-Quote und hoher Vorstufe tr\u00e4gt ein Problem, das "
                   "die etablierte Kennzahl noch nicht zeigt.",
        "note": "**Keine Schwelle, und kein Werturteil.** Eine Stundung ist "
                "ein Instrument, kein Fehler \u2014 sie kann einen Ausfall "
                "verhindern statt ihn anzuk\u00fcndigen. Aussagekr\u00e4ftig "
                "ist erst das Verh\u00e4ltnis zur NPL-Quote.",
    },
    {
        "id": "forb_npe", "label": "Vorstufe (gestundet, notleidend)",
        "en": "Non-performing forborne ratio", "unit": "%",
        "syn": ["forborne non-performing"],
        "op": "shareOfSum", "kind": "ratio",
        "cells": [[_CQ1, "0020", "0020", "gestundet-notleidend"],
                  [_CQ3, "0020", "0010", "bedient"],
                  [_CQ3, "0020", "0040", "notleidend"]],
        "formula": "gestundet-notleidend / (bedient + notleidend)",
        "definition": "Anteil der gestundeten Kredite, die bereits notleidend "
                      "sind, am Gesamtbestand.",
        "purpose": "Die Gegenprobe zur bedienten Vorstufe: hier hat die "
                   "Stundung den Ausfall nicht mehr verhindert.",
        "note": "**Keine Schwelle.** Die Kennzahl misst, wie oft eine Stundung "
                "den Ausfall nicht mehr verhindert hat \u2014 aufsichtlich "
                "gefordert ist dazu kein Wert.",
    },
    {
        "id": "npl_cov", "label": "NPL-Deckungsquote",
        "en": "NPL coverage ratio", "unit": "%",
        "syn": ["Deckung", "coverage", "Wertberichtigung", "Risikovorsorge"],
        "op": "deckung", "kind": "ratio",
        "cells": [[_CR1, "0020", "0040", "Wertberichtigung"],
                  [_CQ3, "0020", "0040", "notleidend"]],
        "formula": "|Wertberichtigung| / notleidend",
        "definition": "Wertberichtigungen auf notleidende Kredite im "
                      "Verh\u00e4ltnis zum notleidenden Bestand \u2014 die "
                      "klassische Deckungsquote, aus CR1 und CQ3 "
                      "zusammengesetzt.",
        "purpose": "Wie viel des notleidenden Bestands bereits abgeschrieben "
                   "ist. Eine niedrige Deckung bei hoher NPL-Quote heisst: "
                   "der Verlust steht noch aus.",
        "note": "Gerechnet wird mit dem **Betrag**. Die Wertberichtigung wird "
                "uneinheitlich vorzeichenbehaftet gemeldet \u2014 344 von 364 "
                "Reports negativ, 20 positiv. Eine Null ist dabei erlaubt und "
                "kein Rechenfehler: ein Institut im Bestand meldet 0,8 Mio "
                "EUR notleidende Kredite und **keine** Wertberichtigung.",
    },
    {
        "id": "esg_green", "label": "Anteil nachhaltig",
        "en": "Share of environmentally sustainable exposures", "unit": "%",
        "syn": ["taxonomiekonform", "grün", "CCM", "nachhaltig"],
        "op": "share", "kind": "ratio",
        "cells": [[_ESG, "0010", "0030", "davon nachhaltig"],
                  [_ESG, "0010", "0010", "Bruttobuchwert"]],
        "formula": "davon nachhaltig / Bruttobuchwert",
        "definition": "Anteil der ökologisch nachhaltigen Risikopositionen "
                      "(Klimaschutz) am Bruttobuchwert der klimarelevanten Sektoren.",
        "purpose": "Der einzige im Bestand belastbar vergleichbare Indikator "
                   "dafür, wie weit ein Institut sein Kreditbuch bereits an der "
                   "EU-Taxonomie ausgerichtet hat.",
        "note": "Nur als Verhältnis auswertbar — die Absolutbeträge in 41.00 "
                "haben uneinheitliche Meldeeinheiten.",
    },
    {
        "id": "esg_paris", "label": "Paris-ausgeschlossen",
        "en": "Excluded from Paris-aligned benchmarks", "unit": "%",
        "syn": ["Paris-Benchmark", "ausgeschlossen"],
        "op": "share", "kind": "ratio",
        "cells": [[_ESG, "0010", "0020", "davon ausgeschlossen"],
                  [_ESG, "0010", "0010", "Bruttobuchwert"]],
        "formula": "davon ausgeschlossen / Bruttobuchwert",
        "definition": "Anteil der Risikopositionen gegenüber Unternehmen, die aus "
                      "Paris-konformen Referenzwerten ausgeschlossen sind.",
        "purpose": "Das Gegenstück zum grünen Anteil: die Seite des Buchs, die "
                   "am stärksten unter Transitionsdruck steht.",
        "note": "Nur als Verhältnis auswertbar — siehe „Anteil nachhaltig“.",
    },
    {
        "id": "esg_stage2", "label": "Stage 2", "en": "Stage 2 exposures", "unit": "%",
        "syn": ["Wertberichtigungsstufe 2", "erhöhtes Ausfallrisiko"],
        "op": "share", "kind": "ratio",
        "cells": [[_ESG, "0010", "0040", "davon Stage 2"],
                  [_ESG, "0010", "0010", "Bruttobuchwert"]],
        "formula": "davon Stage 2 / Bruttobuchwert",
        "definition": "Anteil der Risikopositionen in Wertberichtigungsstufe 2 "
                      "(signifikant erhöhtes Ausfallrisiko) an den klimarelevanten "
                      "Sektoren.",
        "purpose": "Ein Frühindikator: Stage 2 heißt noch nicht ausgefallen, aber "
                   "deutlich verschlechtert — hier zeigt sich Transitionsdruck "
                   "vor der NPE-Quote.",
        "note": "Nur als Verhältnis auswertbar — siehe „Anteil nachhaltig“.",
    },
    {
        "id": "esg_npe", "label": "davon notleidend",
        "en": "Of which non-performing", "unit": "%",
        "syn": ["ESG notleidend", "Klima NPE"],
        "op": "share", "kind": "ratio",
        "cells": [[_ESG, "0010", "0050", "davon notleidend"],
                  [_ESG, "0010", "0010", "Bruttobuchwert"]],
        "formula": "davon notleidend / Bruttobuchwert",
        "definition": "Anteil notleidender Risikopositionen an den klimarelevanten "
                      "Sektoren.",
        "purpose": "Die bereits eingetretenen Ausfälle in genau den Sektoren, für "
                   "die die Transition ein Geschäftsrisiko ist — vergleichbar mit "
                   "der allgemeinen NPL-Quote desselben Instituts.",
        "note": "Nur als Verhältnis auswertbar — siehe „Anteil nachhaltig“.",
    },
    # ---- Vergütung (REM1, 30.01) ----------------------------------------
    # Zeile 0010 = Kopfzahl der identified staff, 0020 = fixe Gesamtvergütung,
    # 0090 = variable Gesamtvergütung; die vier Spalten sind die Funktionsstufen.
    # Zähler und Nenner stammen aus derselben Zelle-Spalte desselben Reports.
    {
        "id": "rem_head_mb", "label": "Fixvergütung/Kopf Vorstand",
        "en": "Fixed remuneration per head, management body", "unit": "EUR",
        "syn": ["Vorstandsvergütung", "Gehalt Vorstand", "Vergütung", "Boni",
                "remuneration", "management function"],
        "op": "perhead", "kind": "eurPlain", "plausible": list(REM_PER_HEAD),
        "cells": [[_REM, "0020", _MB_MB, "fixe Vergütung"],
                  [_REM, "0010", _MB_MB, "Köpfe"]],
        "formula": "fixe Vergütung / Köpfe",
        "definition": "Fixe Gesamtvergütung der Geschäftsleitung (MB Management "
                      "function) geteilt durch die Zahl der dort gemeldeten "
                      "identified staff, umgerechnet zum EZB-Referenzkurs.",
        "purpose": "Die öffentlich meistbeachtete Zahl im ganzen Datensatz — und "
                   "eine, die EDAP nicht aggregiert: sie entsteht erst aus der "
                   "Population.",
        "note": _REM_NOTE,
    },
    {
        "id": "rem_head_sb", "label": "Fixvergütung/Kopf Aufsichtsrat",
        "en": "Fixed remuneration per head, supervisory function", "unit": "EUR",
        "syn": ["Aufsichtsratsvergütung", "supervisory function", "Aufsichtsrat"],
        "op": "perhead", "kind": "eurPlain", "plausible": list(REM_PER_HEAD),
        "cells": [[_REM, "0020", _MB_SB, "fixe Vergütung"],
                  [_REM, "0010", _MB_SB, "Köpfe"]],
        "formula": "fixe Vergütung / Köpfe",
        "definition": "Fixe Gesamtvergütung des Aufsichtsorgans (MB Supervisory "
                      "function) je gemeldetem Kopf.",
        "purpose": "Aufsichtsratsmandate sind Nebenämter — die Größenordnung "
                   "liegt deshalb systematisch unter der Geschäftsleitung und "
                   "sagt etwas über die Governance-Struktur, nicht über Gehälter.",
        "note": _REM_NOTE,
    },
    {
        "id": "rem_head_sm", "label": "Fixvergütung/Kopf Senior Management",
        "en": "Fixed remuneration per head, other senior management", "unit": "EUR",
        "syn": ["Senior Management", "Führungsebene", "senior management"],
        "op": "perhead", "kind": "eurPlain", "plausible": list(REM_PER_HEAD),
        "cells": [[_REM, "0020", _SM, "fixe Vergütung"],
                  [_REM, "0010", _SM, "Köpfe"]],
        "formula": "fixe Vergütung / Köpfe",
        "definition": "Fixe Gesamtvergütung der übrigen oberen Führungsebene je "
                      "gemeldetem Kopf.",
        "purpose": "Die Ebene unterhalb des Vorstands — der Abstand zu ihm zeigt, "
                   "wie steil die Vergütungspyramide eines Hauses ist.",
        "note": _REM_NOTE,
    },
    {
        "id": "rem_head_ot", "label": "Fixvergütung/Kopf übrige Risk-Taker",
        "en": "Fixed remuneration per head, other identified staff", "unit": "EUR",
        "syn": ["Risk-Taker", "identified staff", "übrige Mitarbeiter"],
        "op": "perhead", "kind": "eurPlain", "plausible": list(REM_PER_HEAD),
        "cells": [[_REM, "0020", _OT, "fixe Vergütung"],
                  [_REM, "0010", _OT, "Köpfe"]],
        "formula": "fixe Vergütung / Köpfe",
        "definition": "Fixe Gesamtvergütung der übrigen identified staff je "
                      "gemeldetem Kopf.",
        "purpose": "Die mit Abstand größte Gruppe — hier steht die Breite des "
                   "Risikonehmerkreises, nicht die Spitze.",
        "note": _REM_NOTE,
    },
    {
        "id": "rem_varfix_mb", "label": "Variabel/Fix Vorstand",
        "en": "Variable to fixed ratio, management body", "unit": "%",
        "syn": ["Bonus", "Bonuskultur", "variable Vergütung", "Bonus-Cap"],
        "op": "share", "kind": "ratio",
        "cells": [[_REM, "0090", _MB_MB, "variable Vergütung"],
                  [_REM, "0020", _MB_MB, "fixe Vergütung"]],
        "formula": "variable Vergütung / fixe Vergütung",
        "definition": "Variable Gesamtvergütung der Geschäftsleitung im Verhältnis "
                      "zur fixen, in Prozent.",
        "purpose": "Der aufsichtlich gedeckelte Teil der Vergütung — und damit "
                   "die Kennzahl, an der sich Anreizstruktur und Bonuskultur "
                   "zwischen Häusern und Ländern unterscheiden.",
        "floor": 100.0,
        "floor_src": "CRD Art. 94 (1) (g) — variabel höchstens 100 % des fixen "
                     "Anteils; per Hauptversammlungsbeschluss bis 200 %",
        "note": "Die Obergrenze gilt je **Person**, nicht für den hier gebildeten "
                "Gruppendurchschnitt: eine Quote unter 100 % schließt eine "
                "Überschreitung im Einzelfall nicht aus, und eine darüber ist "
                "nicht ohne Weiteres ein Verstoß. " + _REM_NOTE,
    },
    {
        "id": "rem_varfix_ot", "label": "Variabel/Fix übrige Risk-Taker",
        "en": "Variable to fixed ratio, other identified staff", "unit": "%",
        "syn": ["Bonus Risk-Taker", "variable Vergütung übrige"],
        "op": "share", "kind": "ratio",
        "cells": [[_REM, "0090", _OT, "variable Vergütung"],
                  [_REM, "0020", _OT, "fixe Vergütung"]],
        "formula": "variable Vergütung / fixe Vergütung",
        "definition": "Variable Gesamtvergütung der übrigen identified staff im "
                      "Verhältnis zur fixen, in Prozent.",
        "purpose": "Zeigt, ob die Bonusorientierung eines Hauses auf die Spitze "
                   "beschränkt ist oder den ganzen Risikonehmerkreis erfasst.",
        "floor": 100.0,
        "floor_src": "CRD Art. 94 (1) (g) — variabel höchstens 100 % des fixen "
                     "Anteils; per Hauptversammlungsbeschluss bis 200 %",
        "note": "Obergrenze je Person, nicht für den Gruppendurchschnitt. "
                + _REM_NOTE,
    },
    {
        "id": "rem_staff_ot", "label": "Identified staff (übrige)",
        "en": "Number of other identified staff", "unit": "Personen",
        "syn": ["Anzahl Risk-Taker", "Kopfzahl", "number of identified staff"],
        "op": "cell", "kind": "num",
        "cells": [[_REM, "0010", _OT, "wert"]],
        "definition": "Zahl der übrigen identified staff, wie im Report gemeldet.",
        "purpose": "Der Bezugsmaßstab für die Vergütungsspalten — und selbst eine "
                   "Aussage: wie weit ein Haus den Kreis der Risikonehmer zieht, "
                   "ist eine Ermessensentscheidung.",
        "note": "Größe, keine Anforderung: eine Schwelle gibt es nicht. "
                + _REM_NOTE,
    },
]

# Benchmark-Profile: nur noch eine Reihenfolge von Kennzahl-IDs. Vorher
# definierte `BM_PROFILES` im Viewer dieselben Kennzahlen ein zweites Mal.
PROFILES = [
    {"id": "km1", "label": "KM1-Kennzahlen", "en": "KM1 key metrics", "tpl": _KM1, "trend": "0050",
     "sort": ["cet1", -1],
     "metrics": ["cet1", "t1", "tc", "lev", "lcr", "nsfr", "trea", "cet1_amt"]},
    {"id": "headroom", "label": "Kapital-Headroom", "en": "Capital headroom", "tpl": _KM1, "trend": "0070",
     "sort": ["hr", 1],
     "metrics": ["cet1", "tc", "ocr", "hr", "cet1_srep", "trea"]},
    {"id": "risk", "label": "Risikoprofil (OV1)", "en": "Risk profile (OV1)", "tpl": _OV1, "trend": None,
     "sort": ["sh_credit", -1],
     "metrics": ["sh_credit", "sh_ccr", "sh_cva", "sh_market", "sh_op", "trea"]},
    {"id": "npl", "label": "Kreditqualität (NPL, CQ3)", "en": "Credit quality (NPL, CQ3)", "tpl": _CQ3, "trend": None,
     "sort": ["npl", -1],
     "metrics": ["npl", "npe_amt", "pe_amt", "npl_hh", "npl_corp"]},
    # Die Kette aus #16. Grundlage ist CQ3, weil dort die NPL-Quote steht und
    # weil ein Report ohne CQ3 keinen Anker hätte — CQ1 und CR1 kommen als
    # Quellzellen dazu. Sortiert nach der Vorstufe, nicht nach der NPL-Quote:
    # die NPL-Rangliste gibt es schon im Profil daneben, und der Zweck dieses
    # Profils ist die Stufe, die man dort NICHT sieht.
    {"id": "kette", "label": "Kreditverschlechterungs-Kette", "en": "Credit-deterioration chain", "tpl": _CQ3,
     "trend": None, "sort": ["forb_pe", -1],
     # Fremdtemplates ausdruecklich deklariert. Die Regel ist sonst: eine
     # Spalte kommt aus dem eigenen Template, sonst bleibt sie fuer die
     # meisten Zeilen leer. Hier gemessen: 90,3 % / 91,1 % (CQ1) und 98,2 %
     # (CR1) der Reports mit CQ3-Kreditzeile tragen die Zelle auch. Die
     # Deklaration ist die Bedingung, unter der die Ausnahme gilt -- und sie
     # verpflichtet: was hier steht, muss in HEAD_TEMPLATES stehen, sonst
     # erreicht die Zelle benchmark.json nie und die Spalte bleibt leer,
     # ohne dass irgendetwas fehlschlaegt.
     "cross": ["80.00.A", "21.01.D"],
     "note": "performing → gestundet → notleidend. Jede Stufe steht in einem "
             "anderen Template (CQ3, CQ1, CR1); EDAP liefert sie in "
             "getrennten Dateien, die nie zusammengeführt werden. "
             "Vollständige Auswertung: processed/credit_chain.csv.",
     "metrics": ["npl", "forb_pe", "forb_npe", "npl_cov", "npe_amt", "pe_amt"]},
    {"id": "esg", "label": "ESG — Klima-Transitionsrisiko", "en": "ESG — climate transition risk", "tpl": _ESG, "trend": None,
     "sort": ["esg_green", -1],
     "note": "Nur Verhältniszahlen: die Absolutbeträge in 41.00 haben "
             "uneinheitliche Meldeeinheiten.",
     "metrics": ["esg_green", "esg_paris", "esg_stage2", "esg_npe"]},
    {"id": "liq", "label": "Liquidität", "en": "Liquidity", "tpl": _KM1, "trend": "0320",
     "sort": ["lcr", -1],
     "metrics": ["lcr", "nsfr", "hqla", "outflow", "asf"]},
    # Vergütung (#18). `gate` ist hier keine Kür: eine Vergütungs-Rangliste mit
    # falschen Zahlen wäre der schädlichste denkbare Fehler in diesem Projekt.
    # Ein Report fliegt aus der Liste, sobald IRGENDEINE seiner Funktionsstufen
    # ausserhalb von REM_PER_HEAD liegt — gemessen: 59 von 354 Reports, meist
    # alle vier Stufen zugleich (35 von 59), was die Diagnose stützt: das ist
    # eine falsche Meldeeinheit für das ganze Template, kein einzelner Wert.
    # Der Viewer weist die Ausschlussquote aus und nennt die Ausgeschlossenen.
    {"id": "verg", "label": "Vergütung (REM1)", "en": "Remuneration (REM1)", "tpl": _REM, "trend": None,
     "sort": ["rem_head_mb", -1],
     "gate": ["rem_head_sb", "rem_head_mb", "rem_head_sm", "rem_head_ot"],
     "note": "Vergütung pro Kopf, nicht pro Person: „identified staff“ ist eine "
             "aufsichtliche Teilmenge, Teilzeit und unterjährige Wechsel sind "
             "nicht bereinigt, und der Konsolidierungskreis entscheidet mit, "
             "wer mitzählt. Ein Vergleich zweier Häuser ist damit ein Vergleich "
             "zweier Meldungen — keine Gehaltsstatistik.",
     "metrics": ["rem_head_mb", "rem_head_sb", "rem_head_sm", "rem_head_ot",
                 "rem_varfix_mb", "rem_varfix_ot", "rem_staff_ot"]},
]

# ---------------------------------------------------------------------------
# Englische Fassung der Erklaerungstexte (#65).
#
# Die Registry bleibt deutsch — hier sind die Befunde entstanden, und die
# Nuance sitzt dort genauer. Englisch ist trotzdem die Standardsprache der
# Oberflaeche, und eine englische Oberflaeche mit deutschen Kennzahl-
# erklaerungen waere halb uebersetzt.
#
# Warum ein eigener Block und nicht `definition_en` neben jedem `definition`:
# die Registry ist die Stelle, an der man nachliest, WAS eine Kennzahl ist und
# aus welcher Zelle sie kommt. Zwei Sprachen ineinander verschraenkt machen
# genau das unlesbar. Getrennt ist ausserdem pruefbar, ob eine Uebersetzung
# fehlt — verschraenkt faellt ein fehlendes Feld niemandem auf.
#
# Zusammengefuehrt wird erst in `metric_payload()`, dem einzigen Weg der
# Registry nach codebook.json.
# ---------------------------------------------------------------------------

_REM_NOTE_EN = (
    "**No threshold, and no salary statistic.** “Identified staff” is a "
    "supervisory subset (CRD Art. 92 (3)) — not the workforce. Part-time work "
    "and arrivals and departures during the year are not adjusted for, so one "
    "head is not necessarily a full year. And the scope of consolidation "
    "(CON/IND) is part of what decides whose remuneration is counted at all."
)
_SH_NOTE_EN = (
    "Composition, not a requirement: there is no threshold. The denominator is "
    "the total risk exposure amount from KM1 r0040 of **the same filing** — "
    "numerator and denominator therefore come from one report. The five "
    "categories shown here do **not** add up to 100 %: OV1 carries further rows "
    "(among them settlement, securitisation and large-exposure risks in the "
    "trading book) that this profile does not show."
)
_SIZE_EN = "A magnitude, not a requirement: there is no threshold."
_NPL_NO_THRESHOLD_EN = ("As with the NPL ratio there is **no supervisory "
                        "threshold** — see “NPL ratio (CQ3)”.")
_ESG_RATIO_EN = "Analysable as a ratio only — see “Share environmentally sustainable”."
_VARFIX_SRC_EN = ("CRD Art. 94 (1) (g) — variable at most 100 % of the fixed "
                  "component; up to 200 % by resolution of the general meeting")

TEXTE_EN = {
 "cet1": {
  "definition": "Common Equity Tier 1 capital (CET1) in relation to the total "
                "risk exposure amount (TREA).",
  "purpose": "The central solvency metric: how much loss-absorbing capital of "
             "the highest quality stands behind the weighted risks?",
  "floor_src": "CRR Art. 92 (1) (a) — Pillar 1 minimum ratio",
  "note": "The CET1 requirement binding for this institution is **not** in KM1 "
          "as a single figure: it is composed of the Pillar 1 floor, the CET1 "
          "share of the Pillar 2 add-on and the combined buffer requirement. "
          "The reported overall requirement (r0190) refers to the **total "
          "capital ratio** and belongs there — see “Total capital ratio” and "
          "“Headroom TC−OCR”.",
 },
 "t1": {
  "definition": "Tier 1 capital (CET1 + additional Tier 1) in relation to the "
                "total risk exposure amount.",
  "purpose": "Its distance from the CET1 ratio shows how strongly an "
             "institution relies on AT1 instruments — capital that is liable "
             "in going concern, but only after Common Equity Tier 1.",
  "floor_src": "CRR Art. 92 (1) (b) — Pillar 1 minimum ratio",
 },
 "tc": {
  "definition": "Total own funds (CET1 + AT1 + Tier 2) in relation to the total "
                "risk exposure amount.",
  "purpose": "The broadest capital metric — it also counts subordinated "
             "instruments that become liable later than CET1.",
  "floor_src": "CRR Art. 92 (1) (c) — Pillar 1 minimum ratio",
 },
 "ocr": {
  "definition": "The overall requirement for the total capital ratio that "
                "applies to this institution — Pillar 1 floor, Pillar 2 add-on "
                "and combined buffer requirement together.",
  "purpose": "The figure the total capital ratio really has to be measured "
             "against. It is institution-specific — which is why comparing two "
             "institutions against the Pillar 1 floor alone says little.",
  "note": "This is a **requirement**, not a threshold in its own right. Rebound "
          "to a new data point in RF 4.2 (#26).",
 },
 "hr": {
  "definition": "Distance of the total capital ratio from this institution’s "
                "overall requirement (OCR), in percentage points.",
  "purpose": "The only capital figure in the overview that takes the "
             "institution-specific requirement into account instead of the "
             "statutory floor. It says how much room there really is.",
  "floor_src": "no legal value — at 0 pp the institution’s own overall "
               "requirement is met exactly",
  "note": "Both magnitudes come from the same template and the same filing, so "
          "they cancel cleanly. The overall requirement is rebound to a new "
          "data point in RF 4.2 — comparisons across the version change with a "
          "caveat (#26).",
 },
 "cet1_srep": {
  "definition": "Share of Common Equity Tier 1 capital that remains available "
                "after meeting the SREP own funds requirement.",
  "purpose": "The headroom reported by the institution itself — a second, "
             "independent view of the same thing as “Headroom TC−OCR”, only at "
             "CET1 level and without the buffer requirement.",
  "note": "A magnitude without a threshold of its own: the requirement it was "
          "computed against is already inside the value.",
 },
 "lev": {
  "definition": "Tier 1 capital (T1) in relation to the leverage ratio total "
                "exposure measure — an **unweighted** reference base.",
  "purpose": "A backstop against model risk: it ignores risk weighting and "
             "therefore catches exactly the cases in which the weighted ratios "
             "look too favourable.",
  "floor_src": "CRR Art. 92 (1) (d) — Pillar 1 minimum ratio",
 },
 "lcr": {
  "definition": "Liquidity coverage ratio: highly liquid assets in relation to "
                "the net outflows of a 30-day stress scenario.",
  "purpose": "Does the institution survive a month of acute liquidity stress "
             "under its own steam?",
  "floor_src": "Delegated Regulation (EU) 2015/61 — minimum ratio 100 %",
 },
 "nsfr": {
  "definition": "Structural liquidity ratio: available stable funding in "
                "relation to required stable funding, over a one-year horizon.",
  "purpose": "The long-run counterpart to the LCR — does the maturity of the "
             "funding match the maturity of the business?",
  "floor_src": "CRR Art. 428b — minimum ratio 100 %",
 },
 "hqla": {
  "definition": "Stock of high quality liquid assets — the numerator of the LCR.",
  "purpose": "Separates the two routes to a high LCR: a large buffer is "
             "something other than small expected outflows.",
  "note": _SIZE_EN,
 },
 "outflow": {
  "definition": "Total net cash outflows in the 30-day scenario — the "
                "denominator of the LCR.",
  "purpose": "The stress scenario in one figure: how much liquidity the "
             "institution assumes will flow out within 30 days.",
  "note": _SIZE_EN,
 },
 "asf": {
  "definition": "Available stable funding — the numerator of the NSFR.",
  "purpose": "The part of the funding that holds up over the long run. Together "
             "with the NSFR it shows whether a good ratio comes from a lot of "
             "stable funding or from little long-term business.",
  "note": _SIZE_EN,
 },
 "trea": {
  "definition": "Total risk exposure amount: the sum of all risk-weighted "
                "exposure amounts, converted at the ECB reference rate.",
  "purpose": "The denominator of the capital ratios and at the same time the "
             "most common measure of size — it is what makes the other ratios "
             "placeable in the first place.",
  "note": _SIZE_EN,
 },
 "cet1_amt": {
  "definition": "Common Equity Tier 1 capital as an amount — the numerator of "
                "the CET1 ratio.",
  "purpose": "Breaks the CET1 ratio into its two causes: a high ratio can come "
             "from a lot of capital or from little weighted risk. Only with the "
             "TREA beside it does it become readable.",
  "note": _SIZE_EN,
 },
 "sh_credit": {
  "definition": "Share of credit risk (excluding counterparty credit risk) in "
                "the total risk exposure amount.",
  "purpose": "The core of the business model in one figure: a classic lender is "
             "high, a trading or custody house markedly lower.",
  "note": _SH_NOTE_EN,
 },
 "sh_ccr": {
  "definition": "Share of counterparty credit risk in the total risk exposure "
                "amount.",
  "purpose": "Measures the weight of the derivatives and securities financing "
             "business — risk from the default of the counterparty, not of the "
             "borrower.",
  "note": _SH_NOTE_EN,
 },
 "sh_cva": {
  "definition": "Share of credit valuation adjustment risk in the total risk "
                "exposure amount.",
  "purpose": "The valuation risk of the derivatives book. Small at almost every "
             "institution — conspicuously high only where OTC derivatives play "
             "a load-bearing role.",
  "note": _SH_NOTE_EN,
 },
 "sh_market": {
  "definition": "Share of market risk (position, foreign exchange and commodity "
                "risk) in the total risk exposure amount.",
  "purpose": "Shows how large the trading book is relative to the business as a "
             "whole — the type of risk that moves fastest.",
  "note": _SH_NOTE_EN,
 },
 "sh_op": {
  "definition": "Share of operational risk in the total risk exposure amount.",
  "purpose": "The share that comes not from credit or market positions but from "
             "processes, systems and legal risk. At fee-heavy houses regularly "
             "the second largest block.",
  "note": _SH_NOTE_EN + " All filings in the holdings fall after the date of "
          "application of CRR3, so operational risk is determined throughout "
          "via the business indicator — this share is methodologically uniform "
          "across institutions.",
 },
 "npl": {
  "definition": "Share of non-performing loans and advances in the total stock, "
                "from CQ3 row “Loans and advances”.",
  "purpose": "The most direct view of the quality of the loan book — and the "
             "metric that shows credit cycles earliest.",
  "note": "**No supervisory threshold.** The 5 % often quoted come from the EBA "
          "Guidelines on management of non-performing exposures "
          "(EBA/GL/2018/06), where they trigger the obligation to have an NPE "
          "strategy. That is a trigger, not a limit.",
 },
 "npl_hh": {
  "definition": "NPL ratio in the loan book towards households.",
  "purpose": "Separates consumer and residential mortgage lending from the "
             "corporate book. The two sub-ratios move in different cycles; the "
             "overall ratio hides that.",
  "note": _NPL_NO_THRESHOLD_EN,
 },
 "npl_corp": {
  "definition": "NPL ratio in the loan book towards non-financial corporations.",
  "purpose": "The corporate book reacts earlier and more sharply to the economic "
             "cycle than the retail book — a deterioration shows up here first.",
  "note": _NPL_NO_THRESHOLD_EN,
 },
 "npe_amt": {
  "definition": "Stock of non-performing loans and advances as an amount.",
  "purpose": "Puts the ratio in proportion to size: 3 % at a small institution "
             "is something other than 3 % at a large bank.",
  "note": _SIZE_EN,
 },
 "pe_amt": {
  "definition": "Stock of performing loans and advances as an amount.",
  "purpose": "The denominator of the NPL ratio — and at the same time the "
             "measure of how large the loan book is at all.",
  "note": _SIZE_EN,
 },
 "forb_pe": {
  "definition": "Share of loans that have been forborne and are (still) being "
                "serviced, in the total stock — from CQ1 row “Loans and "
                "advances”, against the same denominator as the NPL ratio.",
  "purpose": "The stage **before** default. An institution with a low NPL ratio "
             "and a high preceding stage carries a problem the established "
             "metric does not yet show.",
  "note": "**No threshold, and no value judgement.** Forbearance is an "
          "instrument, not a mistake — it can prevent a default rather than "
          "announce one. Only the relation to the NPL ratio is meaningful.",
 },
 "forb_npe": {
  "definition": "Share of forborne loans that are already non-performing, in "
                "the total stock.",
  "purpose": "The counter-check to the performing preceding stage: here "
             "forbearance no longer prevented the default.",
  "note": "**No threshold.** The metric measures how often forbearance no "
          "longer prevented a default — supervision requires no value for it.",
 },
 "npl_cov": {
  "definition": "Impairments on non-performing loans in relation to the "
                "non-performing stock — the classic coverage ratio, assembled "
                "from CR1 and CQ3.",
  "purpose": "How much of the non-performing stock has already been written "
             "down. Low coverage at a high NPL ratio means: the loss is still "
             "to come.",
  "note": "Computed on the **amount**. The impairment is filed with an "
          "inconsistent sign — 344 of 364 reports negative, 20 positive. A zero "
          "is permitted there and is not an arithmetic error: one institution "
          "in the holdings reports 0.8 m EUR of non-performing loans and **no** "
          "impairment.",
 },
 "esg_green": {
  "definition": "Share of environmentally sustainable exposures (climate change "
                "mitigation) in the gross carrying amount of the "
                "climate-relevant sectors.",
  "purpose": "The only indicator in the holdings that is robustly comparable "
             "for how far an institution has already aligned its loan book with "
             "the EU taxonomy.",
  "note": "Analysable as a ratio only — the absolute amounts in 41.00 have "
          "inconsistent filed units.",
 },
 "esg_paris": {
  "definition": "Share of exposures towards companies excluded from "
                "Paris-aligned benchmarks.",
  "purpose": "The counterpart to the green share: the side of the book under "
             "the strongest transition pressure.",
  "note": _ESG_RATIO_EN,
 },
 "esg_stage2": {
  "definition": "Share of exposures in impairment stage 2 (significantly "
                "increased credit risk) in the climate-relevant sectors.",
  "purpose": "An early indicator: stage 2 does not yet mean default, but "
             "markedly deteriorated — transition pressure shows here before it "
             "reaches the NPE ratio.",
  "note": _ESG_RATIO_EN,
 },
 "esg_npe": {
  "definition": "Share of non-performing exposures in the climate-relevant "
                "sectors.",
  "purpose": "The defaults that have already occurred in exactly those sectors "
             "for which the transition is a business risk — comparable with the "
             "same institution’s general NPL ratio.",
  "note": _ESG_RATIO_EN,
 },
 "rem_head_mb": {
  "definition": "Total fixed remuneration of the management body (MB management "
                "function) divided by the number of identified staff reported "
                "there, converted at the ECB reference rate.",
  "purpose": "The most publicly watched figure in the whole dataset — and one "
             "EDAP does not aggregate: it only comes into being from the "
             "population.",
  "note": _REM_NOTE_EN,
 },
 "rem_head_sb": {
  "definition": "Total fixed remuneration of the supervisory body (MB "
                "supervisory function) per reported head.",
  "purpose": "Supervisory board mandates are secondary offices — the order of "
             "magnitude therefore lies systematically below the management body "
             "and says something about the governance structure, not about "
             "salaries.",
  "note": _REM_NOTE_EN,
 },
 "rem_head_sm": {
  "definition": "Total fixed remuneration of other senior management per "
                "reported head.",
  "purpose": "The level below the executive board — its distance from it shows "
             "how steep a house’s remuneration pyramid is.",
  "note": _REM_NOTE_EN,
 },
 "rem_head_ot": {
  "definition": "Total fixed remuneration of other identified staff per "
                "reported head.",
  "purpose": "By far the largest group — what stands here is the breadth of the "
             "risk-taker population, not the top of it.",
  "note": _REM_NOTE_EN,
 },
 "rem_varfix_mb": {
  "definition": "Total variable remuneration of the management body in relation "
                "to the fixed component, in per cent.",
  "purpose": "The part of remuneration that is capped by supervision — and "
             "therefore the metric on which incentive structure and bonus "
             "culture differ between houses and countries.",
  "floor_src": _VARFIX_SRC_EN,
  "note": "The cap applies per **person**, not to the group average formed "
          "here: a ratio below 100 % does not rule out an individual breach, "
          "and one above it is not without more a breach. " + _REM_NOTE_EN,
 },
 "rem_varfix_ot": {
  "definition": "Total variable remuneration of other identified staff in "
                "relation to the fixed component, in per cent.",
  "purpose": "Shows whether a house’s bonus orientation is confined to the top "
             "or covers the whole risk-taker population.",
  "floor_src": _VARFIX_SRC_EN,
  "note": "Cap per person, not for the group average. " + _REM_NOTE_EN,
 },
 "rem_staff_ot": {
  "definition": "Number of other identified staff, as reported.",
  "purpose": "The reference measure for the remuneration columns — and a "
             "statement in itself: how widely a house draws the circle of risk "
             "takers is a matter of judgement.",
  "note": _SIZE_EN + " " + _REM_NOTE_EN,
 },
}

PROFIL_NOTIZEN_EN = {
 "kette": "performing → forborne → non-performing. Each stage sits in a "
          "different template (CQ3, CQ1, CR1); EDAP delivers them in separate "
          "files that are never brought together. Full analysis: "
          "processed/credit_chain.csv.",
 "esg": "Ratios only: the absolute amounts in 41.00 have inconsistent filed "
        "units.",
 "verg": "Remuneration per head, not per person: “identified staff” is a "
         "supervisory subset, part-time work and mid-year changes are not "
         "adjusted for, and the scope of consolidation is part of what decides "
         "who counts. A comparison of two houses is therefore a comparison of "
         "two filings — not a salary statistic.",
}

METRIC_IDS = [m["id"] for m in METRICS]
OVERVIEW_IDS = [m["id"] for m in METRICS if m.get("ov")]


_TEXTFELDER = ("definition", "purpose", "note", "floor_src")


def metric_payload():
    """Form für codebook.json: Kennzahlen + Profile. Ohne Rechen-Code — die
    Rechenvorschrift steht deklarativ in `op`.

    Hier und nur hier werden die englischen Erklärungstexte angehängt, als
    `definition_en`, `purpose_en`, `note_en`, `floor_src_en`. Der Viewer wählt
    daraus nach eingestellter Sprache und fällt auf die deutsche Fassung
    zurück, wenn eine fehlt — sichtbarer Text ist besser als eine Lücke.

    Die Registry selbst bleibt unverändert: sie ist die Stelle, an der man
    nachliest, was eine Kennzahl ist, und ein `dict`, das zwei Sprachen
    ineinander verschränkt, liest sich nicht mehr.
    """
    metriken = []
    for m in METRICS:
        e = TEXTE_EN.get(m["id"], {})
        kopie = dict(m)
        for feld in _TEXTFELDER:
            if e.get(feld):
                kopie[feld + "_en"] = e[feld]
        metriken.append(kopie)
    profile = []
    for pr in PROFILES:
        kopie = dict(pr)
        if PROFIL_NOTIZEN_EN.get(pr["id"]):
            kopie["note_en"] = PROFIL_NOTIZEN_EN[pr["id"]]
        profile.append(kopie)
    return {"metrics": metriken, "profiles": profile}
