import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from menu_ingestion import ingest_menu as pipeline
from tests.menu_ingestion.test_menu_parser import card, page, STORE

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((pipeline.ROOT / "config/sources.json").read_text())
        self.config["sources"] = [self.config["sources"][0]]
    def load(self, config):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sources.json"
            path.write_text(json.dumps(config))
            return pipeline.load_sources(path)
    def test_two_restaurants_supported(self):
        second = copy.deepcopy(self.config["sources"][0])
        second.update(id="second-restaurant", expected_heading="Another Restaurant",
                      store_id="11111111-1111-4111-8111-111111111111")
        self.config["sources"].append(second)
        sources = self.load(self.config)
        self.assertEqual(len(sources), 2)
        html = page(card()).replace("Primo too Amherst", "Another Restaurant").replace(
            STORE, second["store_id"])
        rows, rejects, _ = pipeline.parse_menu(html, second["store_id"], "Another Restaurant")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rejects, [])
    def test_wrong_heading_rejected(self):
        with self.assertRaises(ValueError):
            pipeline.parse_menu(page(card()), STORE, "Another Restaurant")
    def test_duplicate_source_ids_rejected(self):
        self.config["sources"] *= 2
        with self.assertRaises(ValueError):
            self.load(self.config)
    def test_unsupported_provider_rejected_before_fetch(self):
        self.config["sources"][0]["provider"] = "unknown"
        with self.assertRaises(ValueError):
            self.load(self.config)
    def test_disabled_source_skipped(self):
        self.config["sources"].append({"id":"disabled","enabled":False})
        self.assertEqual(len(self.load(self.config)),1)
    def test_url_fulfillment_must_match(self):
        self.config["sources"][0]["fulfillment_mode"] = "PICKUP"
        with self.assertRaises(ValueError):
            self.load(self.config)
    def test_batch_failure_does_not_skip_next_source(self):
        args=argparse.Namespace(batch_id="scheduled-run",replay=None,resume_local=None)
        calls=[]
        def runner(source,args,run_id):
            calls.append((source["id"],run_id))
            if source["id"] == "first":
                raise RuntimeError("simulated failure")
            return 0
        with tempfile.TemporaryDirectory() as folder, patch.object(pipeline,"ROOT",Path(folder)):
            code=pipeline.run_batch([{"id":"first"},{"id":"second"}],args,runner)
            self.assertEqual(code,1)
            self.assertEqual([x[0] for x in calls],["first","second"])
            self.assertNotEqual(calls[0][1],calls[1][1])
    def test_retry_identity_stable_and_new_schedule_distinct(self):
        self.assertEqual(pipeline.source_run_id("one","schedule-1"),pipeline.source_run_id("one","schedule-1"))
        self.assertNotEqual(pipeline.source_run_id("one","schedule-1"),pipeline.source_run_id("one","schedule-2"))
        self.assertNotEqual(pipeline.source_run_id("one","schedule-1"),pipeline.source_run_id("two","schedule-1"))

if __name__ == "__main__":
    unittest.main()

