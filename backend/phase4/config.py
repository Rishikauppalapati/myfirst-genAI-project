"""Phase 4: Evaluation, tuning, and production hardening config."""

from dataclasses import dataclass, field
from typing import List, Optional

from phase2.config import UserPreferences


@dataclass
class RankingWeights:
    """Tunable weights for the Phase 2 ranking formula."""

    rating: float = 2.0
    votes: float = 1.0
    cuisine_match: float = 0.5
    place_match: float = 0.5


@dataclass
class EvalCase:
    """A single evaluation test case: preferences + expected constraints."""

    name: str
    prefs: UserPreferences
    min_results: int = 1
    max_results: Optional[int] = None
    must_have_cuisine: Optional[str] = None
    must_have_place: Optional[str] = None
    min_rating_any: Optional[float] = None


# Default eval cases for regression checks
DEFAULT_EVAL_CASES: List[EvalCase] = [
    EvalCase(
        name="loose_prefs",
        prefs=UserPreferences(
            price_category=None,
            max_price=None,
            place=None,
            min_rating=None,
            cuisines=[],
            top_k=5,
        ),
        min_results=1,
    ),
    EvalCase(
        name="with_cuisine",
        prefs=UserPreferences(
            price_category=None,
            max_price=None,
            place=None,
            min_rating=3.0,
            cuisines=["North Indian"],  # Common in Zomato dataset
            top_k=5,
        ),
        min_results=1,
        must_have_cuisine="North Indian",
    ),
    EvalCase(
        name="with_rating",
        prefs=UserPreferences(
            price_category=None,
            max_price=None,
            place=None,
            min_rating=4.0,
            cuisines=[],
            top_k=3,
        ),
        min_results=0,
        min_rating_any=4.0,
    ),
]
