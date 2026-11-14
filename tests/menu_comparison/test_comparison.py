import copy
from datetime import datetime,timezone,timedelta
import unittest
from menu_comparison.compare import comparison_rows,last_scraped,render_table
from menu_ingestion.tools.compare_fetch_modes import compare_items

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.match={"sources":{p:{"item_id":"1","expected_name":"Pizza"} for p in ("ubereats","doordash")}}
        self.menus={p:[{"source_item_id":"1","item_name":"Pizza","price_cents":price,"variant":None,"currency":"USD","observed_at":datetime(2026,11,14,12,tzinfo=timezone.utc)}] for p,price in (("ubereats",1200),("doordash",1000))}
    def test_price_difference(self):
        rows=comparison_rows(self.match,self.menus)
        self.assertEqual(rows[0]["difference"],"+$2.00 (+20%)")
        self.assertEqual(rows[1]["difference"],"Lowest price")
    def test_ties(self):
        self.menus["ubereats"][0]["price_cents"]=1000
        self.assertEqual(comparison_rows(self.match,self.menus)[0]["difference"],"Same price")
    def test_unmatched_or_changed_listing(self):
        for field,value in (("item_name","Different Pizza"),("variant","starting_price; options_unverified"),("currency","CAD")):
            menus=copy.deepcopy(self.menus);menus["ubereats"][0][field]=value
            self.assertEqual(comparison_rows(self.match,menus)[0]["price"],"Unavailable")
            self.assertEqual(comparison_rows(self.match,menus)[1]["difference"],"Not comparable")
    def test_oldest_timestamp(self):
        self.menus["doordash"][0]["observed_at"]+=timedelta(hours=1)
        self.assertEqual(last_scraped(self.menus),self.menus["ubereats"][0]["observed_at"])
        self.menus["doordash"]=[]
        self.assertIsNone(last_scraped(self.menus))
    def test_html_escaped(self):
        html=render_table('<script>alert(1)</script>',comparison_rows(self.match,self.menus))
        self.assertNotIn('<script>',html)
        self.assertIn('@media(max-width:480px)',html)
    def test_exact_fetch_comparison(self):
        before=self.menus["ubereats"]
        after=copy.deepcopy(before)
        self.assertEqual(compare_items(before,after),{"missing_ids":[],"added_ids":[],"changed":[]})
        after[0]["price_cents"]+=1
        self.assertEqual(len(compare_items(before,after)["changed"]),1)

if __name__=="__main__": unittest.main()
