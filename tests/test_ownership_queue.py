"""Research priority must skip reviewed/conflicting/blocked values, not guess them."""
from pathlib import Path
import sys
import unittest
import duckdb

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
from build_ownership_research_queue import priority

class OwnershipQueueTest(unittest.TestCase):
    def setUp(self):
        self.con=duckdb.connect()
        self.con.execute('''create table p(entityID varchar,lei varchar,scope varchar,
          refPeriod varchar,bank_name varchar,fact_value_eur double,fact_value_raw varchar,
          open_axis_dims varchar,unit_ambiguous boolean,template_id varchar,cell_row varchar,
          cell_col varchar)''')

    def tearDown(self):self.con.close()

    def add(self,lei,value,date='2025-12-31',scope='CON',raw=None,dims='',amb=False):
        self.con.execute('insert into p values (?,?,?,?,?,?,?,?,?,?,?,?)',
          [f'rs:{lei}.{scope}',lei,scope,date,lei,value,str(value) if raw is None else raw,
           dims,amb,'61.00','0040','0010'])

    def test_latest_valid_then_consolidated_and_trea_order(self):
        self.add('a',10);self.add('a',30,scope='IND')
        self.add('b',20,date='2025-06-30');self.add('b',40)
        rows=priority(self.con,set(),set())
        self.assertEqual([(r['lei'],r['trea_eur']) for r in rows],[('b',40),('a',10)])
        self.assertEqual([r['rank'] for r in rows],[1,2])

    def test_conflicting_dimensions_known_ownership_and_currency_review_excluded(self):
        self.add('known',999);self.add('conflict',50);self.add('conflict',60)
        self.add('dims',40,dims='x');self.add('dims',40,dims='y')
        self.add('blocked',30);self.add('ambiguous',20,amb=True);self.add('zero',0)
        self.add('valid',10)
        rows=priority(self.con,{'known'},{('rs:blocked.CON','2025-12-31')})
        self.assertEqual([r['lei'] for r in rows],['valid'])

    def test_older_valid_report_fallback_is_explicit_in_priority_date(self):
        self.add('a',20,date='2025-06-30');self.add('a',40)
        rows=priority(self.con,set(),{('rs:a.CON','2025-12-31')})
        self.assertEqual(rows[0]['date'],'2025-06-30')

if __name__=='__main__':unittest.main()
