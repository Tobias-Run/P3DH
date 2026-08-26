"""Tests für die DSR-Dekodierung in scripts/build_entity_meta.py.

Der Knackpunkt ist `decode_pages`: `harvest_catalog_query.py` legt die
Query-Antworten **seitenweise** ab, und die DSR-Kodierung „Wert wie vorige
Zeile" (R-Bitmaske) ist pro Antwort zustandsbehaftet. Würden Seiten naiv
zusammengeworfen, übernähme die erste Zeile einer Folgeseite Werte aus der
letzten Zeile der Vorseite — still falsche Institutsmetadaten.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_entity_meta as m  # noqa: E402

SCHEMA = [{"N": "G0"}, {"N": "G1"}]


def page(rows, dicts=None):
    """Baut eine minimale Query-Antwort im DSR-Format."""
    ds = {"PH": [{"DM0": rows}]}
    if dicts:
        ds["ValueDicts"] = dicts
    return {"results": [{"result": {"data": {"dsr": {"DS": [ds]}}}}]}


class DecodePagesTest(unittest.TestCase):
    def test_single_object_still_accepted(self):
        p = page([{"S": SCHEMA, "C": ["a", "b"]}])
        schema, rows = m.decode_pages(p)
        self.assertEqual([s["N"] for s in schema], ["G0", "G1"])
        self.assertEqual(rows, [["a", "b"]])

    def test_pages_are_concatenated(self):
        p1 = page([{"S": SCHEMA, "C": ["a", "b"]}])
        p2 = page([{"S": SCHEMA, "C": ["c", "d"]}])
        _, rows = m.decode_pages([p1, p2])
        self.assertEqual(rows, [["a", "b"], ["c", "d"]])

    def test_repeat_bitmask_does_not_leak_across_pages(self):
        # Seite 2 beginnt mit R=1 ("wie vorige Zeile") — das muss sich auf die
        # erste Zeile DIESER Seite beziehen, nicht auf Seite 1.
        p1 = page([{"S": SCHEMA, "C": ["seite1", "x"]}])
        p2 = page([{"S": SCHEMA, "C": ["seite2", "y"]},
                   {"S": SCHEMA, "C": ["z"], "R": 1}])
        _, rows = m.decode_pages([p1, p2])
        self.assertEqual(rows[2][0], "seite2",
                         "R-Bitmaske darf nicht über Seitengrenzen hinweg wirken")

    def test_null_bitmask(self):
        p = page([{"S": SCHEMA, "C": ["a"], "Ø": 2}])
        _, rows = m.decode_pages(p)
        self.assertEqual(rows, [["a", None]])

    def test_value_dict_decoding(self):
        p = page([{"S": [{"N": "G0", "DN": "D0"}, {"N": "G1"}], "C": [1, "x"]}],
                 dicts={"D0": ["null", "DekaBank"]})
        _, rows = m.decode_pages(p)
        self.assertEqual(rows[0][0], "DekaBank")

    def test_undecodable_page_skipped(self):
        good = page([{"S": SCHEMA, "C": ["a", "b"]}])
        empty = {"results": [{"result": {"data": {"dsr": {"DS": [{}]}}}}]}
        _, rows = m.decode_pages([good, empty])
        self.assertEqual(rows, [["a", "b"]])

    def test_nothing_decodable_raises(self):
        empty = {"results": [{"result": {"data": {"dsr": {"DS": [{}]}}}}]}
        with self.assertRaises(ValueError):
            m.decode_pages([empty])


if __name__ == "__main__":
    unittest.main(verbosity=2)
