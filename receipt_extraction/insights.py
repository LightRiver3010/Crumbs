"""Receipt facts and explicit savings scenarios; no population benchmarks."""
from collections import Counter
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def facts(orders):
    restaurants=Counter()
    meals=Counter()
    days=Counter()
    for order in orders:
        if order.get("restaurant"):
            restaurants[order["restaurant"].strip()]+=1
        # Count orders containing a meal, not the number of portions bought.
        meals.update({i["name"].strip().casefold() for i in order.get("items",[]) if i.get("name")})
        if order.get("order_date"):
            value=order["order_date"]
            if isinstance(value,str): value=date.fromisoformat(value)
            days[value.strftime("%A")]+=1
    return {"restaurants":restaurants.most_common(),"meals":meals.most_common(),"days":days.most_common()}


def project_spending(orders,start,end,habit,usual_weekly=None):
    if end<start: raise ValueError("End date must follow start date.")
    if not orders: raise ValueError("Select orders first.")
    for o in orders:
        if o.get("currency")!="USD" or o.get("total_cents") is None:
            raise ValueError("Every included order needs a confirmed USD total for spending projections.")
        if o.get("order_date"):
            day=date.fromisoformat(o["order_date"]) if isinstance(o["order_date"],str) else o["order_date"]
            if not start<=day<=end: raise ValueError("The selected period must include every dated order.")
    duration=(end-start).days+1
    observed=Decimal(len(orders))*7/Decimal(duration)
    weekly=observed
    if habit!="Yes":
        if usual_weekly is None: raise ValueError("Enter your usual number of orders per week.")
        weekly=Decimal(str(usual_weekly))
        if weekly<0: raise ValueError("Frequency cannot be negative.")
        if habit=="Usually more" and weekly<=observed: raise ValueError("Usually more must exceed the observed weekly frequency.")
        if habit=="Usually less" and weekly>=observed: raise ValueError("Usually less must be below the observed weekly frequency.")
    average=Decimal(sum(o["total_cents"] for o in orders))/len(orders)
    return {"observed_weekly":float(observed),"weekly_orders":float(weekly),
            "weekly_cents":int((average*weekly).quantize(Decimal(1),rounding=ROUND_HALF_UP)),
            "monthly_cents":int((average*weekly*Decimal(365)/12/7).quantize(Decimal(1),rounding=ROUND_HALF_UP))}


def eligible_meals(orders):
    return sorted([o for o in orders if o.get("currency")=="USD" and o.get("total_cents") is not None and o["total_cents"]>1000],key=lambda o:(-o["total_cents"],o["order_id"]))


def dining_savings(orders,count,has_plan):
    eligible=eligible_meals(orders)
    if not 0<=count<=len(eligible): raise ValueError("Invalid replacement count.")
    selected=eligible[:count]
    replacement=count*(0 if has_plan else 1900)
    return {"orders":selected,"replacement_cents":replacement,
            "savings_cents":sum(o["total_cents"] for o in selected)-replacement}
