"""Where the platform reads and writes data, decided by the environment.

CNMV_DATA_DIR overrides the default <repo>/data (containers mount a volume there).
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("CNMV_DATA_DIR", PROJECT_ROOT / "data"))

RAW_DIR = DATA_DIR / "raw"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
GOLD_DIR = DATA_DIR / "gold"
EXPORTS_DIR = DATA_DIR / "exports"

ECB_RAW_DIR = RAW_DIR / "ecb"

# Written last by the ingestion once a bronze period is fully extracted; it holds the
# sha256 of the source zip. The Silver build compares it to know what is new or changed.
COMPLETE_MARKER = ".complete"
