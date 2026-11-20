"""Non-secret defaults; credentials remain in .env or local cloud login."""
import json
import os
from dotenv import load_dotenv
from shared.paths import ROOT
load_dotenv(ROOT / ".env")
DEFAULTS = json.loads((ROOT / "config/sources.json").read_text())["defaults"]
PROJECT = DEFAULTS["project"]
BUCKET = DEFAULTS["bucket"]
LOCATION = DEFAULTS["location"]


def secret(name):
    """Read a deployment secret from environment variables or Streamlit secrets."""
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st
        value = st.secrets.get(name)
    except (ImportError, FileNotFoundError, KeyError):
        value = None
    return str(value) if value else None


MODEL = secret("GEMINI_MODEL") or "gemini-2.5-flash"
