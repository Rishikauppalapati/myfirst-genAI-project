"""Phase 4: Offline evaluation suite and regression checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from phase2.config import UserPreferences
from phase2.recommender import recommend
from phase4.config import DEFAULT_EVAL_CASES, EvalCase, RankingWeights


@dataclass
class EvalResult:
    """Result of a single eval case."""

    name: str
    passed: bool
    num_results: int
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


def _check_constraints(
    results: List[Dict[str, Any]], case: EvalCase
) -> tuple[bool, str]:
    """Verify that results satisfy case constraints."""
    if len(results) < case.min_results:
        return False, f"Expected at least {case.min_results} results, got {len(results)}"

    if case.max_results is not None and len(results) > case.max_results:
        return False, f"Expected at most {case.max_results} results, got {len(results)}"

    if case.must_have_cuisine:
        wanted = case.must_have_cuisine.lower()
        for r in results:
            cuisines = r.get("cuisines")
            if cuisines is not None:
                if hasattr(cuisines, "tolist"):
                    cuisines = cuisines.tolist()
                elif isinstance(cuisines, str):
                    cuisines = [cuisines]
                try:
                    lower = [str(c).lower() for c in cuisines]
                    if wanted in lower:
                        break
                except TypeError:
                    pass
        else:
            return False, f"No result had required cuisine '{case.must_have_cuisine}'"

    if case.must_have_place:
        place = case.must_have_place.lower()
        for r in results:
            city = (r.get("city") or "").lower()
            locality = (r.get("locality") or "").lower()
            if place in city or place in locality:
                break
        else:
            return False, f"No result matched required place '{case.must_have_place}'"

    if case.min_rating_any is not None:
        for r in results:
            rating = r.get("rating")
            if rating is not None and rating < case.min_rating_any:
                return False, f"Result has rating {rating} < {case.min_rating_any}"

    return True, ""


def run_eval(
    cases: Optional[List[EvalCase]] = None,
    catalog_df: Optional[pd.DataFrame] = None,
    ranking_weights: Optional[Dict[str, float]] = None,
) -> List[EvalResult]:
    """
    Run the offline evaluation suite.
    Returns a list of EvalResult for each case.
    """
    cases = cases or DEFAULT_EVAL_CASES
    weights_dict: Optional[Dict[str, float]] = None
    if ranking_weights is not None:
        if isinstance(ranking_weights, RankingWeights):
            weights_dict = {
                "rating": ranking_weights.rating,
                "votes": ranking_weights.votes,
                "cuisine_match": ranking_weights.cuisine_match,
                "place_match": ranking_weights.place_match,
            }
        else:
            weights_dict = ranking_weights

    results: List[EvalResult] = []
    for case in cases:
        recs = recommend(
            case.prefs,
            catalog_df=catalog_df,
            ranking_weights=weights_dict,
        )
        ok, msg = _check_constraints(recs, case)
        results.append(
            EvalResult(
                name=case.name,
                passed=ok,
                num_results=len(recs),
                message=msg,
                details={"top_names": [r.get("name") for r in recs[:3]]},
            )
        )
    return results


def run_regression_checks(
    catalog_df: Optional[pd.DataFrame] = None,
) -> tuple[bool, List[EvalResult]]:
    """
    Run regression checks. Returns (all_passed, results).
    """
    results = run_eval(catalog_df=catalog_df)
    all_passed = all(r.passed for r in results)
    return all_passed, results
