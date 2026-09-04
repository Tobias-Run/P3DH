"""Tests zur Verteilungsansicht des Benchmarks (#48, R3).

Der Benchmark öffnete mit vier Zeilen „Kommuninvest – Grupp" um 370 % CET1. Für
eine schwedische Kommunalfinanzierungsagentur mag das stimmen — aber als erster
Eindruck einer Rangliste liest es sich als „die Daten sind kaputt". Das Problem
ist die Darstellungsform: eine Rangliste sagt „Bester" und hat keine Stelle, an
der ein Randwert wie ein Randwert aussieht.

Seit R3 steht über der Liste die Verteilung, und Zeilen außerhalb der
Tukey-Zäune ihrer Peer-Gruppe tragen ein ◇. Kein Wert wird entfernt oder
verändert — genau das war die Randbedingung des Issues.

Geprüft wird hier nicht die Zeichnung (die ist am gerenderten Zustand in
Chromium abgenommen), sondern die drei Aussagen, auf denen sie beruht:

1. Die Zäune treffen tatsächlich die Werte, wegen derer das Issue geschrieben
   wurde — sonst wäre die Markierung eine leere Geste.
2. Sie treffen nicht fast alles — sonst wäre sie Rauschen.
3. Quartile statt Mittelwert war nicht Geschmack: der Mittelwert wird von genau
   den Werten verschoben, die er einordnen soll.
"""

from pathlib import Path
import collections
import json
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "processed" / "zweig_a" / "data"
VIEWER = ROOT / "processed" / "zweig_a" / "viewer_json.html"
PCT_MIN_GROUP = 5      # spiegelt den Viewer
FENCE = 1.5


def quant(sorted_vals, p):
    """Lineare Interpolation — dieselbe Formel wie quart() im Viewer."""
    i = (len(sorted_vals) - 1) * p
    lo, hi = int(i), min(int(i) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def fences(vals):
    s = sorted(vals)
    q1, q3 = quant(s, 0.25), quant(s, 0.75)
    iqr = q3 - q1
    return q1 - FENCE * iqr, q3 + FENCE * iqr


def short_itype(t):
    return {"Large highest EEA": "Large", "Other highest EEA": "Other",
            "Large subsidiaries": "Large sub."}.get(t, t)


class Cet1Population(unittest.TestCase):
    """CET1-Quote je Report aus benchmark.json, geschlüsselt wie im Viewer."""

    @classmethod
    def setUpClass(cls):
        cls.rows = None
        if not (DATA / "benchmark.json").exists() or not (DATA / "index.json").exists():
            return
        bm = json.loads((DATA / "benchmark.json").read_text(encoding="utf-8"))
        idx = json.loads((DATA / "index.json").read_text(encoding="utf-8"))
        meta = idx["meta"]
        names = idx["names"]
        rows = []
        for rep in idx["reports"]:
            cells = bm.get(rep["k"], {}).get("61.00")
            if not cells:
                continue
            m = re.search(r"([A-Z0-9]{20})(?:\.(\w+))?", rep["entityID"])
            lei, scope = m.group(1), (m.group(2) or "")
            v = next((float(c[2]) for c in cells
                      if c[0] == "0050" and c[1] == "0010"), None)
            # Der Viewer verwirft |v| > 10 als fehlgemeldeten Betrag statt Quote.
            if v is None or abs(v) > 10:
                continue
            im = meta.get(lei, {})
            rows.append({
                "key": rep["k"], "v": v * 100,
                "name": (names.get(lei) or {}).get("name", lei),
                "peer": (short_itype(im.get("institution_type", "") or "?"),
                         scope or "?", rep["refPeriod"]),
            })
        cls.rows = rows

    def setUp(self):
        if self.rows is None:
            self.skipTest("benchmark.json / index.json nicht gebaut")

    def _flags(self):
        by_peer = collections.defaultdict(list)
        for r in self.rows:
            by_peer[r["peer"]].append(r["v"])
        fen = {k: fences(v) for k, v in by_peer.items() if len(v) >= PCT_MIN_GROUP}
        out = set()
        for r in self.rows:
            f = fen.get(r["peer"])
            if f and (r["v"] < f[0] or r["v"] > f[1]):
                out.add(r["key"])
        return out

    def test_the_rows_that_motivated_the_issue_are_flagged(self):
        """Die vier Kommuninvest-Zeilen führen die Rangliste an. Wenn der Zaun
        sie nicht erwischt, markiert die Ansicht das Problem nicht, das sie
        lösen soll."""
        flagged = self._flags()
        head = [r for r in self.rows if r["v"] > 300]
        self.assertTrue(head, "keine Reports über 300 % CET1 im Bestand")
        unflagged = [(r["name"], round(r["v"], 1)) for r in head
                     if r["key"] not in flagged]
        self.assertEqual(unflagged, [],
                         f"Werte über 300 % ohne Randwert-Markierung: {unflagged}")

    def test_the_marker_stays_the_exception(self):
        """Ein Marker an jeder zweiten Zeile ordnet nichts mehr ein."""
        share = len(self._flags()) / len(self.rows)
        self.assertLess(share, 0.15,
                        f"{share:.0%} der Zeilen markiert — das ist keine Ausnahme mehr")
        self.assertGreater(share, 0.0, "kein einziger Randwert — Markierung wirkungslos")

    def test_quartiles_are_robust_where_the_mean_is_not(self):
        """Warum Tukey und nicht Mittelwert ± Standardabweichung: die Extremwerte
        verschieben den Mittelwert, den sie einordnen sollen. Der Median hält
        stand — deshalb steht er in der Karte und nicht der Mittelwert."""
        v = sorted(r["v"] for r in self.rows)
        trimmed = [x for x in v if x <= quant(v, 0.99)]
        mean = lambda a: sum(a) / len(a)  # noqa: E731
        d_mean = abs(mean(v) - mean(trimmed)) / mean(trimmed)
        d_med = abs(quant(v, 0.5) - quant(sorted(trimmed), 0.5)) / quant(v, 0.5)
        self.assertGreater(d_mean, 10 * max(d_med, 1e-9),
                           f"Mittelwert {d_mean:.3%} vs Median {d_med:.3%} — "
                           "die Begründung für Quartile trägt hier nicht")


class ViewerContractTest(unittest.TestCase):
    """Zwei Eigenschaften, die man der Zeichnung nicht ansieht."""

    def setUp(self):
        self.src = VIEWER.read_text(encoding="utf-8")

    def test_the_row_marker_is_peer_relative(self):
        """Über alle Größenklassen zu zäunen hieße, eine Exportkreditagentur an
        einer Dorfsparkasse zu messen — dieselbe Überlegung wie bei den
        Perzentilbändern, und dort steht sie schon im Code."""
        m = re.search(r"function fenceOutliers\(rows,colId\)\{(.*?)\n\}", self.src, re.S)
        self.assertIsNotNone(m, "fenceOutliers nicht gefunden")
        self.assertIn("peerKeyOf(r)", m.group(1),
                      "Zäune ohne Peer-Gruppe — der Marker wäre eine Aussage über die Größe")
        self.assertIn("PCT_MIN_GROUP", m.group(1),
                      "kein Mindestgruppengröße — ein Zaun aus 2 Werten ist Rauschen")

    def test_nothing_is_removed_from_the_ranking(self):
        """#48: „Kein Wert wird entfernt oder verändert. Die Markierung ist
        additiv, die Zeile bleibt sortierbar an ihrer Position." Die Zeilenmenge
        der Tabelle darf deshalb nur vom ausdrücklichen Einklapp-Schalter
        abhängen, nicht von den Zäunen."""
        m = re.search(r"const rows=BM_HIDEFLAG\?(.*?);", self.src)
        self.assertIsNotNone(m, "Zeilenauswahl der Rangliste nicht gefunden")
        self.assertNotIn("fence", m.group(1).lower(),
                         "die Zäune filtern die Rangliste — sie dürfen nur markieren")


if __name__ == "__main__":
    unittest.main(verbosity=2)
