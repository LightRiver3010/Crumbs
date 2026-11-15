"""User-controlled receipt facts and two savings routes."""
from datetime import date
import streamlit as st
from receipt_extraction.insights import facts,project_spending,eligible_meals,dining_savings
from frontend.landing import load_catalog
from menu_comparison.catalog import configured_sources
from menu_comparison.restaurant import restaurants,restaurant_items,restaurant_label,table_rows
from frontend.theme import section_header


def money(cents): return f"${cents/100:,.2f}"

def label(o):
    total=money(o["total_cents"]) if o.get("total_cents") is not None else "Unknown total"
    return f"{o.get('order_date') or 'Unknown date'} | {o.get('restaurant') or 'Unknown restaurant'} | {total} | {o['order_id'][:6]}"


def keep_same(orders):
    st.write("Compare the same meals across today's available platforms.")
    st.caption("Assumes today's menu prices were unchanged when you ordered. Estimates cover matched menu items only, excluding fees, taxes, tips, promotions and paid customizations.")
    sources=configured_sources()
    try:
        menus=load_catalog(sources)
    except Exception:
        st.info("Current comparison prices are temporarily unavailable. Try again later.")
        return
    grouped=restaurants(sources)
    restaurant_keys=list(grouped)
    if not restaurant_keys:
        st.info("No restaurant menus are available for comparison yet.")
        return
    total=matched=complete=0
    total_lines=sum(len(o.get("items",[])) for o in orders)
    for order in orders:
        items=order.get("items",[])
        if not items: continue
        with st.expander(label(order)):
            extracted_restaurant=(order.get("restaurant") or "").casefold()
            default_restaurant=next(
                (key for key in restaurant_keys
                 if restaurant_label(grouped[key]).casefold() in extracted_restaurant
                 or extracted_restaurant in restaurant_label(grouped[key]).casefold()),
                restaurant_keys[0],
            )
            restaurant=st.selectbox(
                "Restaurant for this order",
                restaurant_keys,
                index=restaurant_keys.index(default_restaurant),
                format_func=lambda key: restaurant_label(grouped[key]),
                key="restaurant_"+order["order_id"],
            )
            menu_items=restaurant_items(grouped[restaurant],menus)
            if not menu_items:
                st.info("No saved menu items are available for this restaurant yet.")
                continue
            provider=st.selectbox("Platform used for this order",["Select platform","ubereats","doordash"],key="platform_"+order["order_id"])
            if provider=="Select platform": continue
            matched_order=0
            for i,item in enumerate(items):
                key=f"{order['order_id']}_{i}"
                exact=[menu_item for menu_item in menu_items
                       if menu_item["name"].casefold()==(item.get("name") or "").strip().casefold()]
                choices=exact or menu_items
                def choice_label(menu_item):
                    return menu_item["name"] if menu_item["comparable"] else f"{menu_item['name']} — comparison unavailable"
                choice=st.selectbox(
                    f"Match: {item.get('name') or 'Unnamed item'} (exact size/count)",
                    choices,
                    format_func=choice_label,
                    key="match_"+key,
                )
                quantity=st.number_input("Confirm quantity",min_value=1,max_value=100,value=item.get("quantity") or 1,key="qty_"+key)
                if not choice["comparable"]:
                    st.info("A side-by-side comparison is not available for this meal. Choose another saved item or restaurant.")
                    continue
                st.dataframe(table_rows([choice]),hide_index=True,width="stretch")
                source_price=choice["entries"][provider]["price_cents"]
                comparison_prices=[choice["entries"][platform]["price_cents"] for platform in ("ubereats","doordash")]
                total+=(source_price-min(comparison_prices))*quantity
                matched+=1;matched_order+=1
            if matched_order==len(items): complete+=1
    st.metric("Estimated savings on matched items",money(total))
    st.caption(f"Compared {matched} of {total_lines} visible item lines; {complete} of {len(orders)} orders fully matched. Orders without visible items cannot be compared. This is a menu-price scenario, not a reconstructed checkout total.")


def render(orders,habit):
    section_header("YOUR CRUMB TRAIL", "Your ordering facts", "See the little patterns behind your delivery spending.")
    ids=[o["order_id"] for o in orders]
    by_id={o["order_id"]:o for o in orders}
    multiselect_args={"options": ids, "format_func": lambda k: label(by_id[k]), "key": "insight_orders"}
    if "insight_orders" not in st.session_state:
        multiselect_args["default"] = ids
    selected=st.multiselect("Include these orders (deselect overlapping duplicates or unrelated purchases)",**multiselect_args)
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
        start_args={"key": "period_start"}
        if "period_start" not in st.session_state:
            start_args["value"]=min(dates) if dates else date.today()
        start=st.date_input("Period start (include days without orders)",**start_args)
        end_args={"key": "period_end"}
        if "period_end" not in st.session_state:
            end_args["value"]=max(dates) if dates else date.today()
        end=st.date_input("Period end",**end_args)
        confirmed=st.checkbox("I confirmed the period and included all orders for the ordering category I want to measure",key="period_confirmed")
        usual=None
        if habit!="Yes":
            st.caption("Usually more/less means your normal ordering frequency compared with these screenshots. Enter a frequency so we do not guess the adjustment.")
            usual_args={"min_value": 0.0, "step": 0.5, "key": "usual_weekly"}
            if "usual_weekly" not in st.session_state:
                usual_args["value"]=2.0
            usual=st.number_input("Usual orders per week",**usual_args)
        if confirmed:
            try:
                estimate=project_spending(orders,start,end,habit,usual)
                st.write(f"Estimated weekly spending: **{money(estimate['weekly_cents'])}**")
                st.write(f"Estimated monthly spending: **{money(estimate['monthly_cents'])}**")
                st.caption(f"Observed frequency: {estimate['observed_weekly']:.2f}/week; scenario: {estimate['weekly_orders']:.2f}/week. Monthly estimate uses 365/12 days and the uploaded average order total. Receipt dates and facts are unchanged. No population benchmark comparison is applied.")
            except ValueError as exc: st.info(f"We couldn't calculate that estimate yet: {exc}")
    render_savings(orders)


@st.fragment
def render_savings(orders):
    from frontend.state import preserve_controls
    preserve_controls(savings_only=True)
    section_header("ONE MORE CRUMB", "How would you like to save?", "Choose one small change for your next order.")
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
        slider_args={"min_value": 0, "max_value": len(meals), "key": "meal_swaps"}
        if "meal_swaps" not in st.session_state:
            slider_args["value"]=0
        count=st.slider("How many delivery meals would you replace?",**slider_args)
        result=dining_savings(meals,count,plan=="Yes")
        value=result["savings_cents"]
        st.metric("Estimated savings" if value>=0 else "This would cost more",money(abs(value)))
        st.caption("Replaces the most expensive selected orders first. Uses confirmed delivery totals, including whatever charges are in those totals. This is separate from the keep-the-same scenario; do not add their savings together.")
        if result["orders"]: st.dataframe([{"Replaced order":label(o),"Delivery total":money(o["total_cents"])} for o in result["orders"]],hide_index=True)
