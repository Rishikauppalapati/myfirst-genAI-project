from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from .config import CATALOG_FILE, PROCESSED_SUBDIR
from .data_loader import download_raw_dataset, compute_basic_stats
from .schema import Restaurant


def _normalize_cuisines(raw_value) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return [str(c).strip() for c in raw_value if str(c).strip()]
    # Many Zomato datasets store cuisines as comma-separated string
    return [part.strip() for part in str(raw_value).split(",") if part.strip()]


def build_catalog(split: str = "train") -> tuple[pd.DataFrame, dict]:
    """
    End-to-end Phase 1 pipeline:
    - Download raw dataset
    - Normalize into canonical Restaurant schema
    - Persist catalog as Parquet
    - Return catalog dataframe and basic stats
    """
    ds, _ = download_raw_dataset(split=split)
    df = ds.to_pandas()

    base_stats = compute_basic_stats(df)

    # Try to be robust to slightly different column names
    def get_col(row, *candidates):
        for c in candidates:
            if c in row and pd.notna(row[c]):
                return row[c]
        return None

    records: List[Restaurant] = []
    for _, row in df.iterrows():
        raw = row.to_dict()

        restaurant_id = str(
            get_col(row, "restaurant_id", "id", "res_id") or _
        )  # fallback to row index if needed

        name = str(get_col(row, "name", "restaurant_name") or "").strip()

        city = get_col(row, "city", "City", "listed_in(city)")
        locality = get_col(row, "locality", "location", "Location")
        address = get_col(row, "address", "full_address")

        cuisines = _normalize_cuisines(get_col(row, "cuisines", "Cuisines"))

        avg_cost = get_col(
            row,
            "average_cost_for_two",
            "Average Cost for two",
            "approx_cost(for two people)",
        )
        try:
            average_cost_for_two = float(avg_cost) if avg_cost is not None else None
        except (TypeError, ValueError):
            average_cost_for_two = None

        rating_val = get_col(row, "rating", "aggregate_rating", "rate")
        try:
            rating = float(str(rating_val).split("/")[0]) if rating_val is not None else None
        except (TypeError, ValueError):
            rating = None

        votes_val = get_col(row, "votes", "votes_count")
        try:
            votes = int(votes_val) if votes_val is not None else None
        except (TypeError, ValueError):
            votes = None

        url = get_col(row, "url", "link")

        records.append(
            Restaurant(
                restaurant_id=restaurant_id,
                name=name,
                city=str(city) if city is not None else None,
                locality=str(locality) if locality is not None else None,
                address=str(address) if address is not None else None,
                cuisines=cuisines,
                average_cost_for_two=average_cost_for_two,
                rating=rating,
                votes=votes,
                url=str(url) if url is not None else None,
                raw=raw,
            )
        )

    # Convert to DataFrame for easy storage / later querying
    catalog_df = pd.DataFrame(
        [
            {
                "restaurant_id": r.restaurant_id,
                "name": r.name,
                "city": r.city,
                "locality": r.locality,
                "address": r.address,
                "cuisines": r.cuisines,
                "average_cost_for_two": r.average_cost_for_two,
                "rating": r.rating,
                "votes": r.votes,
                "url": r.url,
            }
            for r in records
        ]
    )

    # Ensure output directory exists and persist catalog
    Path(PROCESSED_SUBDIR).mkdir(parents=True, exist_ok=True)
    catalog_df.to_parquet(CATALOG_FILE, index=False)

    stats = {
        **base_stats,
        "catalog_num_rows": int(catalog_df.shape[0]),
        "catalog_num_columns": int(catalog_df.shape[1]),
    }

    return catalog_df, stats


def main() -> None:
    catalog_df, stats = build_catalog()
    print("Phase 1 catalog built.")
    print(f"Rows: {stats['catalog_num_rows']}, Columns: {stats['catalog_num_columns']}")


if __name__ == "__main__":
    main()

