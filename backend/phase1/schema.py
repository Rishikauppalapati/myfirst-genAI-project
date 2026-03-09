from dataclasses import dataclass
from typing import List, Optional, Any, Dict


@dataclass
class Restaurant:
    """Canonical restaurant record used across phases."""

    restaurant_id: str
    name: str
    city: Optional[str]
    locality: Optional[str]
    address: Optional[str]
    cuisines: List[str]
    average_cost_for_two: Optional[float]
    rating: Optional[float]
    votes: Optional[int]
    url: Optional[str]
    raw: Dict[str, Any]

