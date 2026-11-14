import copy
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from menu_ingestion import ingest_menu as pipeline
from menu_ingestion.extract_ubereats import parse_menu as uber
from menu_ingestion.extract_doordash import parse_menu as doordash
from tests.menu_ingestion.test_doordash import html, item
from tests.menu_ingestion.test_menu_parser import STORE

class FetchModeTests(unittest.TestCase):
    def test_all_four_flag_combinations(self):
        for tested,matching in itertools.product((False,True),repeat=2):
            with self.subTest(tested=tested,matching=matching):
                mode=pipeline.use_html_only({"html_only_tested":tested,"html_only_matches_js":matching})
                self.assertEqual(mode,tested and matching)
                response=Mock(status_code=200,content=b"fixture",headers={})
                with patch.object(pipeline.requests,"get",return_value=response) as request:
                    _,meta=pipeline.fetch_menu("https://example.test","fake-test-key","ubereats",html_only=mode)
                    params=request.call_args.kwargs["params"]
                    self.assertEqual(params["js_render"],"false" if mode else "true")
                    self.assertEqual("wait_for" in params,not mode)
                    self.assertEqual(meta["fetch_options"]["js_render"],not mode)
                    request.assert_called_once()
    def test_missing_flags_are_safe(self):
        self.assertFalse(pipeline.use_html_only({}))
        self.assertFalse(pipeline.use_html_only({"html_only_tested":True}))
    def test_strings_not_truthy_and_config_rejects_them(self):
        self.assertFalse(pipeline.use_html_only({"html_only_tested":"true","html_only_matches_js":"true"}))
        config=json.loads((pipeline.ROOT/"config/sources.json").read_text())
        config["sources"][0]["html_only_tested"]="true"
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"sources.json";p.write_text(json.dumps(config))
            with self.assertRaises(ValueError):pipeline.load_sources(p)
    def test_proof_not_inherited(self):
        config=json.loads((pipeline.ROOT/"config/sources.json").read_text())
        config["sources"]=[config["sources"][0]]
        for flag in ("html_only_tested","html_only_matches_js"):
            config["defaults"][flag]=True
            config["sources"][0].pop(flag,None)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"sources.json";p.write_text(json.dumps(config))
            self.assertFalse(pipeline.use_html_only(pipeline.load_sources(p)[0]))
    def test_configured_decisions(self):
        sources={s["id"]:s for s in pipeline.load_sources(pipeline.ROOT/"config/sources.json")}
        self.assertTrue(pipeline.use_html_only(sources["primo-too"]))
        self.assertFalse(pipeline.use_html_only(sources["taco-bell"]))
        self.assertFalse(pipeline.use_html_only(sources["popeyes"]))
    def test_no_automatic_paid_retry(self):
        response=Mock(status_code=422,headers={})
        with patch.object(pipeline.requests,"get",return_value=response) as request:
            with self.assertRaises(RuntimeError):
                pipeline.fetch_menu("https://example.test","fake","doordash",html_only=True)
            request.assert_called_once()
    def test_replay_uses_snapshot_mode_not_current_flags(self):
        source={"provider":"ubereats","html_only_tested":True,"html_only_matches_js":True}
        for options,expected in (({},False),({"js_render":True},False),({"js_render":False},True)):
            manifest={"store_id":STORE,"fetch_options":options}
            parser=Mock(return_value=([],[],0))
            with patch.dict(pipeline.PARSERS,{"ubereats":parser}):
                pipeline.extract_snapshot(b"fixture",manifest,source)
                self.assertEqual(parser.call_args.kwargs["html_only"],expected)
    def test_doordash_parser_accepts_both_modes(self):
        self.assertEqual(doordash(html([item()]),"1199296",html_only=True),
                         doordash(html([item()]),"1199296",html_only=False))

def embedded_page(store=STORE,price=1599,display="$15.99"):
    data={"uuid":store,"title":"Primo too Amherst","catalogSectionsMap":{"section":[{"payload":{"standardItemsPayload":{
          "title":"Grinders","catalogItems":[{"uuid":"31fe9d85-a0cb-4ae7-a72d-d0addfbf6288","title":"Roast Beef",
                                            "price":price,"priceTagline":{"text":display}}]}}}]}}
    return '<script id="__REACT_QUERY_STATE__" type="application/json">'+json.dumps({"queries":[{"state":{"data":data}}]})+'</script>'

class UberEmbeddedTests(unittest.TestCase):
    def test_html_mode_extracts_without_visible_cards(self):
        rows,errors,count=uber(embedded_page(),STORE,"Primo too Amherst",html_only=True)
        self.assertEqual(rows[0]["price_cents"],1599);self.assertEqual(errors,[])
    def test_rendered_mode_does_not_silently_switch(self):
        with self.assertRaises(ValueError):uber(embedded_page(),STORE,html_only=False)
    def test_other_store_rejected(self):
        with self.assertRaises(ValueError):uber(embedded_page(),"another-store",html_only=True)
    def test_price_disagreement_rejected(self):
        with self.assertRaises(ValueError):uber(embedded_page(price=1),STORE,html_only=True)
    def test_missing_state_fails(self):
        with self.assertRaises(ValueError):uber("<h1>Primo too Amherst</h1>",STORE,html_only=True)

if __name__=="__main__":
    unittest.main()

