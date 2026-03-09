from dataclasses import dataclass, field
from typing import List, Optional

from phase1.config import CATALOG_FILE


CATALOG_PATH = CATALOG_FILE


@dataclass
class UserPreferences:
    """Normalized user preferences used by the deterministic recommender."""

    price_category: Optional[str] = None  # "low" | "medium" | "high"
    max_price: Optional[float] = None
    place: Optional[str] = None
    min_rating: Optional[float] = None
    cuisines: List[str] = field(default_factory=list)
    top_k: int = 5

