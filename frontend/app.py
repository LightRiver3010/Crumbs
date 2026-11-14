"""Run from project root: python -m streamlit run frontend/app.py."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import streamlit as st
from frontend.comparison import render as render_comparison
from frontend.receipts import render as render_receipts
from frontend.theme import apply_theme, brand_header

st.set_page_config(page_title="Platewise", page_icon="✦", layout="centered", initial_sidebar_state="collapsed")
apply_theme()
brand_header("Platewise", "Make every delivery dollar go further.")
# Detach persistent controls from widget cleanup while their tab is hidden.
from frontend.state import preserve_controls
preserve_controls()
comparison,receipts=st.tabs(["Compare prices","Receipt insights"],key="active_tab",on_change="rerun")
if comparison.open:
    with comparison:
        render_comparison()
if receipts.open:
    with receipts:
        render_receipts()
