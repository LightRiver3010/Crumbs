import unittest
from datetime import date
from receipt_extraction.insights import facts,project_spending,dining_savings,eligible_meals

class InsightsTests(unittest.TestCase):
    def setUp(self):
        self.orders=[{"order_id":str(i),"restaurant":"Cafe","currency":"USD","total_cents":cost,"order_date":date(2026,11,10),"items":[{"name":"Pizza"},{"name":"Pizza"}]} for i,cost in enumerate((1000,1500,2500))]
    def test_meal_counts_orders_not_lines(self):
        self.assertEqual(facts(self.orders)["meals"],[("pizza",3)])
    def test_strict_meal_threshold(self):
        self.assertEqual(len(eligible_meals(self.orders)),2)
    def test_plan_and_expensive_first(self):
        result=dining_savings(self.orders,1,True)
        self.assertEqual(result["savings_cents"],2500)
        self.assertEqual(result["orders"][0]["order_id"],"2")
    def test_paid_meal_can_cost_more(self):
        self.assertEqual(dining_savings([self.orders[1]],1,False)["savings_cents"],-400)
    def test_zero_swaps(self):
        self.assertEqual(dining_savings(self.orders,0,True)["savings_cents"],0)
    def test_full_week(self):
        result=project_spending(self.orders,date(2026,11,8),date(2026,11,14),"Yes")
        self.assertEqual(result["weekly_cents"],5000)
    def test_adjustments_need_correct_direction(self):
        with self.assertRaises(ValueError): project_spending(self.orders,date(2026,11,8),date(2026,11,14),"Usually more",2)
        result=project_spending(self.orders,date(2026,11,8),date(2026,11,14),"Usually less",1.5)
        self.assertEqual(result["weekly_cents"],2500)
    def test_unknown_currency_blocks_projection(self):
        self.orders[0]["currency"]=None
        with self.assertRaises(ValueError): project_spending(self.orders,date(2026,11,8),date(2026,11,14),"Yes")
    def test_dates_outside_range_rejected(self):
        with self.assertRaises(ValueError): project_spending(self.orders,date(2026,11,12),date(2026,11,14),"Yes")

if __name__=="__main__": unittest.main()
