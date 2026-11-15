"""Run from project root: python -m streamlit run frontend/app.py."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import streamlit as st
from frontend.receipts import render as render_receipts
from frontend.landing import render as render_landing
from frontend.theme import apply_theme, brand_header

st.set_page_config(page_title="Crumbs", page_icon="✦", layout="centered", initial_sidebar_state="collapsed")
apply_theme()
brand_header("Crumbs", "Small savings add up, one order at a time.")
# Detach persistent controls from widget cleanup while their tab is hidden.
from frontend.state import preserve_controls
preserve_controls()
home,receipts=st.tabs(["Home","Receipt insights"],key="active_tab",on_change="rerun")
if home.open:
    with home:
        render_landing()
if receipts.open:
    with receipts:
        render_receipts()
