"""Minimal local MVP. Run from project root with streamlit run frontend/app.py."""
import sys
from pathlib import Path
# Streamlit launches a file rather than a package module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uuid
import streamlit as st
from receipt_extraction.pipeline import prepare
from receipt_extraction.gemini_client import extraction_error_message
from receipt_extraction.schemas import Extraction
from receipt_extraction.repository import save
from receipt_extraction.analytics import summarize

st.title("Your delivery orders")
st.caption("Upload a receipt or order-history screenshot. Images go to S3 and Gemini; confirmed orders go to BigQuery.")
st.session_state.setdefault("session_id", str(uuid.uuid4()))
upload = st.file_uploader("Choose an image (up to 10 MB)", type=["png","jpg","jpeg","webp","heic","heif","bmp","tif","tiff","gif"])
if upload:
    import hashlib
    selected = hashlib.sha256(upload.getvalue()).hexdigest()
    if st.session_state.get("selected") != selected:
        st.session_state.pop("draft", None)
        st.session_state["selected"] = selected
    if st.button("Extract orders", disabled="draft" in st.session_state):
        try:
            with st.spinner("Reading screenshot..."):
                identifier, uri, extraction = prepare(upload.getvalue(), st.session_state.session_id)
            st.session_state.draft = (identifier, uri, extraction)
            st.rerun()
        except Exception as exc:
            st.error(extraction_error_message(exc))
    if "draft" in st.session_state:
        identifier, uri, extraction = st.session_state.draft
        for warning in extraction.warnings:
            st.warning(warning)
        st.caption("Review and edit the JSON below. Amounts are cents; unknown values are null. Remove duplicate orders from overlapping screenshots.")
        edited = st.text_area("Extracted orders", extraction.model_dump_json(indent=2), height=350, key=f"review_{selected}")
        confirmed = st.checkbox("I checked these orders and removed duplicates", key=f"confirm_{selected}")
        if st.button("Save confirmed orders", disabled=not confirmed):
            try:
                reviewed = Extraction.model_validate_json(edited)
                if not reviewed.orders:
                    st.warning("There are no orders to save.")
                else:
                    save(st.session_state.session_id, identifier, uri, reviewed)
                    st.success("Saved to BigQuery.")
                    st.session_state.show_summary = True
            except Exception as exc:
                st.error(f"Save failed ({type(exc).__name__}). Check the JSON and BigQuery setup, then retry.")
if st.button("Refresh my summaries"):
    st.session_state.show_summary = True
if st.session_state.get("show_summary"):
    try:
        rows = summarize(st.session_state.session_id)
        if rows:
            st.dataframe(rows)
        else:
            st.info("No confirmed orders in this session yet.")
    except Exception as exc:
        st.error(f"Summary unavailable ({type(exc).__name__}). Check BigQuery setup.")
st.caption("Summaries cover uploads in this browser session only. Benchmark comparison is not connected yet. Reloading can start a new session; this MVP has no account login.")
