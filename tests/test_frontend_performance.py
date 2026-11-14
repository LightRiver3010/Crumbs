import unittest
from unittest.mock import patch
from datetime import date
from streamlit.testing.v1 import AppTest
from frontend.comparison import load_menus
from shared.paths import ROOT

class PerformanceTests(unittest.TestCase):
    def test_tabs_cache_and_retained_controls(self):
        load_menus.clear()
        with patch("frontend.comparison.get_latest_menus",return_value={}) as menu, patch("frontend.receipts.prepare") as extract:
            app=AppTest.from_file(str(ROOT/"frontend/app.py"))
            app.session_state["active_tab"]="Receipt insights"
            app.session_state["saved_orders"]=[{"order_id":"x","restaurant":"Cafe","currency":"USD","total_cents":1500,"order_date":date(2026,11,10),"items":[]}]
            app.session_state["ordering_habit"]="Yes"
            app.session_state["review_fixture"]="unsaved edit"
            app.run(timeout=30)
            self.assertFalse(app.exception)
            menu.assert_not_called()
            next(b for b in app.button if b.label=="Make a small change").click().run()
            next(m for m in app.multiselect if "Confirm which" in m.label).select("x").run()
            next(r for r in app.radio if "meal plan" in r.label).set_value("Yes").run()
            app.slider[0].set_value(1).run()
            self.assertFalse(app.exception)
            menu.assert_not_called();extract.assert_not_called()
            app.session_state["active_tab"]="Compare prices";app.run()
            self.assertFalse(app.exception)
            self.assertEqual(menu.call_count,1)
            app.run();self.assertEqual(menu.call_count,1)
            next(b for b in app.button if b.label=="Refresh saved prices").click().run()
            self.assertEqual(menu.call_count,2)
            app.session_state["active_tab"]="Receipt insights";app.run()
            self.assertFalse(app.exception)
            self.assertEqual(app.slider[0].value,1)
            self.assertEqual(app.session_state["meal_plan"],"Yes")
            self.assertEqual(app.session_state["review_fixture"],"unsaved edit")
            self.assertEqual(menu.call_count,2)
        load_menus.clear()

if __name__=="__main__": unittest.main()
