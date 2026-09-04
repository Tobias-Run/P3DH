"""Die Testsuite darf nur importieren, was der Testworkflow installiert.

## Der Vorfall

`scripts/build_codebook.py` importierte `access_parser` auf Modulebene.
`tests/test_open_axis.py` importiert dieses Modul wegen `parse_cellcode()` und
`OPEN_AXIS` — reine Funktionen ohne jeden Datenbankbezug. Der Testworkflow
installiert bewusst nur `duckdb` und `pyarrow`, weil `access_parser` nur mit
`setuptools<60` und ohne Build-Isolation baut und ausschließlich für den
opt-in-Codebook-Bau gebraucht wird.

Folge: `ImportError` beim Laden EINER Testdatei, und unittest meldet den
gesamten Lauf als Fehlschlag. **Vier Läufe auf `main` waren rot**, ohne dass es
auffiel — lokal ist das Paket installiert, dort blieb alles grün.

## Warum ein Test und nicht nur der Fix

Es ist derselbe Fehlermodus wie in `docs/reproduzierbarkeit.md`: der Unterschied
zwischen Entwicklungsrechner und Ausführungsumgebung schlägt still zu. Dieselbe
Falle steht mit `openpyxl` (Template-Titel), `playwright` (Harvest), `requests`
und `pandas` unverändert bereit. Der Test prüft deshalb nicht den Einzelfall,
sondern die Regel — und liest die erlaubte Menge aus dem Workflow selbst, damit
er nicht gegen eine zweite, gepflegte Liste läuft.
"""

from pathlib import Path
import ast
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
TESTS = ROOT / "tests"
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


def ci_packages():
    """Die Pakete aus der `pip install`-Zeile des Testworkflows."""
    src = WORKFLOW.read_text(encoding="utf-8")
    m = re.search(r"run:\s*pip install ([^\n]+)", src)
    if not m:
        return set()
    # Paket- zu Importname; nur nötig, wo sie auseinanderfallen.
    alias = {"access-parser": "access_parser"}
    out = set()
    for tok in m.group(1).split():
        if tok.startswith("-"):
            continue
        name = re.split(r"[<>=!\[]", tok)[0].strip()
        out.add(alias.get(name, name.replace("-", "_")))
    return out


def toplevel_imports(path):
    """Module, die beim IMPORT dieser Datei geladen werden.

    Nur was auf Modulebene steht — ein Import in einer Funktion läuft erst beim
    Aufruf und ist genau das Mittel, mit dem eine schwere optionale Abhängigkeit
    aus dem Importpfad genommen wird.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = set()
    stack = [(n, True) for n in tree.body]
    while stack:
        node, top = stack.pop()
        if not top:
            continue
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                out.add(node.module.split(".")[0])
        elif isinstance(node, (ast.If, ast.Try, ast.With)):
            # Läuft ebenfalls beim Import — mitnehmen.
            for field in ("body", "orelse", "finalbody", "handlers"):
                for child in getattr(node, field, []) or []:
                    if isinstance(child, ast.ExceptHandler):
                        stack.extend((c, True) for c in child.body)
                    else:
                        stack.append((child, True))
    return out


class CiImportSurfaceTest(unittest.TestCase):
    def setUp(self):
        self.allowed = ci_packages()
        self.local = {p.stem for p in SCRIPTS.glob("*.py")}
        self.stdlib = set(sys.stdlib_module_names)

    def test_the_workflow_still_names_its_packages(self):
        """Ohne erkannte pip-Zeile prüft der Test nichts mehr und wäre eine
        Attrappe."""
        self.assertTrue(self.allowed, f"keine pip-install-Zeile in {WORKFLOW.name}")
        self.assertIn("duckdb", self.allowed)

    def _reachable_scripts(self):
        """Alle scripts/-Module, die von der Testsuite aus erreichbar sind —
        transitiv, denn ein Modul importiert das nächste."""
        seen, todo = set(), set()
        for t in TESTS.glob("test_*.py"):
            todo |= toplevel_imports(t) & self.local
        while todo:
            name = todo.pop()
            if name in seen:
                continue
            seen.add(name)
            todo |= toplevel_imports(SCRIPTS / f"{name}.py") & self.local - seen
        return seen

    def test_no_test_reaches_a_dependency_ci_does_not_install(self):
        offenders = []
        for name in sorted(self._reachable_scripts()):
            for mod in sorted(toplevel_imports(SCRIPTS / f"{name}.py")):
                if mod in self.stdlib or mod in self.local or mod in self.allowed:
                    continue
                offenders.append(f"scripts/{name}.py importiert '{mod}'")
        for t in sorted(TESTS.glob("test_*.py")):
            for mod in sorted(toplevel_imports(t)):
                if mod in self.stdlib or mod in self.local or mod in self.allowed:
                    continue
                offenders.append(f"tests/{t.name} importiert '{mod}'")
        self.assertEqual(
            offenders, [],
            "Import auf Modulebene, den der Testworkflow nicht installiert — "
            "in eine Funktion verschieben oder in tests.yml aufnehmen:\n  "
            + "\n  ".join(offenders))

    def test_the_heavy_optional_dependencies_stay_out_of_the_import_path(self):
        """Namentlich, damit die Absicht im Fehlertext steht und nicht nur die
        Regel: diese vier gehören zu Harvest bzw. Codebook-Bau und haben im
        Importpfad der Tests nichts verloren."""
        heavy = {"access_parser", "playwright", "openpyxl", "pandas", "requests"}
        reachable = self._reachable_scripts()
        hit = {m for name in reachable
               for m in toplevel_imports(SCRIPTS / f"{name}.py") if m in heavy}
        self.assertEqual(hit, set(),
                         f"schwere Abhängigkeit im Importpfad der Tests: {sorted(hit)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
