"""Mobile-friendly Primo Too price comparison; browsing never scrapes."""
import json
import streamlit as st
from shared.paths import ROOT
from menu_comparison.repository import get_latest_menus
from menu_comparison.compare import comparison_rows, last_scraped, timestamp_label, render_table
from frontend.theme import section_header

@st.cache_data(ttl=900, show_spinner=False)
def load_menus():
    return get_latest_menus()


def render():
    section_header("SAVE A CRUMB", "Compare menu prices", "Find a small price win before you place your next order.")
    st.selectbox("Restaurant",["Primo Too - Amherst"],key="comparison_restaurant")
    matches=json.loads((ROOT/"config/item_matches.json").read_text())["items"]
    category=st.selectbox("Category",["All"]+sorted({m["category"] for m in matches}),key="comparison_category")
    available=[m for m in matches if category=="All" or m["category"]==category]
    selected=st.selectbox("Meal",available,format_func=lambda m:m["name"],key="comparison_meal")
    if st.button("Refresh saved prices", help="Reload BigQuery data; this does not scrape either website.", use_container_width=True, type="primary"):
        load_menus.clear()
    try:
        with st.spinner("Loading saved menu prices..."):
            menus=load_menus()
    except Exception:
        st.error("Saved prices could not be loaded. Check Google Cloud access and try again.")
        return
    timestamp=last_scraped(menus)
    if timestamp:
        st.caption("Last scraped: "+timestamp_label(timestamp)+" (oldest of the two source snapshots).")
    else:
        st.caption("Last scraped: waiting for both source snapshots.")
    rows=comparison_rows(selected,menus)
    st.html(render_table(selected["name"],rows))
    st.caption("Menu prices only. Delivery fees, service fees, taxes, tips, promotions and paid customizations are excluded. No in-store price is available.")
    if any(r["price_cents"] is None for r in rows):
        st.info("A matched listing is missing or changed in the latest snapshot. Its price is unavailable until reviewed.")
    st.caption("Matches use the listed item name and size/count. Optional choices and current checkout availability are not verified.")
    with st.expander("View original listings"):
        config=json.loads((ROOT/"config/sources.json").read_text())
        for s in config["sources"]:
            if not isinstance(s, dict):
                continue
            if s.get("restaurant_id")=="primo-too-amherst" and s["provider"] in ("ubereats","doordash"):
                st.link_button("Uber Eats" if s["provider"]=="ubereats" else "DoorDash",s["url"])
