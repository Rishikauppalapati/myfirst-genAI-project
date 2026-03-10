import os
from pathlib import Path

DATASET_NAME = "ManikaSaini/zomato-restaurant-recommendation"

# Where Phase 1 will cache raw and processed data
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "phase1"
RAW_SUBDIR = DATA_DIR / "raw"
PROCESSED_SUBDIR = DATA_DIR / "processed"

# Canonical catalog filename (Parquet for efficient loading later phases)
CATALOG_FILE = PROCESSED_SUBDIR / "restaurant_catalog.parquet"

