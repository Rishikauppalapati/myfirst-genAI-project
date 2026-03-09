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


def _filter_catalog(df: pd.DataFrame, prefs: UserPreferences) -> pd.DataFrame:
    filtered = df

    if prefs.place:
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

    w = ranking_weights or DEFAULT_RANKING_WEIGHTS
    wr = w.get("rating", DEFAULT_RANKING_WEIGHTS["rating"])
    wv = w.get("votes", DEFAULT_RANKING_WEIGHTS["votes"])
    wc = w.get("cuisine_match", DEFAULT_RANKING_WEIGHTS["cuisine_match"])
    wp = w.get("place_match", DEFAULT_RANKING_WEIGHTS["place_match"])

    df = filtered.copy()

    rating_norm = df["rating"].fillna(0) / 5.0
    votes_norm = np.log10(df["votes"].fillna(0) + 1.0)

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

    if prefs.place:
        place = prefs.place.lower()

        def place_score(city: Any, locality: Any) -> float:
            parts = [
                str(city).lower() if city is not None else "",
                str(locality).lower() if locality is not None else "",
            ]
            return 1.0 if any(place in p for p in parts) else 0.0

        place_match = [
            place_score(city, loc) for city, loc in zip(df["city"], df["locality"])
        ]
        place_match = pd.Series(place_match, index=df.index)
    else:
        place_match = 0.0

    df["score"] = wr * rating_norm + wv * votes_norm + wc * cuisine_match + wp * place_match

    return df.sort_values(by=["score", "rating"], ascending=False)


def recommend(
    prefs: UserPreferences,
    catalog_df: Optional[pd.DataFrame] = None,
    ranking_weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Deterministic recommendation for Phase 2.
    Returns a list of top-k restaurant dicts without any LLM involvement.
    Phase 4 can pass ranking_weights for tuning.
    """
    if catalog_df is None:
        catalog_df = load_catalog()

    filtered = _filter_catalog(catalog_df, prefs)
    ranked = _rank(filtered, prefs, ranking_weights)

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

