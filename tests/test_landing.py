import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest
from frontend.landing import load_catalog
from frontend.item_carousel import carousel_html, featured_items
import json
from menu_comparison.catalog import configured_sources, get_catalog
from shared.paths import ROOT


class LandingTests(unittest.TestCase):
    def tearDown(self):
        load_catalog.clear()

    def test_catalog_keeps_sources_separate_and_missing_sources(self):
        sources = configured_sources()
        rows = [{"source_id": source["id"], "item_name": source["id"]}
                for source in sources[:2]]
        client = Mock()
        client.query.return_value.result.return_value = rows
        with patch("menu_comparison.catalog.get_client", return_value=client):
            menus = get_catalog(sources)
        self.assertEqual(set(menus), {s["id"] for s in sources})
        self.assertEqual(menus[sources[0]["id"]][0]["item_name"], sources[0]["id"])
        self.assertEqual(menus[sources[-1]["id"]], [])
        client.query.assert_called_once()

    def test_landing_browsing_refresh_and_empty_snapshot(self):
        sources = configured_sources()
        menus = {sources[0]["id"]: [{"item_name": "Pizza", "source_item_id": "pizza", "price_cents": 1200, "currency": "USD",
                  "observed_at": datetime(2026, 11, 15, tzinfo=timezone.utc),
                  "snapshot_status": "success_partial_coverage"}]}
        load_catalog.clear()
        with patch("frontend.landing.get_catalog", return_value=menus) as query:
            app = AppTest.from_file(str(ROOT / "frontend/app.py")).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(len(app.selectbox[0].options), len({s['restaurant_id'] for s in sources}))
            self.assertEqual(app.dataframe[0].value.iloc[0]["Uber Eats"], "$12.00")
            self.assertEqual(app.dataframe[0].value.iloc[0]["DoorDash"], "Unavailable")
            self.assertTrue(any("Partial coverage" in message.value for message in app.caption))
            app.text_input[0].set_value("missing").run()
            self.assertFalse(app.dataframe)
            app.selectbox[0].select(sources[-1]["restaurant_id"]).run()
            self.assertTrue(any("no successful" in message.value for message in app.info))
            self.assertEqual(query.call_count, 1)
            next(b for b in app.button if b.label == "Refresh saved menus").click().run()
            self.assertEqual(query.call_count, 2)
            self.assertFalse(app.exception)

    def test_error_is_actionable_and_does_not_expose_credentials(self):
        load_catalog.clear()
        with patch("frontend.landing.get_catalog", side_effect=RuntimeError("secret")):
            app = AppTest.from_file(str(ROOT / "frontend/app.py")).run(timeout=30)
        self.assertFalse(app.exception)
        self.assertIn("temporarily unavailable", app.info[0].value)
        self.assertNotIn("secret", app.info[0].value)

    def test_item_comparison_colors_and_unverified_items(self):
        sources = configured_sources()
        match = json.loads((ROOT / "config/item_matches.json").read_text())["items"][0]
        menus = {}
        for source in sources[:2]:
            target = match["sources"][source["provider"]]
            menus[source["id"]] = [{"source_item_id": target["item_id"],
                "item_name": target["expected_name"], "currency": "USD", "variant": None,
                "price_cents": 1560 if source["provider"] == "ubereats" else 1480}]
        slides = featured_items(sources, menus)
        self.assertEqual(len(slides), 1)
        html = carousel_html(slides)
        self.assertIn('+$0.80 vs other app', html)
        self.assertIn('−$0.80 vs other app', html)
        self.assertIn('price-row higher', html)
        self.assertIn('price-row lower', html)
        menus[sources[0]["id"]][0]["variant"] = "options_unverified"
        self.assertEqual(featured_items(sources, menus), [])

    def test_cards_escape_content_and_have_navigation(self):
        html = carousel_html([{"name": "<script>bad</script>", "restaurant": "Cafe",
            "emoji": "🍕", "prices": [{"label": "DoorDash", "price_cents": 1000}], "note": ""}])
        self.assertNotIn("<script>bad</script>", html)
        self.assertIn("scroll-snap-type:x mandatory", html)
        self.assertIn('aria-label="Next item"', html)
        self.assertIn('aria-label="Show item 1"', html)

    def test_upload_shortcut(self):
        with patch("frontend.landing.get_catalog", return_value={}):
            app = AppTest.from_file(str(ROOT / "frontend/app.py")).run(timeout=30)
            next(b for b in app.button if b.label == "Upload a receipt").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["active_tab"], "Receipt insights")


if __name__ == "__main__":
    unittest.main()
