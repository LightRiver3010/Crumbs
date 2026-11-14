"""Multi-image receipt review and personal savings MVP."""
import hashlib
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from receipt_extraction.dates import resolve_missing_years
import streamlit as st
from receipt_extraction.pipeline import prepare
from receipt_extraction.gemini_client import extraction_error_message
from receipt_extraction.schemas import Extraction
from receipt_extraction.repository import save,read_orders
from frontend.receipt_savings import render as render_insights
from frontend.theme import section_header


def remember_uploads():
    # Separate session storage survives file-uploader widget cleanup on tab switches.
    st.session_state.receipt_uploads=list(st.session_state.get("receipt_upload_widget",[]))


def render():
    section_header("KNOW YOUR HABITS", "Your delivery orders", "Upload a few receipts to see where your money is going.")
    st.write("More screenshots = more accurate data")
    st.caption("Upload complete, non-overlapping order histories where possible. Images go to S3 and Gemini; confirmed orders go to BigQuery.")
    st.session_state.setdefault("session_id",str(uuid.uuid4()))
    st.session_state.setdefault("receipt_drafts",{})
    st.file_uploader("Choose screenshots (up to 10 MB each)",type=["png","jpg","jpeg","webp","heic","heif","bmp","tif","tiff","gif"],accept_multiple_files=True,key="receipt_upload_widget",on_change=remember_uploads)
    uploads=st.session_state.get("receipt_uploads",[])
    if uploads:
        st.caption("Selected screenshots: "+", ".join(u.name for u in uploads))
    habit=st.radio("Do these screenshots reflect your normal ordering habits?",["Yes","Usually more","Usually less"],index=None,help="Usually more/less means you normally order more/less often than shown here.",key="ordering_habit") if uploads or st.session_state.get("saved_orders") else None
    if uploads:
        selected={hashlib.sha256(u.getvalue()).hexdigest():u for u in uploads}
        if st.button("Extract orders", disabled=habit is None, use_container_width=True, type="primary"):
            for key,upload in selected.items():
                if key in st.session_state.receipt_drafts: continue
                try:
                    with st.spinner("Reading "+upload.name+"..."):
                        st.session_state.receipt_drafts[key]=prepare(upload.getvalue(),st.session_state.session_id)
                except Exception as exc: st.error(extraction_error_message(exc))
        for key,upload in selected.items():
            if key not in st.session_state.receipt_drafts: continue
            identifier,uri,extraction=st.session_state.receipt_drafts[key]
            with st.expander("Review: "+upload.name,expanded=True):
                for warning in extraction.warnings: st.warning(warning)
                st.caption("Edit JSON as needed. Amounts are cents. Remove duplicate orders from overlapping screenshots; retain exact item sizes and counts.")
                edited=st.text_area("Extracted orders",extraction.model_dump_json(indent=2),height=280,key="review_"+key)
                st.caption("Dates like Sep 19 are preserved in order_date_text. Confirm a year below to fill missing full dates, or edit order_date as YYYY-MM-DD. For histories spanning multiple years, edit dates individually.")
                apply_year=st.checkbox("Apply a confirmed year to dates that show only month and day",key="apply_year_"+key)
                year=None
                if apply_year:
                    year=st.number_input("Year for missing-year dates in this screenshot",min_value=2000,max_value=2100,value=datetime.now(ZoneInfo("America/New_York")).year,step=1,key="date_year_"+key)
                    try:
                        preview=resolve_missing_years(Extraction.model_validate_json(edited),int(year))
                        st.write([{ "Visible date":o.order_date_text, "Date to save":o.order_date.isoformat() if o.order_date else "Unknown" } for o in preview.orders])
                    except ValueError as exc:
                        st.warning(str(exc))
                checked=st.checkbox("I checked these orders and removed duplicates",key="confirm_"+key)
                if st.button("Save confirmed orders",disabled=not checked,key="save_"+key):
                    try:
                        reviewed=Extraction.model_validate_json(edited)
                        if apply_year:
                            reviewed=resolve_missing_years(reviewed,int(year))
                        if any(o.order_date is None for o in reviewed.orders):
                            st.warning("Some dates remain unknown; those orders will not contribute to weekday insights.")
                        save(st.session_state.session_id,identifier,uri,reviewed)
                        st.success("Saved to BigQuery.")
                        st.session_state.refresh_receipts=True
                    except Exception as exc: st.error(f"Save failed ({type(exc).__name__}). Check the edited JSON and cloud access.")
    if st.button("Refresh my summaries", use_container_width=True): st.session_state.refresh_receipts=True
    if st.session_state.pop("refresh_receipts",False):
        try: st.session_state.saved_orders=read_orders(st.session_state.session_id)
        except Exception: st.error("Could not refresh saved orders. Check BigQuery access.")
    orders=st.session_state.get("saved_orders",[])
    if orders:
        if habit is None: st.info("Select whether these screenshots reflect your normal ordering habits to view insights.")
        else: render_insights(orders,habit)
    st.caption("Insights cover confirmed uploads in this browser session. Reloading can start a new session. Population benchmarks are deferred.")
