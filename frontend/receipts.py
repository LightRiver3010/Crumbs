"""Multi-image receipt review and personal savings MVP."""
import hashlib
import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from receipt_extraction.dates import resolve_missing_years
from receipt_extraction.gemini_client import extraction_error_message
import streamlit as st
from receipt_extraction.pipeline import prepare
from receipt_extraction.schemas import Extraction
from receipt_extraction.repository import save,read_orders
from frontend.receipt_savings import render as render_insights
from frontend.theme import section_header

logger = logging.getLogger(__name__)


def remember_uploads():
    # Separate session storage survives file-uploader widget cleanup on tab switches.
    st.session_state.receipt_uploads=list(st.session_state.get("receipt_upload_widget",[]))


def _show_extraction_status(upload_name, message):
    st.info(f"We couldn't finish reading {upload_name}. {message}")


def _order_summary(extraction):
    return [{
        "Restaurant": order.restaurant or "Unknown",
        "Date": order.order_date.isoformat() if order.order_date else order.order_date_text or "Unknown",
        "Total": f"${order.total_cents / 100:,.2f}" if order.total_cents is not None else "Unknown",
        "Items": ", ".join(
            f"{item.name} ×{item.quantity}" if item.quantity else item.name
            for item in order.items
        ) or "No visible items",
    } for order in extraction.orders]


def render():
    section_header("COLLECT YOUR CRUMBS", "Your delivery orders", "Upload a few receipts to spot the small habits that add up.")
    st.write("More screenshots = more accurate data")
    st.caption("Upload complete, non-overlapping order histories where possible. Images go to S3 and Gemini; confirmed orders go to BigQuery.")
    st.session_state.setdefault("session_id",str(uuid.uuid4()))
    st.session_state.setdefault("receipt_drafts",{})
    st.file_uploader("Choose screenshots (up to 10 MB each)",type=["png","jpg","jpeg","webp","heic","heif","bmp","tif","tiff","gif"],accept_multiple_files=True,key="receipt_upload_widget",on_change=remember_uploads)
    uploads=st.session_state.get("receipt_uploads",[])
    if uploads:
        st.caption("Selected screenshots: "+", ".join(u.name for u in uploads))
    if uploads or st.session_state.get("saved_orders"):
        habit_args={"options": ["Yes", "Usually more", "Usually less"],
                    "help": "Usually more/less means you normally order more/less often than shown here.",
                    "key": "ordering_habit"}
        if "ordering_habit" not in st.session_state:
            habit_args["index"]=None
        habit=st.radio("Do these screenshots reflect your normal ordering habits?",**habit_args)
    else:
        habit=None
    if uploads:
        selected={hashlib.sha256(u.getvalue()).hexdigest():u for u in uploads}
        if st.button("Extract orders", disabled=habit is None, use_container_width=True, type="primary"):
            for key,upload in selected.items():
                if key in st.session_state.receipt_drafts: continue
                try:
                    with st.spinner("Reading "+upload.name+"..."):
                        st.session_state.receipt_drafts[key]=prepare(upload.getvalue(),st.session_state.session_id)
                except Exception as exc:
                    reference = uuid.uuid4().hex[:12]
                    cause = exc.__cause__ or exc
                    code = getattr(cause, "code", None)
                    logger.error(
                        "Receipt failure reference=%s stage=%s error_type=%s status=%s",
                        reference, getattr(exc, "stage", "unknown"),
                        type(cause).__name__, code if isinstance(code, int) else "unknown",
                    )
                    _show_extraction_status(upload.name, extraction_error_message(exc) + f" Reference: {reference}.")
        for key,upload in selected.items():
            if key not in st.session_state.receipt_drafts: continue
            identifier,uri,extraction=st.session_state.receipt_drafts[key]
            with st.expander("Review: "+upload.name,expanded=True):
                if extraction.warnings:
                    with st.expander("Details to review"):
                        for warning in extraction.warnings:
                            st.caption(warning)
                st.dataframe(_order_summary(extraction),hide_index=True,width="stretch")
                st.caption("Dates like Sep 19 are preserved for review. Confirm a year below to fill missing full dates; dates that remain unknown are still saved.")
                apply_year=st.checkbox("Apply a confirmed year to dates that show only month and day",key="apply_year_"+key)
                year=None
                if apply_year:
                    year=st.number_input("Year for missing-year dates in this screenshot",min_value=2000,max_value=2100,value=datetime.now(ZoneInfo("America/New_York")).year,step=1,key="date_year_"+key)
                    try:
                        preview=resolve_missing_years(extraction,int(year))
                        st.write([{ "Visible date":o.order_date_text, "Date to save":o.order_date.isoformat() if o.order_date else "Unknown" } for o in preview.orders])
                    except ValueError as exc:
                        st.info(f"We couldn't preview the dates yet: {exc}")
                checked=st.checkbox("I checked these extracted orders",key="confirm_"+key)
                if st.button("Save confirmed orders",disabled=not checked,key="save_"+key):
                    try:
                        reviewed=resolve_missing_years(extraction,int(year)) if apply_year else extraction
                        if any(o.order_date is None for o in reviewed.orders):
                            st.info("Some dates are still unknown. Those orders will be saved, but they will not contribute to weekday insights.")
                        save(st.session_state.session_id,identifier,uri,reviewed)
                        st.session_state.refresh_receipts=True
                    except Exception:
                        st.info("We couldn't save these orders yet. Please try again.")
    if st.button("Refresh my summaries", use_container_width=True): st.session_state.refresh_receipts=True
    if st.session_state.pop("refresh_receipts",False):
        try: st.session_state.saved_orders=read_orders(st.session_state.session_id)
        except Exception: st.info("Your saved summaries are temporarily unavailable. Please try refreshing again.")
    orders=st.session_state.get("saved_orders",[])
    if orders:
        if habit is None: st.info("Select whether these screenshots reflect your normal ordering habits to view insights.")
        else: render_insights(orders,habit)
    st.caption("Insights cover confirmed uploads in this browser session. Reloading can start a new session. Population benchmarks are deferred.")
