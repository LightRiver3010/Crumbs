"""Saved menus for every enabled restaurant source."""

import streamlit as st
from frontend.item_carousel import featured_items, carousel_html

from frontend.theme import section_header
from menu_comparison.catalog import configured_sources, get_catalog
from menu_comparison.compare import render_table, timestamp_label
from menu_comparison.restaurant import restaurants, restaurant_label, restaurant_items, table_rows

PROVIDERS = {"ubereats": "Uber Eats", "doordash": "DoorDash"}


@st.cache_data(ttl=900, show_spinner=False)
def load_catalog(sources):
    return get_catalog(sources)


def open_receipts():
    st.session_state["active_tab"] = "Receipt insights"

def render():
    section_header("YOUR NEXT BITE", "Explore local menus", "Browse saved delivery menus around Amherst, Hadley and Northampton.")
    sources = configured_sources()
    if not sources:
        st.info("No restaurant sources are enabled yet.")
        return
    if st.button("Refresh saved menus", help="Reload BigQuery snapshots without scraping websites."):
        load_catalog.clear()
    try:
        with st.spinner("Loading saved menus..."):
            menus = load_catalog(sources)
    except Exception:
        st.info("Saved menus are temporarily unavailable. Try refreshing in a moment.")
        return
    slides = featured_items(sources, menus)
    if slides:
        st.iframe(carousel_html(slides), height="content", alt="Featured menu items and price differences")
        st.caption("Green − saves money; red + costs more than the other matched app. Direct delivery prices are not available. Menu prices exclude fees, taxes and tips.")
    else:
        st.info("No comparable saved items are available yet. Browse all restaurant menus below.")
    render_menu_browser(sources, menus)
    section_header("COLLECT YOUR CRUMBS", "Find savings in your favorites",
                   "Upload a receipt screenshot to see where your delivery spending goes.")
    st.button("Upload a receipt", type="primary", width="stretch", on_click=open_receipts)


def render_menu_browser(sources, menus):
    section_header("SAVE A CRUMB", "Compare meals side by side", "Choose a restaurant, category and meal to compare saved delivery prices.")
    grouped = restaurants(sources)
    selected = st.selectbox("Restaurant", list(grouped),
                            format_func=lambda key: restaurant_label(grouped[key]), key="landing_restaurant")
    restaurant_sources = grouped[selected]
    items = restaurant_items(restaurant_sources, menus)
    metric_columns = st.columns(2)
    metric_columns[0].metric("Comparable meals", sum(item["comparable"] for item in items))
    metric_columns[1].metric("Saved menu listings", len(items))
    for source in restaurant_sources:
        rows = menus.get(source["id"], [])
        provider = PROVIDERS.get(source["provider"], source["provider"])
        with st.container(border=True):
            st.link_button("Open " + provider, source["url"])
            timestamps = [r["observed_at"] for r in rows if r.get("observed_at")]
            st.caption(f"{provider}: {len(rows)} saved items" +
                       (" | Last scraped: " + timestamp_label(max(timestamps)) if timestamps else " | No successful saved snapshot yet"))
            if any(r.get("snapshot_status") == "success_partial_coverage" for r in rows):
                st.caption("Partial coverage: some items or options may be missing.")
    if not items:
        st.info("This restaurant has no successful saved snapshot in BigQuery yet.")
        return
    categories = ["All"] + sorted({item["category"] for item in items})
    if st.session_state.get("landing_category") not in categories:
        st.session_state["landing_category"] = "All"
    category = st.selectbox("Category", categories, key="landing_category")
    search = st.text_input("Search meals", key="landing_search").strip().casefold()
    visible = [item for item in items
               if (category == "All" or item["category"] == category)
               and search in item["name"].casefold()]
    visible.sort(key=lambda item: (not item["comparable"], item["name"].casefold()))
    if not visible:
        st.info("No meals are available in this category.")
        return
    labels = {
        id(item): item["name"] if item["comparable"]
        else f"{item['name']} — comparison unavailable"
        for item in visible
    }
    if st.session_state.get("landing_meal") not in visible:
        st.session_state["landing_meal"] = visible[0]
    selected_item = st.selectbox("Meal", visible,
                                 format_func=lambda item: labels[id(item)],
                                 key="landing_meal")
    if not selected_item["comparable"]:
        st.info("A side-by-side comparison is not available for this meal. Choose a meal without the “comparison unavailable” label to compare prices.")
        st.dataframe(table_rows([selected_item]), hide_index=True, width="stretch")
        return
    entries = selected_item["entries"]
    prices = [entries[provider]["price_cents"] for provider in PROVIDERS]
    rows = []
    for provider in PROVIDERS:
        price = entries[provider]["price_cents"]
        rows.append({
            "source": PROVIDERS[provider] + " Menu Price",
            "price_cents": price,
            "price": f"${price / 100:.2f}",
            "difference": "Same price" if prices[0] == prices[1] else
                         "Lowest price" if price == min(prices) else
                         f"+${(price - min(prices)) / 100:.2f}",
        })
    st.html(render_table(selected_item["name"], rows))
    st.caption(selected_item["basis"] + ". Menu prices exclude fees, taxes and tips.")
