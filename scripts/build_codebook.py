"""Phase 2: Build the fully-labelled DPM codebook from the DPM 2.0 Access dictionary
(pure-python access-parser — no pyodbc/mdbtools needed).

Resolution chain (pure ID joins, no fragile text matching):
    dp<n>  ==  Variable.VariableID
           ->  VariableVersion        (VariableID -> VariableVID)
           ->  TableVersionCell       (VariableVID -> TableVID + CellCode)
    CellCode "{K_61.00, r0010, c0010}"  ->  template, row, col
    TableVID -> TableVersion.Name      (template title)
    TableVID + ordinate -> HeaderVersion.Label  (row / column label)

The 4.2 DB stores several text fields with inconsistent, per-record Unicode packing
that access-parser mis-reads. `dpm_decode` brute-forces the candidate decodings and
keeps the one with the highest printable-ASCII ratio.
"""

from pathlib import Path
from collections import defaultdict
import csv
import re

# `access_parser` wird ERST IN main() importiert. Der Import auf Modulebene hat
# die Testsuite in CI vier Läufe lang rot gehalten: tests/test_open_axis.py
# importiert dieses Modul wegen parse_cellcode() und OPEN_AXIS — reine
# Funktionen ohne Datenbankbezug —, und der Testworkflow installiert bewusst
# nur duckdb + pyarrow. Ein ImportError beim Laden EINER Testdatei lässt
# unittest den ganzen Lauf als Fehlschlag melden.
#
# Die Abhängigkeit selbst ist der Grund, sie nicht in CI zu installieren: sie
# baut nur mit setuptools<60 und ohne Build-Isolation, und sie wird ausschließlich
# für den (opt-in) Codebook-Bau aus der 755-MB-DPM-Datenbank gebraucht.

ROOT = Path(__file__).resolve().parent.parent
# Cumulative DPM 2.0 dictionary (RF 4.0/4.1/4.2). Download (755 MB unzipped, gitignored):
#   https://www.eba.europa.eu/sites/default/files/2025-11/d67068fe-6327-4890-9163-3a9fcdabb58f/DPM2%20Database_v%204_2_20251125.zip
DB_PATH = ROOT / "codebook" / "DPM2_v4.2.accdb"
REPORT_CODES = ROOT / "codebook" / "mini_codebook_from_reports.csv"
LONGFORM = ROOT / "processed" / "long_form_raw.csv"   # zusätzliche dp-Quelle (Zustand)
OUT = ROOT / "codebook" / "dpm_codebook.csv"

# CellCode-Achsen: '{K_61.00, r0010, c0010}' — feste Koordinate, oder
# '{K_67.01.a, r*, c0010}' — OFFENE Zeilenachse. Das '*' ist die DPM-Schreibweise
# dafür, dass die Zeile nicht im Modell steht, sondern beim Einreichen aus einem
# Dimensionswert entsteht (bei CCyB1 das Land: eine Zeile je Staat).
#
# Das frühere Muster verlangte r(\w+) und traf '*' nicht — 308 Zellen zu 78
# Datenpunkten fielen still durch `if not parsed: continue`, und mit ihnen die
# SPALTE, die im CellCode sehr wohl steht. Das ist die Ursache von #56.
CELLCODE_RE = re.compile(r"\{([^,]+),\s*r([\w*]+),\s*c([\w*]+)")
OPEN_AXIS = "*"        # Marker im Codebook: Koordinate kommt aus einer offenen Achse


def _char_ok(c: str) -> bool:
    """Chars that count as 'text' when scoring decode candidates. ASCII plus the
    typographic Unicode that EBA labels legitimately contain (– — ' " €, Latin-1
    letters). CJK garbage from wrong byte order stays at zero."""
    o = ord(c)
    return (32 <= o < 127) or (0xA0 <= o <= 0x17F) or (0x2010 <= o <= 0x2027) or o == 0x20AC


def _printable_ratio(s: str) -> float:
    if not s:
        return -1.0
    return sum(1 for c in s if _char_ok(c)) / len(s)


_GP_MANGLED = re.compile(r"([\x10-\x1f])\x20")

# Dasselbe Byte-Paar-Problem, anderer Unicode-Block: ≤ (U+2264) und ≥ (U+2265)
# ueberleben als 'd"' bzw. 'e"' — low byte 0x64/0x65, high byte 0x22 als
# Anfuehrungszeichen. Aufgefallen an Adyens 82.00.A, wo die Spaltenkoepfe
# „Past due > 30 days d" 90 days" lauteten.
#
# BEWUSST als Tabelle statt als Regel `(.)"` -> chr(0x2200|ord(.)): eine
# allgemeine Regel wuerde jedes Zeichen vor einem Anfuehrungszeichen umdeuten
# und damit auch legitime Labels treffen (5" als Zollangabe etwa). Gemessen ueber
# das ganze Codebook kommen genau diese zwei Paare vor, 121x und 144x.
_MATH_MANGLED = {'d"': "≤", 'e"': "≥"}


def _repair_mangled_punct(s: str) -> str:
    """A UTF-16LE char from the General Punctuation block (U+2010–U+201F: – — ' ")
    sometimes survives decoding as its two bytes: a control char 0x10–0x1F followed by
    the 0x20 high byte rendered as a space. Recombine: chr(0x2000+low). Plain ASCII
    (e.g. '&' 0x26) is never touched.

    Die Mathematik-Operatoren ≤/≥ tragen dasselbe Muster mit druckbarem low byte
    und werden namentlich ersetzt — siehe `_MATH_MANGLED`."""
    s = _GP_MANGLED.sub(lambda m: chr(0x2000 + ord(m.group(1))), s)
    for kaputt, heil in _MATH_MANGLED.items():
        s = s.replace(kaputt, heil)
    return s


def dpm_decode(v) -> str:
    """Robustly decode an access-parser field against the 4.2 DB's mixed encodings."""
    if v is None:
        return ""
    if not isinstance(v, str):
        return str(v)
    cands = [v]
    if all(ord(c) < 256 for c in v):
        try:
            cands.append(v.encode("latin-1").decode("utf-16-le"))
        except Exception:
            pass
    bs = bytearray()
    for ch in v:
        bs += ord(ch).to_bytes(2, "big")
    cands.append(bs.decode("latin-1", "replace"))            # big-endian direct
    sw = bytearray()
    for k in range(0, len(bs) - 1, 2):
        sw += bytes([bs[k + 1], bs[k]])
    cands.append(sw.decode("latin-1", "replace"))            # byte-pair swapped
    i = bs.find(b"\xfe\xff")
    if i >= 0:                                                # BOM + swap (CellCode)
        p = bs[i + 2:]
        s2 = bytearray()
        for k in range(0, len(p) - 1, 2):
            s2 += bytes([p[k + 1], p[k]])
        cands.append(s2.decode("latin-1", "replace"))
    best = max(cands, key=_printable_ratio).replace("\x00", "").strip()
    return _repair_mangled_punct(best)


def _norm_ws(s: str) -> str:
    """Weissraumfolgen zu einem Leerzeichen. Fuer Labels aus der EBA-Layouttabelle,
    deren Zellenumbrueche als \\n im Text landen."""
    return re.sub(r"\s+", " ", s).strip() if s else s


def clean_text(s: str) -> str:
    """Drop values access-parser failed to decode (memo-overflow rows come back as
    binary junk). Keep only clean printable text."""
    if not s:
        return ""
    if any(ord(c) < 32 or ord(c) == 127 for c in s):
        return ""
    if _printable_ratio(s) < 0.85:
        return ""
    return s


def _direction(v) -> str:
    for c in dpm_decode(v):
        if c in "XYZ":
            return c
    return ""


def build_label_index(db):
    """Return title_by_tvid and label[(tvid, axis, ordinate)] = text."""
    tv = db.parse_table("TableVersion")
    title_by_tvid = {int(vid): clean_text(dpm_decode(name)) for vid, name in zip(tv["TableVID"], tv["Name"])}

    hdr = db.parse_table("Header")
    dir_by_hid = {int(h): _direction(d) for h, d in zip(hdr["HeaderID"], hdr["Direction"])}

    hv = db.parse_table("HeaderVersion")
    # Zeilenumbrueche normalisieren: sie stammen aus dem Zellenumbruch der
    # EBA-Layouttabelle, nicht aus dem Text. 213 Labels tragen sie und lesen
    # sich dadurch als "f Past due\n> 90 days\n<= 180 days". Nur Weissraum wird
    # zusammengefasst — kein Zeichen faellt weg.
    cl_by_hvid = {int(vid): (dpm_decode(c), _norm_ws(dpm_decode(l)))
                  for vid, c, l in zip(hv["HeaderVID"], hv["Code"], hv["Label"])}

    labels = {}
    tvh = db.parse_table("TableVersionHeader")
    for tvid, hid, hvid in zip(tvh["TableVID"], tvh["HeaderID"], tvh["HeaderVID"]):
        d = dir_by_hid.get(int(hid))
        if d not in ("X", "Y"):
            continue
        code, label = cl_by_hvid.get(int(hvid), ("", ""))
        if not code or not label:
            continue
        axis = "row" if d == "Y" else "col"
        labels[(int(tvid), axis, code.zfill(4))] = label
    return title_by_tvid, labels


# DataType table is a fixed 13-row dictionary; IDs verified against the 4.2 DB.
DATATYPE_BY_ID = {1: "integer", 2: "decimal", 3: "string", 4: "boolean", 5: "true",
                  6: "datetime", 7: "date", 8: "enum", 9: "monetary", 10: "percentage",
                  11: "uri", 12: "ordinal", 13: "string"}


def build_datatype_map(db):
    """VariableID -> data type name, via VariableVersion.PropertyID -> Property.DataTypeID.
    All versions of a variable share its property, so variable-level typing is exact."""
    prop = db.parse_table("Property")
    dt_by_prop = {int(p): DATATYPE_BY_ID.get(int(d), "")
                  for p, d in zip(prop["PropertyID"], prop["DataTypeID"]) if p and d}
    vv = db.parse_table("VariableVersion")
    id2dt = {}
    for varid, pid in zip(vv["VariableID"], vv["PropertyID"]):
        if varid in id2dt or not pid:
            continue
        dt = dt_by_prop.get(int(pid))
        if dt:
            id2dt[varid] = dt
    return id2dt


# --- Welche DPM-Releases unser Bestand überhaupt benutzt (#54) --------------
#
# Das DPM-Dictionary ist kumulativ: es führt jede Tabellenfassung mit, die es
# je gab, in fünf Releases. Ohne Filter landen Zeilenbeschriftungen und
# Platzierungen aus Fassungen im Codebook, die unser Korpus nie meldet — und
# `xbrl_csv_parser._load_codebook()` schlüsselt nur nach (dp, template) und
# nimmt dann die letzte Zeile der Datei. Gemessen: 31 Koordinaten mit zwei
# konkurrierenden Zeilenlabels (7.994 Fakten) und 73 (dp, Template)-Paare mit
# zwei Platzierungen.
#
# Die Zuordnung Release <-> Framework-Version ist gemessen, nicht geschätzt.
# Für jede Framework-Version wurde gezählt, welcher Anteil ihrer Fakten einen
# (Datenpunkt, Template)-Eintrag in der jeweiligen Release findet:
#
#     RF     Fakten      Release 3   Release 4   Release 5
#     4.1   2.231.690      25,3 %     100,0 %      95,9 %
#     4.2      63.534      34,6 %      97,6 %     100,0 %
#
# Jede Version wird von GENAU EINER Release vollständig gedeckt. RF 4.1 ist
# Release 4, RF 4.2 ist Release 5. Die Asymmetrie stützt es: 4,1 % der
# 4.1-Datenpunkte gibt es in 4.2 nicht mehr, 2,4 % der 4.2-Datenpunkte sind
# dort neu — genau das Bild eines Versionsschritts.
#
# Deshalb 4: alles davor ist Altbestand. Ein Filter auf 5 allein würde zwar
# auch die letzten Platzierungspaare beseitigen, aber 4,1 % der 4.1-Fakten
# (rund 91.500) unplatzierbar machen. Kommt eine RF 4.3, gehört diese Zahl
# geprüft — der Test in tests/test_placement_ambiguity.py hält sie fest.
MIN_RELEASE = 4


def alive_from(rel_range, min_release=MIN_RELEASE):
    """Gilt diese Fassung in `min_release` oder später?

    `EndReleaseID` ist EXKLUSIV — die Fassung gilt bis ausschließlich dieser
    Release. Das ist nicht dokumentiert, sondern gemessen: unter der
    inklusiven Lesart überlappen alle 31 mehrdeutigen Koordinaten in genau
    einer Release, unter der exklusiven sind alle 31 disjunkt. Eine Konvention,
    die 31 von 31 Fällen sauber trennt, ist die richtige.
    """
    _, end = rel_range
    return end is None or end == 0 or end > min_release


def prefer_live_placement(rows, live):
    """Konkurrierende Platzierungen auf die geltende Fassung reduzieren (#54).

    `rows`: Codebook-Zeilen mit `_tvid`; `live`: TableVIDs, die in MIN_RELEASE
    gelten. Liefert (Zeilen, Zahl der verworfenen).

    Greift NUR, wenn ein Datenpunkt in einem Template auf verschiedenen Zellen
    liegt UND die geltende Fassung eine echte Teilmenge davon platziert. Liegen
    alle konkurrierenden Zellen in derselben geltenden Fassung, bleibt alles
    stehen — dort ist die Mehrdeutigkeit echt (OV1: A-SA gegen A-IMA) und wird
    gemeldet statt stillschweigend aufgelöst.
    """
    by_pair = defaultdict(list)
    for r in rows:
        by_pair[(r["datapoint_code"], r["template"])].append(r)
    out, dropped = [], 0
    for _, group in sorted(by_pair.items()):
        coords = {(r["row"], r["col"]) for r in group}
        if len(coords) > 1:
            keep = [r for r in group if r["_tvid"] in live]
            if keep and {(r["row"], r["col"]) for r in keep} != coords:
                dropped += len(group) - len(keep)
                group = keep
        out.extend(group)
    return out, dropped


def live_tvids(db, min_release=MIN_RELEASE):
    """TableVIDs, die in `min_release` gelten — Start erreicht, Ende noch nicht."""
    tv = db.parse_table("TableVersion")
    return {int(v) for v, s, e in zip(tv["TableVID"], tv["StartReleaseID"],
                                      tv["EndReleaseID"])
            if (s or 1) <= min_release and alive_from((s, e), min_release)}


def build_resolution_maps(db, min_release=MIN_RELEASE):
    """VariableID -> set(VariableVID); VariableVID -> set((TableVID, decoded CellCode)).

    Tabellenfassungen, die vor `min_release` endeten, fallen heraus (#54).
    """
    vv = db.parse_table("VariableVersion")
    id2vid = defaultdict(set)
    for vid, varid in zip(vv["VariableVID"], vv["VariableID"]):
        id2vid[varid].add(vid)

    tv = db.parse_table("TableVersion")
    keep = {int(v) for v, s, e in zip(tv["TableVID"], tv["StartReleaseID"],
                                     tv["EndReleaseID"])
            if alive_from((s, e), min_release)}
    print(f"  TableVersions ab Release {min_release}: {len(keep)} von {len(tv['TableVID'])}")

    tvc = db.parse_table("TableVersionCell")
    vid2cell = defaultdict(set)
    dropped = 0
    for vvid, tvid, code in zip(tvc["VariableVID"], tvc["TableVID"], tvc["CellCode"]):
        if not code:
            continue
        if int(tvid) not in keep:
            dropped += 1
            continue
        vid2cell[vvid].add((int(tvid), dpm_decode(code)))
    print(f"  Zellen aus abgelösten Fassungen verworfen: {dropped:,}".replace(",", "."))
    return id2vid, vid2cell


def parse_cellcode(code: str):
    """'{K_67.01.a, r*, c0010}' -> ('K_67.01.a', '*', '0010'), sonst None.

    Ein '*' in row oder col heißt: diese Achse ist OFFEN — die Koordinate steht
    nicht im Modell, sondern entsteht beim Einreichen aus einem Dimensionswert.
    Der Aufrufer muss sie dort holen; der Rest des CellCodes (insbesondere die
    jeweils andere, feste Achse) ist verwertbar und darf nicht verloren gehen.
    """
    m = CELLCODE_RE.match(code.strip())
    if not m:
        return None
    return m.group(1).strip(), m.group(2), m.group(3)


ORDINATE_RE = re.compile(r"^\d{4}$")


def _wohlgeformt(code: str) -> bool:
    """Eine Modellkoordinate ist vierstellig — oder die offene Achse."""
    return code == OPEN_AXIS or bool(ORDINATE_RE.match(code))


def repair_truncated_ordinates(rows, axis="col"):
    """Abgeschnittene Koordinaten aus dem Modell der Schwesterzeilen herstellen.

    ## Der Befund

    Zwei Zellen im ganzen Codebook tragen den Spaltencode `00` statt der sonst
    durchgängigen vier Ziffern — beide in Zeile 0060:

        K_82.00.a r0060 c00   die Zeile hat 12 Spalten wie alle 14 Schwestern,
                              aber ihr fehlt 0060
        R_12.00.a r0060 c00   dieselbe Konstellation, dort fehlt 0080

    `00` ist in beiden Fällen der auf zwei Zeichen gekürzte echte Code. Bei
    Adyen N.V. hängt daran ein realer Wert (3.325,29 EUR): 82.00.A Spalte 0040
    ist die Summe ihrer Komponenten, und genau dieser Betrag fehlt darin.

    Der Wert war also nie verloren — er stand nur in einer namenlosen Spalte,
    und niemand konnte ihm ansehen, in welches Verzugsband er gehört.

    ## Warum das eine Regel und kein Raten ist

    Wiederhergestellt wird ausschliesslich, wenn das Modell die Antwort selbst
    erzwingt: Die Spaltenmenge des Templates ergibt sich aus allen wohlgeformten
    Codes seiner Zeilen. Fehlt der betroffenen Zeile daraus **genau eine**
    Spalte, und ist der kaputte Code ein **Präfix** davon, dann gibt es keine
    zweite Möglichkeit.

    Ist es nicht eindeutig, bleibt der Code kaputt und wird gemeldet. Lieber
    eine sichtbare Lücke als eine erfundene Koordinate (Arbeitsprinzip 3).

    Gibt (repariert, ungeklaert) zurueck — beide als Liste zum Ausgeben.
    """
    other = "row" if axis == "col" else "col"
    modell = defaultdict(set)
    for r in rows:
        if _wohlgeformt(r[axis]):
            modell[r["template"]].add(r[axis])

    belegt = defaultdict(set)
    for r in rows:
        if _wohlgeformt(r[axis]):
            belegt[(r["template"], r[other])].add(r[axis])

    repariert, ungeklaert = [], []
    for r in rows:
        if _wohlgeformt(r[axis]):
            continue
        kaputt = r[axis]
        kandidaten = {c for c in modell[r["template"]] - belegt[(r["template"], r[other])]
                      if c.startswith(kaputt)}
        if len(kandidaten) == 1:
            heil = kandidaten.pop()
            repariert.append((r["template"], r[other], kaputt, heil, r["datapoint_code"]))
            r[axis] = heil
        else:
            ungeklaert.append((r["template"], r[other], kaputt, sorted(kandidaten)))
    return repariert, ungeklaert


def load_template_titles():
    """Authoritative template titles from the EBA Annotated Table Layout TOC
    (extract_template_titles.py). Keyed by DPM code 'K_61.00'. Empty if absent."""
    path = ROOT / "codebook" / "template_titles.csv"
    titles = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                titles[r["template"]] = r["title"]
        # base fallback: a sheet variant like K_19.02.d reuses K_19.02.<any> title
        for code, title in list(titles.items()):
            parts = code.split(".")
            if len(parts) == 3 and len(parts[-1]) == 1:  # K_NN.NN.x
                titles.setdefault(".".join(parts[:2]), title)
    return titles


def title_for(tmpl: str, titles: dict) -> str:
    """Exact match, else fall back to the base template (drop sheet sub-letter)."""
    if tmpl in titles:
        return titles[tmpl]
    parts = tmpl.split(".")
    if len(parts) == 3 and len(parts[-1]) == 1:
        return titles.get(".".join(parts[:2]), "")
    return ""


def load_report_codes(path: Path, longform: Path = None):
    """dp-Codes, für die Labels aufgelöst werden sollen.

    Basis ist `mini_codebook_from_reports.csv` (aus den Roh-ZIPs, committet).
    Zusätzlich wird — falls vorhanden — die Long Form ausgewertet: sie ist der
    Zustand, der zwischen Läufen übertragen wird, und enthält damit auch die
    dp-Codes neuer Wellen. Auf einem zustandslosen Runner ist `raw/` leer, das
    Mini-Codebook also veraltet; ohne diese Vereinigung blieben neue Codes
    unaufgelöst und ihre Fakten unplatzierbar.
    """
    seen = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            seen[r["datapoint_code"]] = r.get("frequency", "")

    if longform and longform.exists():
        before = len(seen)
        with open(longform, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                dp = (r.get("datapoint_code") or "").strip()
                if dp:
                    seen.setdefault(dp, "")
        if len(seen) > before:
            print(f"  +{len(seen) - before} dp-Codes aus der Long Form ergänzt")

    out = []
    for dp, freq in sorted(seen.items()):
        digits = dp.replace("dp", "")
        if digits.isdigit():
            out.append((dp, int(digits), freq))
    return out


def main():
    from access_parser import AccessParser   # siehe Kommentar am Dateikopf

    print(f"Reading DPM dictionary: {DB_PATH.name}")
    db = AccessParser(str(DB_PATH))
    print("  building label index...")
    title_by_tvid, labels = build_label_index(db)
    print("  building resolution maps...")
    id2vid, vid2cell = build_resolution_maps(db)
    id2dt = build_datatype_map(db)
    title_csv = load_template_titles()
    print(f"  template titles (EBA layout): {len(title_csv)}")

    report_codes = load_report_codes(REPORT_CODES, LONGFORM)
    print(f"Resolving {len(report_codes)} datapoint codes...")

    rows = []
    resolved = 0
    unparsed = defaultdict(int)     # CellCode-Formen, die das Muster nicht trifft
    for dp_str, dp_int, freq in report_codes:
        cells = set()
        for vvid in id2vid.get(dp_int, ()):
            cells |= vid2cell.get(vvid, set())
        if not cells:
            rows.append({"datapoint_code": dp_str, "variable_id": dp_int, "template": "",
                         "row": "", "col": "", "template_title": "", "row_label": "",
                         "col_label": "", "data_type": id2dt.get(dp_int, ""), "frequency": freq})
            continue
        resolved += 1
        for tvid, code in sorted(cells):
            parsed = parse_cellcode(code)
            if not parsed:
                # NICHT stillschweigend fallen lassen: genau dieses `continue`
                # hat 308 Zellen verschluckt, ohne eine Spur zu hinterlassen
                # (#56). Wer die Zahl am Ende sieht, kann sie prüfen.
                unparsed[code.strip()] += 1
                continue
            tmpl, row, col = parsed
            rows.append({
                "datapoint_code": dp_str, "variable_id": dp_int,
                "template": tmpl, "row": row, "col": col,
                "template_title": title_for(tmpl, title_csv) or title_by_tvid.get(tvid, ""),
                # Für eine offene Achse gibt es kein Label im Modell — die
                # Beschriftung ist der Dimensionswert selbst (bei CCyB1 der
                # Ländername). Leer lassen statt einen Platzhalter erfinden.
                "row_label": "" if row == OPEN_AXIS
                             else labels.get((tvid, "row", row.zfill(4)), ""),
                "col_label": "" if col == OPEN_AXIS
                             else labels.get((tvid, "col", col.zfill(4)), ""),
                "data_type": id2dt.get(dp_int, ""),
                "frequency": freq,
                "_tvid": tvid,
            })

    # A datapoint resolves through several table-version releases that collapse to the
    # same (template, row, col); keep the most complete-labelled variant per cell.
    best = {}
    for r in rows:
        key = (r["datapoint_code"], r["template"], r["row"], r["col"])
        completeness = len(r["template_title"]) + len(r["row_label"]) + len(r["col_label"])
        if key not in best or completeness > best[key][0]:
            best[key] = (completeness, r)
    rows = [r for _, r in best.values()]

    # --- Vorzugsregel bei konkurrierenden Platzierungen (#54) --------------
    #
    # Bis hierher deduplizieren wir je (dp, template, row, col). Legt ein
    # Datenpunkt aber auf VERSCHIEDENE Zellen desselben Templates, überleben
    # beide — und `xbrl_csv_parser._load_codebook()` schlüsselt nur nach
    # (dp, template) und nimmt die letzte Zeile der Datei, also die höchste
    # (Zeile, Spalte). Das ist deterministisch, aber es hat mit der Wahrheit
    # nichts zu tun: gemessen wählt es bei 14 von 26 auflösbaren Paaren die
    # falsche Zelle. In K_26.01 landen dadurch Werte durchweg in c0050,
    # während c0040 leer bleibt.
    #
    # Auflösbar sind die Fälle, in denen die Platzierungen aus verschiedenen
    # Releases stammen — der Framework-Bruch aus #26. Dann gilt die Fassung
    # aus MIN_RELEASE: unser Bestand ist zu 97,2 % RF 4.1, und auf genau
    # diesen Paaren liegt KEIN einziger RF-4.2-Fakt. Es gibt also nichts zu
    # unterscheiden, sondern nur eine richtige Zelle.
    #
    # Ein Schlüssel (dp, template, framework_version) leistete dasselbe, würde
    # aber das Codebook-Format, den Kern-Lookup des Parsers und sechs weitere
    # Skripte anfassen — und eine neue Art schaffen, Fakten zu verlieren
    # (Datenpunkt ohne Eintrag für seine Version). Für 0,06 % des Bestands.
    #
    # Bleiben mehrere Platzierungen AUS DERSELBEN Fassung übrig, ändert die
    # Regel nichts: dort ist die Mehrdeutigkeit echt und wird unten gemeldet.
    rows, dropped_stale = prefer_live_placement(rows, live_tvids(db))
    if dropped_stale:
        print(f"  Platzierungen aus abgelösten Fassungen verworfen: {dropped_stale}")

    # Abgeschnittene Koordinaten herstellen — NACH dem Release-Filter.
    #
    # Zuerst stand das vor der Deduplizierung, und dort greift es nicht: solange
    # die Fassungen mehrerer DPM-Releases nebeneinander liegen, trägt Zeile 0060
    # bereits ein wohlgeformtes '0060' aus einer anderen Fassung. Die Lücke, aus
    # der die Regel ihre Eindeutigkeit zieht, ist dann gar nicht leer — die Regel
    # verweigert korrekt, und der kaputte Code überlebt.
    #
    # Erst hier ist der Zeilenbestand der, den das Codebook auch ausliefert.
    for achse in ("col", "row"):
        heil, offen = repair_truncated_ordinates(rows, achse)
        for tmpl, andere, kaputt, neu, dp in heil:
            print(f"  Koordinate hergestellt: {tmpl} {andere} {achse} "
                  f"'{kaputt}' -> '{neu}'  ({dp})")
        for tmpl, andere, kaputt, kand in offen:
            print(f"  ⚠ {achse}-Code '{kaputt}' in {tmpl} {andere} nicht eindeutig "
                  f"herstellbar — Kandidaten: {kand or 'keine'}")
        # Das Label hängt an der Koordinate: nach der Reparatur neu nachschlagen.
        for tmpl, andere, kaputt, neu, dp in heil:
            for r in rows:
                if r["template"] == tmpl and r[achse] == neu and r["datapoint_code"] == dp:
                    r[f"{achse}_label"] = labels.get((r["_tvid"], achse, neu.zfill(4)), "")

    for r in rows:
        r.pop("_tvid", None)
    rows.sort(key=lambda r: (r["template"], r["row"], r["col"], r["datapoint_code"]))

    fields = ["datapoint_code", "variable_id", "template", "row", "col",
              "template_title", "row_label", "col_label", "data_type", "frequency"]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    labelled = sum(1 for r in rows if r["row_label"] or r["col_label"])
    open_row = sum(1 for r in rows if r["row"] == OPEN_AXIS)
    open_col = sum(1 for r in rows if r["col"] == OPEN_AXIS)
    print(f"\n✓ Codebook: {OUT}")
    print(f"  Datapoints resolved: {resolved}/{len(report_codes)} ({100*resolved//len(report_codes)}%)")
    print(f"  Codebook rows (incl. multi-cell): {len(rows)}")
    print(f"  Rows with axis label: {labelled}")
    print(f"  Offene Zeilenachse (r*): {open_row}   offene Spaltenachse (c*): {open_col}")
    if unparsed:
        # Sichtbar machen, nicht verschweigen — siehe #56.
        total = sum(unparsed.values())
        print(f"  ⚠ CellCodes ohne Muster-Treffer: {total} in {len(unparsed)} Formen")
        for code, n in sorted(unparsed.items(), key=lambda kv: (-kv[1], kv[0]))[:5]:
            print(f"      {n:5d}x  {code}")

    # --- Mehrdeutige Platzierung (#54) -------------------------------------
    # Der Release-Filter oben nimmt den größten Teil weg: 73 -> 12 Paare, und
    # die 31 Koordinaten mit konkurrierenden Zeilenlabels verschwinden ganz.
    #
    # Was bleibt, ist eine andere Sache und NICHT über Versionen auflösbar:
    # dieselbe Variablenfassung liegt in derselben Tabellenfassung auf zwei
    # verschiedenen Zellen. In OV1 sind das „21. Of which the Alternative
    # standardised approach (A-SA)" und „22. Of which the Alternative Internal
    # Models Approach (A-IMA)" — zwei Ansätze, nicht zwei Schreibweisen. Die
    # Meldung hilft nicht weiter: OV1 trägt keine einzige Dimension, die Zeile
    # steht dort nirgends.
    #
    # Der Parser schlüsselt nur nach (dp, template) und nimmt die letzte Zeile
    # der Datei. Für eine der beiden Zellen ist das falsch — sichtbar daran,
    # dass die gewählte Zeile doppelt so viele Datenpunkte trägt wie ihre
    # Nachbarn, während die andere fast leer bleibt. Das darf nicht schweigend
    # passieren.
    placed = defaultdict(set)
    for r in rows:
        if r["template"]:
            placed[(r["datapoint_code"], r["template"])].add((r["row"], r["col"]))
    multi = {k: v for k, v in placed.items() if len(v) > 1}
    if multi:
        by_tmpl = defaultdict(int)
        for dp, tmpl in multi:
            by_tmpl[tmpl] += 1
        print(f"  ⚠ Nicht eindeutig platziert: {len(multi)} (dp, Template)-Paare — "
              f"der Parser wählt dort willkürlich (#54)")
        for tmpl, n in sorted(by_tmpl.items(), key=lambda kv: (-kv[1], kv[0]))[:6]:
            print(f"      {n:5d}x  {tmpl}")


if __name__ == "__main__":
    main()
