from pathlib import Path

import pandas as pd

from phase1.catalog_builder import build_catalog
from phase1.config import CATALOG_FILE


def test_phase1_build_catalog_creates_parquet_and_has_rows():
    """
    Integration-style test for Phase 1.
    - Runs the full Phase 1 pipeline
    - Asserts that a catalog parquet file is written
    - Asserts that it has at least one restaurant row and expected columns
    """
    catalog_df, stats = build_catalog()

    assert CATALOG_FILE.exists(), "Catalog parquet file was not created"

    loaded = pd.read_parquet(CATALOG_FILE)
    assert len(loaded) > 0, "Catalog should contain at least one restaurant"

    for col in [
        "restaurant_id",
        "name",
        "city",
        "locality",
        "cuisines",
        "average_cost_for_two",
        "rating",
    ]:
        assert col in loaded.columns, f"Expected column '{col}' in catalog"

    # Basic sanity check that stats are populated
    assert stats["catalog_num_rows"] == len(loaded)

