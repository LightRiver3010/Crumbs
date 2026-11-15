import unittest

from frontend.item_carousel import featured_items
from menu_comparison.restaurant import restaurant_items, table_rows


class RestaurantTests(unittest.TestCase):
    def setUp(self):
        self.sources = [dict(id=p, provider=p, restaurant_id="cafe-amherst",
                             expected_heading="Cafe", fulfillment_mode="DELIVERY")
                        for p in ("ubereats", "doordash")]
        self.menus = {p: [dict(source_item_id=p, item_name="Pizza 12 inch", price_cents=price,
                             currency="USD", variant=None)]
                      for p, price in (("ubereats", 1200), ("doordash", 1000))}

    def test_exact_name_comparison_for_any_restaurant(self):
        items = restaurant_items(self.sources, self.menus)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["comparable"])
        self.assertEqual(table_rows(items)[0]["Comparison"], "DoorDash saves $2.00")
        self.assertEqual(len(featured_items(self.sources, self.menus)), 1)

    def test_different_sizes_never_match(self):
        self.menus["doordash"][0]["item_name"] = "Pizza 16 inch"
        items = restaurant_items(self.sources, self.menus)
        self.assertEqual(len(items), 2)
        self.assertFalse(any(i["comparable"] for i in items))
        self.assertEqual(featured_items(self.sources, self.menus), [])

    def test_starting_prices_visible_but_never_compared(self):
        self.menus["doordash"][0]["variant"] = "starting_price; options_unverified"
        items = restaurant_items(self.sources, self.menus)
        self.assertEqual(table_rows(items)[0]["DoorDash"], "$10.00+")
        self.assertEqual(table_rows(items)[0]["Comparison"], "Not comparable")
        self.assertEqual(featured_items(self.sources, self.menus), [])

    def test_duplicate_names_stay_separate(self):
        self.menus["doordash"].append(dict(self.menus["doordash"][0], source_item_id="other"))
        items = restaurant_items(self.sources, self.menus)
        self.assertEqual(len(items), 3)
        self.assertFalse(any(i["comparable"] for i in items))

    def test_missing_prices_currency_and_fulfillment(self):
        for field, value in (("price_cents", None), ("currency", "CAD"), ("fulfillment_mode", "PICKUP")):
            with self.subTest(field=field):
                self.setUp()
                self.menus["doordash"][0][field] = value
                self.assertFalse(restaurant_items(self.sources, self.menus)[0]["comparable"])

    def test_single_platform_and_cross_restaurant_never_enter_slider(self):
        self.sources[1]["restaurant_id"] = "other-amherst"
        self.assertEqual(featured_items(self.sources, self.menus), [])


if __name__ == "__main__":
    unittest.main()
