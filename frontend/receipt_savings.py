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


def _provider_key(value):
    normalized=(value or "").casefold().replace(" ","")
    if "uber" in normalized:
        return "ubereats"
    if "door" in normalized:
        return "doordash"
    return None


def _restaurant_key(value, grouped):
    normalized=(value or "").casefold().strip()
    if not normalized:
        return None
    for key, sources in grouped.items():
        candidates={restaurant_label(sources).casefold()}
        candidates.update(source.get("expected_heading","").casefold() for source in sources)
        if any(normalized in candidate or candidate in normalized for candidate in candidates if candidate):
            return key
    return None


def optimal_savings(orders, sources, menus):
    """Estimate savings using current prices without guessing ambiguous matches."""
    grouped=restaurants(sources)
    savings=0
    comparable_lines=0
    for order in orders:
        restaurant=_restaurant_key(order.get("restaurant"),grouped)
        provider=_provider_key(order.get("provider"))
        if restaurant is None:
            continue
        menu_items=restaurant_items(grouped[restaurant],menus)
        for item in order.get("items",[]):
            name=(item.get("name") or "").strip().casefold()
            matches=[menu_item for menu_item in menu_items
                     if menu_item["name"].casefold()==name and menu_item["comparable"]]
            if len(matches)!=1:
                continue
            menu_item=matches[0]
            prices=[menu_item["entries"][platform]["price_cents"] for platform in ("ubereats","doordash")]
            selected_provider=provider
            if selected_provider is None:
                receipt_price=item.get("price_cents")
                matching_platforms=[platform for platform in ("ubereats","doordash")
                                    if receipt_price == menu_item["entries"][platform]["price_cents"]]
                if len(matching_platforms)==1:
                    selected_provider=matching_platforms[0]
                elif len(matching_platforms)==2:
                    comparable_lines+=1
                    continue
            if selected_provider not in ("ubereats","doordash"):
                continue
            quantity=item.get("quantity") or 1
            savings+=max(0,menu_item["entries"][selected_provider]["price_cents"]-min(prices))*quantity
            comparable_lines+=1
    return {"savings_cents": savings, "comparable_lines": comparable_lines}


def render_optimal_savings(orders):
    sources=configured_sources()
    try:
        menus=load_catalog(sources)
    except Exception:
        st.info("We couldn't calculate an optimal-order total right now. Your receipt data is still available below.")
        return
    result=optimal_savings(orders,sources,menus)
    st.subheader("Your optimal-order opportunity")
    if not result["comparable_lines"]:
        st.info("There aren't enough unambiguous restaurant, item, and platform matches to calculate a total yet.")
        return
    st.metric("Could have saved with today's prices",money(result["savings_cents"]))
    st.caption(f"Based on {result['comparable_lines']} comparable receipt line{'s' if result['comparable_lines'] != 1 else ''}; fees, taxes, tips, promotions and historic price changes are excluded.")
    if result["savings_cents"]==0:
        st.success("Congratulations — your comparable orders were already at the best available menu price.")


def keep_same(orders):
    st.write("Pick an item and see how you could save.")
    st.caption("Choose a food item from your receipts, then select its restaurant to compare today's saved Uber Eats and DoorDash menu prices.")
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
    item_counts={}
    item_restaurants={}
    for order in orders:
        for item in order.get("items",[]):
            name=(item.get("name") or "").strip()
            if not name:
                continue
            item_key=name.casefold()
            item_counts[item_key]=item_counts.get(item_key,0)+1
            item_restaurants.setdefault(item_key,{})
            restaurant_name=(order.get("restaurant") or "").casefold()
            item_restaurants[item_key][restaurant_name]=item_restaurants[item_key].get(restaurant_name,0)+1
    if not item_counts:
        st.info("No food items were visible in the confirmed receipts.")
        return
    item_keys=sorted(item_counts,key=lambda key:(-item_counts[key],key))
    if st.session_state.get("same_food_item") not in item_keys:
        st.session_state["same_food_item"]=item_keys[0]
    selected_item=st.selectbox(
        "Food item",
        item_keys,
        format_func=lambda key: next(
            (item.get("name") for order in orders for item in order.get("items",[])
             if (item.get("name") or "").strip().casefold()==key),
            key,
        ) + f" ({item_counts[key]} receipt line{'s' if item_counts[key] != 1 else ''})",
        key="same_food_item",
    )
    extracted_names=item_restaurants.get(selected_item,{})
    default_restaurant=restaurant_keys[0]
    for key in restaurant_keys:
        label_text=restaurant_label(grouped[key]).casefold()
        if any(name and (name in label_text or label_text in name) for name in extracted_names):
            default_restaurant=key
            break
    if st.session_state.get("same_restaurant") not in restaurant_keys:
        st.session_state["same_restaurant"]=default_restaurant
    restaurant=st.selectbox(
        "Restaurant",
        restaurant_keys,
        format_func=lambda key: restaurant_label(grouped[key]),
        key="same_restaurant",
    )
    menu_items=restaurant_items(grouped[restaurant],menus)
    exact=[menu_item for menu_item in menu_items if menu_item["name"].casefold()==selected_item]
    if not exact:
        st.info("This item does not have an exact saved menu match for the selected restaurant yet.")
        return
    choice=exact[0]
    if not choice["comparable"]:
        st.info("A side-by-side comparison is not available for this item at the selected restaurant.")
        st.dataframe(table_rows([choice]),hide_index=True,width="stretch")
        return
    st.dataframe(table_rows([choice]),hide_index=True,width="stretch")
    prices=[choice["entries"][platform]["price_cents"] for platform in ("ubereats","doordash")]
    if prices[0]==prices[1]:
        st.info("They're the same price. Recommendation: choose the platform where you have rewards or a subscription, or check back later.")
        return
    provider=st.selectbox("Platform used for this order",["Select platform","ubereats","doordash"],key="same_provider")
    if provider!="Select platform":
        quantity_args={"min_value": 1, "max_value": 100, "key": "same_quantity"}
        if "same_quantity" not in st.session_state:
            quantity_args["value"]=1
        quantity=st.number_input("Quantity ordered",**quantity_args)
        savings=(choice["entries"][provider]["price_cents"]-min(prices))*quantity
        st.metric("Potential savings",money(savings) if savings >= 0 else "No savings")


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
    render_optimal_savings(orders)
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
