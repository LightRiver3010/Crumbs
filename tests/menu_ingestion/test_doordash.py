import json
from pathlib import Path
import sys
import unittest
from menu_ingestion.extract_doordash import parse_menu, store_id_from_url
from menu_ingestion.ingest_menu import manifest_store_id

def item(id="123", price="$$1.25", amount=125):
    return {"__typename":"MenuPageItem","id":id,"name":"Test Taco","storeId":"1199296",
            "displayPrice":price,"quickAddContext":{"price":{"currency":"USD","decimalPlaces":2,"unitAmount":amount}}}

def html(records,store="1199296"):
    payload="1:"+json.dumps(records,separators=(",",":"))
    return '<h1>Taco Bell</h1><link rel="canonical" href="https://www.doordash.com/store/taco-bell-'+store+'/"><script>self.__next_f.push('+json.dumps([1,payload])+')</script>'

class DoorDashTests(unittest.TestCase):
    def test_numeric_id_and_exact_price(self):
        rows,errors,_=parse_menu(html([item()]),"1199296","Taco Bell")
        self.assertEqual(rows[0]["source_item_id"],"123")
        self.assertEqual(rows[0]["price_cents"],125)
        self.assertEqual(errors,[])
    def test_explicit_us_currency(self):
        rows,errors,_=parse_menu(html([item(price="US$1.25")]),"1199296")
        self.assertEqual(rows[0]["price_cents"],125)
        self.assertEqual(errors,[])
    def test_starting_price_not_exact(self):
        rows,_,_=parse_menu(html([item(price="$$1.25+",amount=0)]),"1199296")
        self.assertEqual(rows[0]["price_type"],"starting_at")
        self.assertIsNotNone(rows[0]["variant"])
    def test_blank_price_excluded_not_zero(self):
        rows,errors,_=parse_menu(html([item(),item(id="124",price="")]),"1199296")
        self.assertEqual(len(rows),1)
        self.assertEqual(errors[0]["severity"],"excluded")
    def test_wrong_store(self):
        with self.assertRaises(ValueError): parse_menu(html([item()]),"1751802")
    def test_wrong_item_store(self):
        bad=item();bad["storeId"]="999"
        with self.assertRaises(ValueError): parse_menu(html([bad]),"1199296")
    def test_conflicting_duplicate(self):
        with self.assertRaises(ValueError):
            parse_menu(html([item(),item(price="$$2.00",amount=200)]),"1199296")
    def test_duplicate_categories_deduplicate(self):
        rows,errors,count=parse_menu(html([item(),item()]),"1199296")
        self.assertEqual(len(rows),1)
        self.assertEqual(count,2)
    def test_money_mismatch(self):
        with self.assertRaises(ValueError): parse_menu(html([item(amount=999)]),"1199296")
    def test_store_not_menu_id(self):
        self.assertEqual(store_id_from_url("https://www.doordash.com/store/taco-bell-northampton-1199296/1751802/?pickup=false"),"1199296")
    def test_old_manifest_compatibility(self):
        self.assertEqual(manifest_store_id({"store_uuid":"legacy"}),"legacy")
        self.assertEqual(manifest_store_id({"store_id":"1199296"}),"1199296")

if __name__=="__main__":
    unittest.main()

