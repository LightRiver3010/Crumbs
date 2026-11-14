"""User-controlled receipt facts and two savings routes."""
from datetime import date
import json
import streamlit as st
from receipt_extraction.insights import facts,project_spending,eligible_meals,dining_savings
from shared.paths import ROOT
from frontend.comparison import load_menus
from menu_comparison.compare import comparison_rows,render_table,timestamp_label,last_scraped
from frontend.theme import section_header


def money(cents): return f"${cents/100:,.2f}"

def label(o):
    total=money(o["total_cents"]) if o.get("total_cents") is not None else "Unknown total"
    return f"{o.get('order_date') or 'Unknown date'} | {o.get('restaurant') or 'Unknown restaurant'} | {total} | {o['order_id'][:6]}"


def keep_same(orders):
    st.write("Compare the same meals across today's available platforms.")
    st.caption("Assumes today's menu prices were unchanged when you ordered. Estimates cover matched menu items only, excluding fees, taxes, tips, promotions and paid customizations.")
    try:
        menus=load_menus()
    except Exception:
        st.info("Current comparison prices are unavailable. Try again later.")
        return
    matches=json.loads((ROOT/"config/item_matches.json").read_text())["items"]
    stamp=last_scraped(menus)
    if stamp: st.caption("Menu prices last scraped: "+timestamp_label(stamp)+" (oldest source).")
    st.caption("Currently supports the nine reviewed Primo Too, Amherst items. Confirm the restaurant branch and exact size/count; unsupported items are not counted as zero savings.")
    total=matched=complete=0
    total_lines=sum(len(o.get("items",[])) for o in orders)
    for order in orders:
        items=order.get("items",[])
        if not items: continue
        with st.expander(label(order)):
            correct=st.checkbox("This order is from Primo Too in Amherst",key="branch_"+order["order_id"])
            if not correct: continue
            provider=st.selectbox("Platform used for this order",["Select platform","ubereats","doordash"],key="platform_"+order["order_id"])
            if provider=="Select platform": continue
            matched_order=0
            for i,item in enumerate(items):
                key=f"{order['order_id']}_{i}"
                choice=st.selectbox(f"Match: {item['name']} (exact size/count)",[None]+list(range(len(matches))),format_func=lambda v:"Not matched" if v is None else matches[v]["name"],key="match_"+key)
                if choice is None: continue
                quantity=st.number_input("Confirm quantity",min_value=1,max_value=100,value=item.get("quantity") or 1,key="qty_"+key)
                rows=comparison_rows(matches[choice],menus)
                st.html(render_table(matches[choice]["name"],rows))
                if any(r["price_cents"] is None for r in rows): continue
                source_price=rows[0 if provider=="ubereats" else 1]["price_cents"]
                total+=(source_price-min(r["price_cents"] for r in rows))*quantity
                matched+=1;matched_order+=1
            if matched_order==len(items): complete+=1
    st.metric("Estimated savings on matched items",money(total))
    st.caption(f"Compared {matched} of {total_lines} visible item lines; {complete} of {len(orders)} orders fully matched. Orders without visible items cannot be compared. This is a menu-price scenario, not a reconstructed checkout total.")


def render(orders,habit):
    section_header("YOUR SNAPSHOT", "Your ordering facts", "Use confirmed orders to spot patterns, not to judge your choices.")
    ids=[o["order_id"] for o in orders]
    by_id={o["order_id"]:o for o in orders}
    selected=st.multiselect("Include these orders (deselect overlapping duplicates or unrelated purchases)",ids,default=ids,format_func=lambda k:label(by_id[k]),key="insight_orders")
    orders=[by_id[k] for k in selected]
    if not orders:
        st.info("Select at least one confirmed order.");return
    known=[o for o in orders if o.get("currency")=="USD" and o.get("total_cents") is not None]
    st.metric("Included orders",len(orders))
    st.metric("Known USD spending",money(sum(o["total_cents"] for o in known)))
    if len(known)!=len(orders): st.caption(f"Spending excludes {len(orders)-len(known)} orders with unknown totals or non-USD currency.")
    summary=facts(orders)
    for title,key in (("Most common meals","meals"),("Favorite restaurants","restaurants"),("Most popular days to order","days")):
        st.write("**"+title+"**")
        if summary[key]: st.dataframe([{"Name":name,"Orders":count} for name,count in summary[key][:5]],hide_index=True)
        else: st.caption("Not enough visible information in these screenshots.")
    st.caption("Meals count orders containing that item, not portions. Weekdays use dated orders only. These facts describe your included screenshots, not all your purchases.")
    with st.expander("Estimate weekly and monthly spending"):
        dates=[o["order_date"] for o in orders if o.get("order_date")]
        start=st.date_input("Period start (include days without orders)",value=min(dates) if dates else date.today(),key="period_start")
        end=st.date_input("Period end",value=max(dates) if dates else date.today(),key="period_end")
        confirmed=st.checkbox("I confirmed the period and included all orders for the ordering category I want to measure",key="period_confirmed")
        usual=None
        if habit!="Yes":
            st.caption("Usually more/less means your normal ordering frequency compared with these screenshots. Enter a frequency so we do not guess the adjustment.")
            usual=st.number_input("Usual orders per week",min_value=0.0,value=2.0,step=0.5,key="usual_weekly")
        if confirmed:
            try:
                estimate=project_spending(orders,start,end,habit,usual)
                st.write(f"Estimated weekly spending: **{money(estimate['weekly_cents'])}**")
                st.write(f"Estimated monthly spending: **{money(estimate['monthly_cents'])}**")
                st.caption(f"Observed frequency: {estimate['observed_weekly']:.2f}/week; scenario: {estimate['weekly_orders']:.2f}/week. Monthly estimate uses 365/12 days and the uploaded average order total. Receipt dates and facts are unchanged. No population benchmark comparison is applied.")
            except ValueError as exc: st.warning(str(exc))
    render_savings(orders)


@st.fragment
def render_savings(orders):
    from frontend.state import preserve_controls
    preserve_controls(savings_only=True)
    section_header("NEXT STEP", "How would you like to save?", "Choose the strategy that fits your next order.")
    if st.button("Keep the same",use_container_width=True): st.session_state.savings_route="same"
    if st.button("Make a small change",use_container_width=True): st.session_state.savings_route="change"
    route=st.session_state.get("savings_route")
    if route=="same": keep_same(orders)
    if route=="change":
        st.write("Replace a few delivery meals with dining-hall meals.")
        eligible=eligible_meals(orders)
        if not eligible:
            st.info("Upload receipts of full meals to get more insights.");return
        by_key={o["order_id"]:o for o in eligible}
        chosen=st.multiselect("Confirm which are delivery orders that each replace one person's meal",list(by_key),format_func=lambda k:label(by_key[k]),key="delivery_meals")
        meals=[by_key[k] for k in chosen]
        if not meals:
            st.info("Select confirmed delivery meals above $10 to enable the slider.");return
        plan=st.radio("Do you have a dining-hall meal plan?",["Yes","No"],index=None,key="meal_plan")
        if plan is None: return
        st.caption("Meal plan: $0 additional cost per meal; prepaid plan cost is ignored and available swipes are assumed." if plan=="Yes" else "No meal plan: assumes $19 per dining-hall meal, not a verified current dining-hall price.")
        count=st.slider("How many delivery meals would you replace?",0,len(meals),0,key="meal_swaps")
        result=dining_savings(meals,count,plan=="Yes")
        value=result["savings_cents"]
        st.metric("Estimated savings" if value>=0 else "This would cost more",money(abs(value)))
        st.caption("Replaces the most expensive selected orders first. Uses confirmed delivery totals, including whatever charges are in those totals. This is separate from the keep-the-same scenario; do not add their savings together.")
        if result["orders"]: st.dataframe([{"Replaced order":label(o),"Delivery total":money(o["total_cents"])} for o in result["orders"]],hide_index=True)
