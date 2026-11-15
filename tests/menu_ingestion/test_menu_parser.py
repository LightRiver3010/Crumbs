"""Synthetic fixtures test parser behavior; these are not live observations."""
import sys
from pathlib import Path
import unittest
import json
from urllib.parse import quote
from menu_ingestion.ingest_menu import parse_menu

STORE = "8be06cab-de88-569c-99b7-9ad79d1cf936"
ITEM = "31fe9d85-a0cb-4ae7-a72d-d0addfbf6288"

def card(price="$15.99", extra=""):
    context = quote(quote(json.dumps({"storeUuid": STORE, "itemUuid": ITEM})))
    return f'<a href="/store/test?mod=quickView&amp;modctx={context}"><span data-testid="rich-text">Roast Beef</span><span data-testid="rich-text">{price}</span><span data-testid="rich-text">100% (5)</span>{extra}</a>'

def page(content):
    return '<h1>Primo too Amherst</h1><h3>Grinders</h3>' + content

class ParserTests(unittest.TestCase):
    def test_money_rating_and_double_encoded_id(self):
        rows, rejects, count = parse_menu(page(card()), STORE)
        self.assertEqual(rows[0]["price_cents"], 1599)
        self.assertEqual(rows[0]["source_item_id"], ITEM)
        self.assertEqual(rows[0]["category"], "Grinders")
        self.assertEqual(rejects, [])
    def test_duplicate_cards_are_not_duplicate_observations(self):
        rows, rejects, count = parse_menu(page(card() + card()), STORE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(count, 2)
    def test_duplicate_in_different_categories_is_not_price_conflict(self):
        rows, rejects, count = parse_menu(page(card() + '<h3>Popular</h3>' + card()), STORE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rejects, [])

    def test_rendered_utf8_heading_and_item_names(self):
        html = page(card()).replace("Primo too Amherst", "McDonald's®").replace("Roast Beef", "Café")
        rows, rejects, _ = parse_menu(html.encode("utf-8"), STORE, "McDonald's®")
        self.assertEqual(rows[0]["item_name"], "Café")
        self.assertEqual(rejects, [])
    def test_explicit_zero_price_is_retained(self):
        rows, rejects, _ = parse_menu(page(card("$0.00")), STORE)
        self.assertEqual(rows[0]["price_cents"], 0)
        self.assertEqual(rejects, [])

    def test_add_on_priced_item_is_excluded_without_guessing_price(self):
        extra = card("Priced by add-ons").replace(ITEM, "11111111-1111-4111-8111-111111111111")
        rows, rejects, _ = parse_menu(page(card() + extra), STORE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rejects[0]["severity"], "excluded")
        with self.assertRaises(ValueError):
            parse_menu(page(extra), STORE)
    def test_ambiguous_sale_price_not_silently_selected(self):
        with self.assertRaises(ValueError):
            parse_menu(page(card(extra='<span data-testid="rich-text">$12.99</span>')), STORE)
    def test_conflicting_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            parse_menu(page(card() + card("$14.99")), STORE)
    def test_block_page_is_not_empty_success(self):
        with self.assertRaises(ValueError):
            parse_menu("<h1>Access denied</h1>", STORE)
    def test_wrong_store_rejected(self):
        with self.assertRaises(ValueError):
            parse_menu(page(card()), "another-store")

if __name__ == "__main__":
    unittest.main()

