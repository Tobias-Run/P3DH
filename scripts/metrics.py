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
]

# Benchmark-Profile: nur noch eine Reihenfolge von Kennzahl-IDs. Vorher
# definierte `BM_PROFILES` im Viewer dieselben Kennzahlen ein zweites Mal.
PROFILES = [
    {"id": "km1", "label": "KM1-Kennzahlen", "tpl": _KM1, "trend": "0050",
     "sort": ["cet1", -1],
     "metrics": ["cet1", "t1", "tc", "lev", "lcr", "nsfr", "trea", "cet1_amt"]},
    {"id": "headroom", "label": "Kapital-Headroom", "tpl": _KM1, "trend": "0070",
     "sort": ["hr", 1],
     "metrics": ["cet1", "tc", "ocr", "hr", "cet1_srep", "trea"]},
    {"id": "risk", "label": "Risikoprofil (OV1)", "tpl": _OV1, "trend": None,
     "sort": ["sh_credit", -1],
     "metrics": ["sh_credit", "sh_ccr", "sh_cva", "sh_market", "sh_op", "trea"]},
    {"id": "npl", "label": "Kreditqualität (NPL, CQ3)", "tpl": _CQ3, "trend": None,
     "sort": ["npl", -1],
     "metrics": ["npl", "npe_amt", "pe_amt", "npl_hh", "npl_corp"]},
    {"id": "esg", "label": "ESG — Klima-Transitionsrisiko", "tpl": _ESG, "trend": None,
     "sort": ["esg_green", -1],
     "note": "Nur Verhältniszahlen: die Absolutbeträge in 41.00 haben "
             "uneinheitliche Meldeeinheiten.",
     "metrics": ["esg_green", "esg_paris", "esg_stage2", "esg_npe"]},
    {"id": "liq", "label": "Liquidität", "tpl": _KM1, "trend": "0320",
     "sort": ["lcr", -1],
     "metrics": ["lcr", "nsfr", "hqla", "outflow", "asf"]},
]

METRIC_IDS = [m["id"] for m in METRICS]
OVERVIEW_IDS = [m["id"] for m in METRICS if m.get("ov")]


def metric_payload():
    """Form für codebook.json: Kennzahlen + Profile. Ohne Rechen-Code — die
    Rechenvorschrift steht deklarativ in `op`."""
    return {"metrics": METRICS, "profiles": PROFILES}
