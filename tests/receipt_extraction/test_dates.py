import unittest
from datetime import date
from receipt_extraction.schemas import Extraction,Order
from receipt_extraction.dates import resolve_missing_years

class DateTests(unittest.TestCase):
    def test_abbreviated_dates(self):
        original=Extraction(orders=[Order(order_date_text="Sep 19"),Order(order_date_text="Oct 9")])
        result=resolve_missing_years(original,2025)
        self.assertEqual([o.order_date for o in result.orders],[date(2025,9,19),date(2025,10,9)])
        self.assertIsNone(original.orders[0].order_date)
        self.assertEqual(result.orders[0].order_date_text,"Sep 19")
    def test_explicit_date_preserved(self):
        e=Extraction(orders=[Order(order_date=date(2024,9,19),order_date_text="Sep 19, 2024")])
        self.assertEqual(resolve_missing_years(e,2026).orders[0].order_date,date(2024,9,19))
    def test_ambiguous_text_not_guessed(self):
        e=Extraction(orders=[Order(order_date_text=t) for t in ("Yesterday","09/10","Sep 19, 2024",None)])
        self.assertTrue(all(o.order_date is None for o in resolve_missing_years(e,2026).orders))
    def test_leap_year(self):
        e=Extraction(orders=[Order(order_date_text="Feb 29")])
        with self.assertRaises(ValueError): resolve_missing_years(e,2025)
        self.assertEqual(resolve_missing_years(e,2024).orders[0].order_date,date(2024,2,29))
    def test_old_payload_compatible(self):
        self.assertIsNone(Order.model_validate({"restaurant":"Cafe"}).order_date_text)

if __name__=="__main__": unittest.main()
