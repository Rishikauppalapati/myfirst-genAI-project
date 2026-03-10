from __future__ import annotations

from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd

from phase1.catalog_builder import build_catalog
from phase2.config import CATALOG_PATH, UserPreferences


# Default ranking weights (can be overridden by Phase 4 tuning)
DEFAULT_RANKING_WEIGHTS = {
    "rating": 2.0,
    "votes": 1.0,
    "cuisine_match": 0.5,
    "place_match": 0.5,
}


def load_catalog() -> pd.DataFrame:
    """
    Load the canonical restaurant catalog built in Phase 1.
    If the catalog file does not exist yet, Phase 1 is executed to build it.
    """
    if not CATALOG_PATH.exists():
        build_catalog()
    return pd.read_parquet(CATALOG_PATH)


def _price_ok(row_cost: Optional[float], prefs: UserPreferences) -> bool:
    if row_cost is None:
        return True

    if prefs.max_price is not None:
        return row_cost <= prefs.max_price

    if prefs.price_category is None:
        return True

    # Simple heuristic thresholds; can be tuned later.
    cat = prefs.price_category.lower()
    if cat == "low":
        return row_cost <= 500
    if cat == "medium":
        return 500 < row_cost <= 1000
    if cat == "high":
        return row_cost > 1000
    return True


def _filter_catalog(df: pd.DataFrame, prefs: UserPreferences, strict_place: bool = True) -> pd.DataFrame:
    filtered = df

    if strict_place and prefs.place:
        place = prefs.place.lower()
        city_match = filtered["city"].fillna("").str.lower().str.contains(place)
        locality_match = filtered["locality"].fillna("").str.lower().str.contains(place)
        filtered = filtered[city_match | locality_match]

    if prefs.min_rating is not None:
        filtered = filtered[
            (filtered["rating"].notna()) & (filtered["rating"] >= prefs.min_rating)
        ]

    if prefs.cuisines:
        wanted = [c.lower() for c in prefs.cuisines]

        def has_cuisine(cuisine_list: Any) -> bool:
            if cuisine_list is None:
                return False
            # Handle list, numpy array, or any iterable
            try:
                lower = [str(c).lower() for c in cuisine_list]
            except (TypeError, ValueError):
                return False
            return any(c in lower for c in wanted)

        filtered = filtered[filtered["cuisines"].apply(has_cuisine)]

    if prefs.price_category is not None or prefs.max_price is not None:
        if "average_cost_for_two" in filtered.columns:
            filtered = filtered[
                filtered["average_cost_for_two"].apply(
                    lambda v: _price_ok(v if pd.notna(v) else None, prefs)
                )
            ]

    return filtered


def _rank(
    filtered: pd.DataFrame,
    prefs: UserPreferences,
    ranking_weights: Optional[Dict[str, float]] = None,
) -> pd.DataFrame:
    if filtered.empty:
        return filtered

    df = filtered.copy()

    df["rating_clean"] = df["rating"].fillna(0)
    df["votes_clean"] = df["votes"].fillna(0)

    if prefs.cuisines:
        wanted = [c.lower() for c in prefs.cuisines]

        def cuisine_score(cuisine_list: Any) -> float:
            if cuisine_list is None:
                return 0.0
            try:
                lower = [str(c).lower() for c in cuisine_list]
            except (TypeError, ValueError):
                return 0.0
            matches = sum(1 for c in wanted if c in lower)
            return float(matches) / max(len(wanted), 1)

        cuisine_match = df["cuisines"].apply(cuisine_score)
    else:
        cuisine_match = 0.0

    df["cuisine_match"] = cuisine_match
    
    # The requirement asks to sort by: Highest rating, then Best match with cuisines, then Popularity.
    return df.sort_values(
        by=["rating_clean", "cuisine_match", "votes_clean"], 
        ascending=[False, False, False]
    )


def recommend(
    prefs: UserPreferences,
    catalog_df: Optional[pd.DataFrame] = None,
    ranking_weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Deterministic recommendation for Phase 2.
    Returns a list of top-k restaurant dicts without any LLM involvement.
    Now prioritizing locality and properly filtering any cuisine matches.
    """
    if catalog_df is None:
        catalog_df = load_catalog()

    # Attempt 1: Strict locality match
    filtered_strict = _filter_catalog(catalog_df, prefs, strict_place=True)
    ranked_strict = _rank(filtered_strict, prefs, ranking_weights)

    # If the user specified a place and we didn't get enough results, show ALL matches first
    # but still prioritize the strictly matching ones at the top.
    if prefs.place:
        filtered_relaxed = _filter_catalog(catalog_df, prefs, strict_place=False)
        ranked_relaxed = _rank(filtered_relaxed, prefs, ranking_weights)
        
        # Combine them: Strict matches first, then any other relevant results
        if not ranked_strict.empty:
            already_in_strict = ranked_strict.index
            ranked_relaxed_remaining = ranked_relaxed.drop(already_in_strict, errors="ignore")
            
            # Tag them
            ranked_strict = ranked_strict.assign(is_nearby=False)
            ranked_relaxed_remaining = ranked_relaxed_remaining.assign(is_nearby=True)
            
            # We strictly keep the user's chosen location results at the VERY TOP
            ranked = pd.concat([ranked_strict, ranked_relaxed_remaining])
        else:
            ranked = ranked_relaxed.assign(is_nearby=True)
    else:
        ranked = ranked_strict.assign(is_nearby=False)

    if ranked.empty:
        return []

    top = ranked.head(prefs.top_k)
    cols = [
        "restaurant_id",
        "name",
        "city",
        "locality",
        "cuisines",
        "rating",
        "votes",
        "url",
        "score",
        "is_nearby"
    ]
    if "average_cost_for_two" in top.columns:
        cols.append("average_cost_for_two")
        
    # Only select columns that actually exist to avoid KeyError
    existing_cols = [c for c in cols if c in top.columns]
    records = top[existing_cols].to_dict(orient="records")
    for r in records:
        if "cuisines" in r:
            c = r["cuisines"]
            if hasattr(c, "tolist"):
                r["cuisines"] = c.tolist()
    return records


def main() -> None:
    prefs = UserPreferences(
        price_category=None,
        max_price=None,
        place=None,
        min_rating=3.5,
        cuisines=[],
        top_k=5,
    )
    results = recommend(prefs)
    print(f"Found {len(results)} recommendations.")
    for r in results:
        print(
            f"{r['name']} ({r.get('city')}) - rating={r.get('rating')}, "
            f"cost_for_two={r.get('average_cost_for_two')}, score={r.get('score'):.3f}"
        )


if __name__ == "__main__":
    main()

