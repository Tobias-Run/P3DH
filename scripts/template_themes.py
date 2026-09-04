"""Kuratierte Themenzuordnung der Offenlegungstemplates (#47, R2).

Der Report-Blick zeigte 136 Tabellen gleichrangig in Codereihenfolge — das
Erste nach dem Einstieg war eine fast leere Krypto-Tabelle, weil `01.00`
alphabetisch vorn steht. `docs/mehrwert_vs_edap.md` beansprucht für uns die
„kuratierte, urteilende Sicht — nicht die vollständige"; genau die fehlte hier.

**Warum kuratiert und nicht abgeleitet.** Eine Gruppierung nach Codepräfix wäre
in zwei Zeilen zu haben und würde wieder Aufsichtssystematik statt Bedeutung
abbilden — dasselbe Problem, das die Nummerierung schon hat: `19.xx` ist
operationelles Risiko, `20.xx` Asset Encumbrance, `21.xx` Kreditrisiko, ohne
dass die Nachbarschaft etwas bedeutet. Die Zuordnung unten ist deshalb von Hand
gesetzt, je Basistemplate, nach dem, worüber das Template Auskunft gibt.

**Schlüssel ist das BASISTEMPLATE** (`60.00`, nicht `60.00.A`): die Buchstaben-
Suffixe sind Teilblätter desselben Templates und gehören immer zusammen.

Die Registry wird von `build_zweig_a_shards.py` nach `codebook.json` geschrieben
und vom Viewer gelesen — eine Quelle für Oberfläche und Auswertung. Templates
ohne Eintrag verschwinden NICHT; sie landen im Block „Nicht zugeordnet". Das
ist die Sicherung gegen genau den Fehler, den R2 vermeiden soll: kuratieren
heißt Reihenfolge und Sichtbarkeit ändern, nicht Daten weglassen.
"""

# Reihenfolge = Anzeigereihenfolge im Report. Kapital zuerst, weil dort die
# Kennzahlen liegen, nach denen zuerst gesucht wird; die Narrative zuletzt.
THEMES = [
    ("kapital", "Kapital, Eigenmittel & Verschuldung", [
        "60.00",   # OV1  — Überblick Risikopositionsbeträge
        "61.00",   # KM1  — Kennzahlen
        "62.01", "62.02",           # INS1/INS2 — Versicherungsbeteiligungen
        "63.01", "63.02",           # CMS1/CMS2 — Modell vs. Standardansatz
        "64.01", "64.02", "64.03",  # LI1/LI3/LI2 — Rechnungslegung vs. Aufsicht
        "65.00",                    # PV1  — vorsichtige Bewertung
        "66.01", "66.02",           # CC1/CC2 — Zusammensetzung der Eigenmittel
        "67.01", "67.02",           # CCyB1/CCyB2 — antizyklischer Puffer
        "70.00", "71.00", "72.00",  # LR1/LR2/LR3 — Verschuldungsquote
    ]),
    ("kredit", "Kreditrisiko", [
        "21.01", "21.02",           # CR1, CR1-A
        "22.01", "22.02",           # CR2, CR2a
        "23.00", "24.00", "25.00",  # CR3, CR4, CR5
        "26.00", "26.01",           # CR6, CR6-A
        "27.01", "27.02",           # CR7, CR7-A
        "28.00", "29.00", "29.01", "29.02",   # CR8, CR9, CR9.1, CR10
    ]),
    # Bewusst NICHT mit dem Kreditrisiko zusammengelegt, obwohl beide "Kredit"
    # heißen: CR beschreibt die Messung des Risikos (Ansätze, RWEA, PD-Bänder),
    # CQ den Zustand des Bestands (notleidend, gestundet, Sicherheiten). Wer
    # NPL-Quoten sucht, sucht nicht CR6. Zusammen wären es 23 Templates in
    # einem Block — die Gliederung wäre wieder eine Wand.
    ("kreditqualitaet", "Kreditqualität & notleidende Kredite", [
        "80.00", "81.00", "82.00",  # CQ1, CQ2, CQ3
        "83.01", "84.01",           # CQ4, CQ5
        "85.00", "86.00", "87.00",  # CQ6, CQ7, CQ8
    ]),
    ("markt", "Markt-, Gegenpartei- & Zinsrisiko", [
        "02.00", "03.00", "04.00", "05.00", "06.00", "07.00", "08.00",  # CCR1–CCR8
        "10.00", "11.00", "12.00", "13.00",                             # MR1–MR3
        "18.01", "18.02", "18.03", "18.04",                             # CVA1–CVA4
        "68.00",   # IRRBB1 — Zinsrisiko im Anlagebuch
    ]),
    ("verbriefung", "Verbriefungen", [
        "09.01", "09.02", "09.03", "09.04", "09.05",   # SEC1–SEC5
    ]),
    ("oprisk", "Operationelles Risiko", [
        "19.01", "19.02", "19.03",   # OR1–OR3
    ]),
    ("liquiditaet", "Liquidität & Belastung von Vermögenswerten", [
        "20.01", "20.02", "20.03",   # AE1–AE3
        "73.00", "74.00",            # LIQ1 (LCR), LIQ2 (NSFR)
    ]),
    ("abwicklung", "Abwicklung: MREL & TLAC", [
        "90.01",            # KM2
        "91.00", "93.00",   # TLAC1, ILAC
        "95.00", "96.00", "97.00", "98.00",   # TLAC2a/2b/3a/3b
    ]),
    ("esg", "ESG & Klimarisiko", [
        "41.00", "42.00", "43.00", "44.00", "45.00",   # Transitions-/physisches Risiko
        "46.00", "47.00", "48.00",                     # GAR
        "49.01", "49.02", "49.03",                     # BTAR
        "50.00",                                       # sonstige Maßnahmen
    ]),
    ("verguetung", "Vergütung", [
        "30.01", "30.02", "30.03", "30.04", "30.05",   # REM1–REM5
    ]),
    ("gsii", "G-SII-Indikatoren", [
        "100.00", "101.00", "102.00", "103.00", "104.00", "105.00", "106.00",
        "107.00", "108.00", "109.00", "110.00", "111.00", "112.00", "113.00",
    ]),
    # Krypto-Exposure steht hier, nicht im Kreditrisiko: `01.00` (CAE1) meldet
    # Positionen in Kryptowerten als eigene Kategorie. Der Block trägt außerdem
    # die erläuternden Freitexte je Modul.
    ("sonstige", "Weitere Angaben", [
        "01.00",                                                  # CAE1 — Kryptowerte
        "00.01", "00.02", "00.03", "00.04", "00.05", "00.06",     # Narrative je Modul
    ]),
]

# Basistemplate -> Themen-ID
THEME_OF = {tid: key for key, _label, tids in THEMES for tid in tids}


def theme_payload():
    """Form für codebook.json: Reihenfolge + Zuordnung, ohne Wiederholung."""
    return {"order": [[key, label] for key, label, _ in THEMES], "map": THEME_OF}
