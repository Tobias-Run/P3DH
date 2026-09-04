"""Kuratierte Kennzahlen-Registry (#63, erster Teil von #25).

Der Überblick zeigte acht Zahlen ohne Erklärung. Wer nicht weiß, was eine NSFR
ist, erfuhr es dort nicht — und ob 12,6 % CET1 viel oder wenig ist, schon gar
nicht.

Diese Registry trägt zu jeder Kennzahl **Definition, Zweck, Schwelle und
Herkunft**. Sie wird von `build_zweig_a_shards.py` nach `codebook.json`
geschrieben; der Viewer liest sie und führt keine zweite Liste — dasselbe
Muster wie `template_themes.py`.

Was hier NICHT steht, ist die Rechenvorschrift als Code. Die bleibt im Viewer
(`OV_METRICS`), weil sie Code ist und keine Daten. Verbunden sind beide über
`id`; ein Test hält fest, dass die Mengen deckungsgleich bleiben.

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
METRICS = [
    {
        "id": "cet1", "label": "CET1-Quote", "unit": "%",
        "cells": [["61.00", "0050", "0010", "wert"]],
        "definition": "Hartes Kernkapital (CET1) im Verhältnis zum "
                      "Gesamtrisikobetrag (TREA).",
        "purpose": "Die zentrale Solvenzkennzahl: wie viel verlustabsorbierendes "
                   "Eigenkapital höchster Qualität steht hinter den gewichteten "
                   "Risiken?",
        "floor": 4.5, "floor_src": "CRR Art. 92 (1) (a) — Säule-1-Mindestquote",
        # BEWUSST kein `own_req`: KM1 r0190 ist die Anforderung an die
        # GESAMTkapitalquote. Neben die CET1-Quote gestellt suggeriert sie eine
        # Unterdeckung, wo keine ist — bei BNP Paribas 12,6 % CET1 gegen
        # 14,7 % OCR. Die bindende CET1-Anforderung (4,5 % + CET1-Anteil des
        # Säule-2-Aufschlags + kombinierte Pufferanforderung) wird in KM1 nicht
        # als eine Zahl gemeldet; sie zu rekonstruieren wäre eine Schätzung.
        "note": "Die für dieses Institut bindende CET1-Anforderung steht **nicht** "
                "als eine Zahl in KM1: sie setzt sich aus dem Säule-1-Boden, dem "
                "CET1-Anteil des Säule-2-Aufschlags und der kombinierten "
                "Pufferanforderung zusammen. Die gemeldete Gesamtanforderung "
                "(r0190) bezieht sich auf die **Gesamtkapitalquote** und gehört "
                "dorthin — siehe die Karten „Gesamtkapitalquote“ und "
                "„Headroom TC−OCR“.",
    },
    {
        "id": "tc", "label": "Gesamtkapitalquote", "unit": "%",
        "cells": [["61.00", "0070", "0010", "wert"]],
        "definition": "Gesamte Eigenmittel (CET1 + AT1 + Ergänzungskapital) im "
                      "Verhältnis zum Gesamtrisikobetrag.",
        "purpose": "Die weiteste Kapitalkennzahl — sie zählt auch nachrangige "
                   "Instrumente mit, die erst später als CET1 haften.",
        "floor": 8.0, "floor_src": "CRR Art. 92 (1) (c) — Säule-1-Mindestquote",
        # Hier passt r0190: die gemeldete Gesamtanforderung bezieht sich genau
        # auf diese Quote. Das ist die einzige Karte, auf der ein direkter
        # Vergleich Wert gegen Anforderung zulässig ist.
        "own_req": ["61.00", "0190", "0010"],
    },
    {
        "id": "hr", "label": "Headroom TC−OCR", "unit": "pp",
        "cells": [["61.00", "0070", "0010", "gesamtkapitalquote"],
                  ["61.00", "0190", "0010", "gesamtanforderung"]],
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
        "id": "lev", "label": "Verschuldungsquote", "unit": "%",
        "cells": [["61.00", "0220", "0010", "wert"]],
        "definition": "Kernkapital (T1) im Verhältnis zur Gesamtrisikoposition "
                      "der Verschuldungsquote — einer **ungewichteten** "
                      "Bezugsgröße.",
        "purpose": "Rückfalllinie gegen Modellrisiko: Sie ignoriert die "
                   "Risikogewichtung und fängt damit genau die Fälle, in denen "
                   "die gewichteten Quoten zu günstig aussehen.",
        "floor": 3.0, "floor_src": "CRR Art. 92 (1) (d) — Säule-1-Mindestquote",
    },
    {
        "id": "lcr", "label": "LCR", "unit": "%",
        "cells": [["61.00", "0320", "0010", "wert"]],
        "definition": "Liquiditätsdeckungsquote: hochliquide Aktiva im "
                      "Verhältnis zu den Nettomittelabflüssen eines "
                      "30-Tage-Stressszenarios.",
        "purpose": "Übersteht das Institut einen Monat akuten Liquiditätsstress "
                   "aus eigener Kraft?",
        "floor": 100.0,
        "floor_src": "Delegierte Verordnung (EU) 2015/61 — Mindestquote 100 %",
    },
    {
        "id": "nsfr", "label": "NSFR", "unit": "%",
        "cells": [["61.00", "0350", "0010", "wert"]],
        "definition": "Strukturelle Liquiditätsquote: verfügbare stabile "
                      "Refinanzierung im Verhältnis zur erforderlichen, über "
                      "einen Einjahreshorizont.",
        "purpose": "Das Gegenstück zur LCR auf lange Sicht — passt die "
                   "Fristigkeit der Refinanzierung zur Fristigkeit des Geschäfts?",
        "floor": 100.0, "floor_src": "CRR Art. 428b — Mindestquote 100 %",
    },
    {
        "id": "npl", "label": "NPL-Quote (CQ3)", "unit": "%",
        "cells": [["82.00.A", "0020", "0040", "notleidend"],
                  ["82.00.A", "0020", "0010", "bedient"]],
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
        "id": "trea", "label": "TREA", "unit": "Mrd EUR",
        "cells": [["61.00", "0040", "0010", "wert"]],
        "definition": "Gesamtrisikobetrag: die Summe aller risikogewichteten "
                      "Positionsbeträge, umgerechnet zum EZB-Referenzkurs.",
        "purpose": "Der Nenner der Kapitalquoten und zugleich das gebräuchlichste "
                   "Größenmaß — er macht die übrigen Quoten erst einordenbar.",
        "note": "Größe, keine Anforderung: eine Schwelle gibt es nicht.",
    },
]

METRIC_IDS = [m["id"] for m in METRICS]


def metric_payload():
    """Form für codebook.json. Ohne die Rechenvorschrift — die ist Code."""
    return METRICS
