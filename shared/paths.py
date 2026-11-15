"""Project paths shared by application packages."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_ROOT = Path(os.getenv("DELIVERY_ARTIFACTS_ROOT", ROOT / "artifacts"))
