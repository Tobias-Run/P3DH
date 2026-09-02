"""Determinismus als Zusage statt als Glücksache.

Dieselbe Fehlerklasse hat im Projekt dreimal zugeschlagen: eine Ausgabe ändert
sich zwischen zwei Läufen auf UNVERÄNDERTEN Eingaben, ohne dass irgendetwas
fehlschlägt. Gefunden wurde sie jedes Mal beiläufig und nachträglich; repariert
jedes Mal, indem eine Spalte mehr an den ORDER BY gehängt wurde, bis der Churn
verschwand. Das ist Symptombehandlung — sie sagt nicht, wann man fertig ist.

Die Invariante, die hier durchgesetzt wird, ist präziser und stärker als
"der Sortierschlüssel muss eindeutig sein":

    Jedes Feld, das in die AUSGABE fließt, muss im Sortierschlüssel stehen.

Dann sind zwei Zeilen einer Tie-Gruppe in der Ausgabe ununterscheidbar und ihre
Vertauschung ist folgenlos. Der Sortierschlüssel darf also Ties haben — er muss
nur alles abdecken, was sichtbar wird. (Im Shard-Build bleiben nach dem Fix
3.695 Tie-Gruppen übrig; sie sind genau deshalb unschädlich.)

Warum eine SQL-Zusage und kein Byte-Vergleich? Weil ein Byte-Vergleich einen
zweiten Volllauf kostet und die Fehlerklasse nur ENTDECKT. Der Guard hier macht
sie schwer begehbar: wer eine Spalte in die Projektion aufnimmt und die
Sortierung nicht nachzieht, bekommt einen harten Abbruch statt einer stillen
Lücke. `tests/test_determinism.py` ergänzt den Byte-Vergleich auf Mini-Daten
für alles, was SQL nicht abdeckt (Set-Iteration in Python).

GRENZEN — bewusst und ehrlich: das hier ist ein Textcheck, kein SQL-Parser.
Er versteht die einfachen Projektionen dieser Pipeline. Was er nicht sicher
beurteilen kann, LEHNT ER AB (fail closed), statt es stillschweigend
durchzuwinken — ein Guard, der im Zweifel "ok" sagt, ist schlimmer als keiner.
"""

import re

# Aggregate, deren Ergebnis unabhängig von der Eingabereihenfolge ist. Alles
# andere ist in einer Query, deren Ergebnis in eine Datei fließt, ein Risiko:
# any_value()/first()/last()/arbitrary() greifen sich ein beliebiges Element,
# string_agg()/list()/array_agg() erben ohne eigenes ORDER BY die Zufallsordnung.
DETERMINISTIC_AGGREGATES = {
    "count", "sum", "min", "max", "avg", "mean", "median",
    "bool_and", "bool_or", "bit_and", "bit_or", "bit_xor",
    "stddev", "stddev_pop", "stddev_samp", "var_pop", "var_samp",
}

# Sammelnde Aggregate: reihenfolgeabhängig, aber mit einem eigenen ORDER BY
# im Argument (`list(x ORDER BY x)`) wieder zugesichert.
ORDER_SENSITIVE_AGGREGATES = {"list", "array_agg", "string_agg", "group_concat", "histogram"}

_COMMENT = re.compile(r"--[^\n]*")
_SELECT = re.compile(r"\bSELECT\b\s+(?:DISTINCT\s+)?(.*?)\s+\bFROM\b", re.S | re.I)
_ORDER = re.compile(r"\bORDER\s+BY\b\s+(.*?)(?:\bLIMIT\b|\bOFFSET\b|;|\Z)", re.S | re.I)
_GROUP = re.compile(
    r"\bGROUP\s+BY\b\s+(.*?)(?:\bHAVING\b|\bORDER\s+BY\b|\bLIMIT\b|;|\Z)", re.S | re.I)
_ALIAS = re.compile(r"\s+AS\s+(\w+)\s*$", re.I)
_FUNC = re.compile(r"^(\w+)\s*\(")


FILL = "\x00"   # Füllzeichen der Maske: KEIN Whitespace, sonst würde
                # `SELECT a, max(x) FROM` in der Maske zu `SELECT a, max      FROM`
                # und das non-greedy `(.*?)\s+FROM` schnitte die letzte Spalte ab.


def mask_nested(sql):
    """Alles in Klammern und in Stringliteralen durch FILL ersetzen.

    Damit greifen die Keyword-Regexe NUR auf der äußersten Ebene. Ohne das
    würde bei `WITH num AS (SELECT ...) SELECT ...` die Projektion der CTE
    geprüft statt die der äußeren Query — der Guard urteilte über die falsche
    Query und hielte eine unsortierte Ausgabe für sauber. Die Maske ist
    positionsgleich zum Original, die Inhalte werden über Indizes daraus
    geschnitten.
    """
    out, depth, in_str = [], 0, False
    for ch in sql:
        if in_str:
            out.append(FILL)
            if ch == "'":
                in_str = False
            continue
        if ch == "'":
            in_str = True
            out.append(FILL)
            continue
        if ch in "()":
            depth += 1 if ch == "(" else -1
            depth = max(0, depth)
            out.append(FILL)
            continue
        out.append(FILL if depth else ch)
    return "".join(out)


class NonDeterministic(AssertionError):
    """Die Query kann zwischen zwei Läufen verschiedene Ausgaben liefern."""


def strip_comments(sql):
    return _COMMENT.sub("", sql)


def split_top_level(s):
    """Kommagetrennte Liste auf oberster Klammerebene ('max(a, b), c' -> 2)."""
    out, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def parse_select(sql):
    """-> (projection, order_by, group_by) als Listen normalisierter Ausdrücke.

    Ordinalzahlen ('ORDER BY 1, 2') werden gegen die Projektion aufgelöst,
    Aliase abgeschnitten, Richtungsangaben (ASC/DESC/NULLS LAST) entfernt.
    """
    sql = strip_comments(sql)
    mask = mask_nested(sql)
    if len(re.findall(r"\bUNION\b|\bINTERSECT\b|\bEXCEPT\b", mask, re.I)):
        raise NonDeterministic("Mengenoperation (UNION/…) — Guard kann nicht urteilen, "
                               "bitte von Hand prüfen oder umformulieren")
    m = _SELECT.search(mask)
    if not m:
        raise NonDeterministic("SELECT ... FROM nicht erkannt — Guard kann nicht urteilen")
    # Keywords in der MASKE finden, Inhalte aus dem ORIGINAL schneiden.
    projection = [_norm_proj(c) for c in split_top_level(sql[m.start(1):m.end(1)])]

    def resolve(part):
        items = []
        for raw in split_top_level(part):
            e = re.sub(r"\s+(ASC|DESC)\b", "", raw, flags=re.I)
            e = re.sub(r"\s+NULLS\s+(FIRST|LAST)\b", "", e, flags=re.I).strip()
            if e.isdigit():                      # Ordinal gegen die Projektion
                idx = int(e) - 1
                if not 0 <= idx < len(projection):
                    raise NonDeterministic(f"ORDER/GROUP BY {e} zeigt an der Projektion vorbei")
                e = projection[idx][0]
            items.append(_bare(e))
        return items

    mo, mg = _ORDER.search(mask), _GROUP.search(mask)
    return (projection,
            resolve(sql[mo.start(1):mo.end(1)]) if mo else [],
            resolve(sql[mg.start(1):mg.end(1)]) if mg else [])


def _norm_proj(col):
    """'max(x) AS y' -> ('max(x)', 'y'); 'a.b' -> ('a.b', None)."""
    m = _ALIAS.search(col)
    return (_ALIAS.sub("", col).strip(), m.group(1)) if m else (col.strip(), None)


def _bare(e):
    """Tabellenpräfix und Whitespace weg: 'num.lei' -> 'lei'."""
    e = re.sub(r"\s+", "", e)
    return e.split(".")[-1] if re.fullmatch(r"\w+\.\w+", e) else e


def aggregate_of(expr):
    """Aggregatname eines Projektionsausdrucks, sonst None."""
    m = _FUNC.match(expr.strip())
    return m.group(1).lower() if m else None


def assert_total_order(sql, what=""):
    """Zusage: das Ergebnis dieser Query ist zeilenweise reproduzierbar.

    Wirft NonDeterministic, wenn eine projizierte Spalte nicht im
    Sortierschlüssel steht — denn genau dann entscheidet die Zufallsreihenfolge
    (DuckDB sortiert parallel; Ties wandern zwischen Läufen), welcher Wert in
    der Ausgabe landet.

    Aggregierte Projektionen sind erlaubt, wenn die Query ein GROUP BY hat,
    dessen Schlüssel vollständig sortiert wird UND das Aggregat selbst
    reihenfolgeunabhängig ist.
    """
    projection, order_by, group_by = parse_select(sql)
    tag = f" [{what}]" if what else ""
    if not order_by:
        raise NonDeterministic(f"Query ohne ORDER BY{tag} — Zeilenreihenfolge ist beliebig")

    ordered = set(order_by)
    if group_by:
        missing_g = [g for g in group_by if g not in ordered]
        if missing_g:
            raise NonDeterministic(
                f"GROUP-BY-Schlüssel nicht sortiert{tag}: {', '.join(missing_g)}")

    problems = []
    for expr, alias in projection:
        if _bare(expr) in ordered or (alias and _bare(alias) in ordered):
            continue
        agg = aggregate_of(expr)
        if agg is None:
            problems.append(f"{expr} — projiziert, aber nicht sortiert")
        elif not group_by:
            problems.append(f"{expr} — Aggregat ohne GROUP BY")
        elif agg in ORDER_SENSITIVE_AGGREGATES:
            # list()/string_agg() erben ohne eigenes ORDER BY die Zufallsordnung
            # der Eingabe — mit einem sind sie zugesichert.
            if not re.search(r"\bORDER\s+BY\b", expr, re.I):
                problems.append(f"{expr} — {agg}() ohne eigenes ORDER BY erbt die "
                                "Zufallsreihenfolge der Eingabe")
        elif agg not in DETERMINISTIC_AGGREGATES:
            problems.append(f"{expr} — {agg}() hängt von der Eingabereihenfolge ab")
    if problems:
        raise NonDeterministic(
            f"Nicht reproduzierbare Ausgabe{tag}:\n    " + "\n    ".join(problems)
            + "\n  Regel: jedes Feld, das in die Ausgabe fließt, gehört in den ORDER BY."
            + "\n  (scripts/determinism.py erklärt, warum.)")
    return True


def ordered_query(con, sql, what=""):
    """Query ausführen — aber nur, wenn ihre Zeilenreihenfolge ZUGESICHERT ist.

    Der Guard sitzt bewusst im Ausführungspfad und nicht bloß in einem Test:
    eine vergessene ORDER-BY-Spalte hat kein Fehlerbild, sie erzeugt nur eine
    Ausgabe, die zwischen Läufen wandert. Wer hier eine Spalte in die Projektion
    aufnimmt und die Sortierung nicht nachzieht, bekommt einen Abbruch statt
    einer stillen Lücke.
    """
    assert_total_order(sql, what)
    return con.execute(sql).fetchall()
