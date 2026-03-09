from __future__ import annotations

from pathlib import Path
from typing import Tuple

import pandas as pd
from datasets import load_dataset, Dataset

from .config import DATASET_NAME, DATA_DIR, RAW_SUBDIR


def ensure_directories() -> None:
    """Create Phase 1 data directories if they do not exist."""
    for path in (DATA_DIR, RAW_SUBDIR):
        Path(path).mkdir(parents=True, exist_ok=True)


def download_raw_dataset(split: str = "train") -> Tuple[Dataset, Path]:
    """
    Download the Hugging Face dataset and cache a raw parquet copy for inspection.

    Returns the in-memory Dataset object and the path to the cached parquet file.
    """
    ensure_directories()

    # Load from Hugging Face (uses HF cache under the hood as well)
    ds = load_dataset(DATASET_NAME, split=split)

    raw_parquet_path = RAW_SUBDIR / f"{split}.parquet"
    # Convert to pandas and persist a snapshot used by later analysis or debugging
    df = ds.to_pandas()
    df.to_parquet(raw_parquet_path, index=False)

    return ds, raw_parquet_path


def compute_basic_stats(df: pd.DataFrame) -> dict:
    """
    Compute simple statistics that describe the dataset and help validate ingestion.
    """
    stats = {
        "num_rows": int(df.shape[0]),
        "num_columns": int(df.shape[1]),
        "columns": list(df.columns),
        "missing_counts": df.isna().sum().to_dict(),
    }

    # Optional helpful stats if these columns exist
    for col in ("rate", "rating", "approx_cost(for two people)", "average_cost_for_two"):
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            stats[f"{col}_summary"] = {
                "min": float(series.min(skipna=True)) if not series.dropna().empty else None,
                "max": float(series.max(skipna=True)) if not series.dropna().empty else None,
                "mean": float(series.mean(skipna=True)) if not series.dropna().empty else None,
            }

    return stats

