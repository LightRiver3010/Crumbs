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
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
