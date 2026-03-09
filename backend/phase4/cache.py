"""Phase 4: Caching for catalog and optional LLM responses."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable, Dict, Optional, TypeVar

import pandas as pd

from phase1.config import CATALOG_FILE
from phase2.recommender import load_catalog

T = TypeVar("T")


def get_catalog_cached() -> pd.DataFrame:
    """
    Load catalog with simple in-memory cache.
    Cache is invalidated when the underlying parquet file changes (by mtime).
    """
    return _load_catalog_cached(str(CATALOG_FILE))


def _catalog_cache_key(path: str) -> str:
    """Cache key includes path and mtime for invalidation."""
    from pathlib import Path
    p = Path(path)
    mtime = p.stat().st_mtime if p.exists() else 0
    return f"{path}:{mtime}"


# Use a module-level cache; maxsize=1 is enough for catalog
_catalog_cache: Dict[str, pd.DataFrame] = {}


def _load_catalog_cached(path: str) -> pd.DataFrame:
    key = _catalog_cache_key(path)
    if key not in _catalog_cache:
        _catalog_cache[key] = load_catalog()
    return _catalog_cache[key]


def clear_catalog_cache() -> None:
    """Clear the catalog cache (useful for tests)."""
    _catalog_cache.clear()


class LLMCache:
    """
    Simple in-memory cache for LLM responses.
    Key is a hash of (prefs, candidates); value is the parsed JSON result.
    """

    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, Any] = {}
        self._max_size = max_size
        self._order: list = []

    def _make_key(self, prefs: Any, candidates: list) -> str:
        import json
        try:
            raw = json.dumps(
                {
                    "price": getattr(prefs, "price_category", None),
                    "place": getattr(prefs, "place", None),
                    "min_rating": getattr(prefs, "min_rating", None),
                    "cuisines": getattr(prefs, "cuisines", []),
                    "top_k": getattr(prefs, "top_k", 5),
                    "candidate_ids": [c.get("restaurant_id") for c in candidates[:10]],
                },
                sort_keys=True,
            )
            return str(hash(raw))
        except Exception:
            return str(id(prefs))

    def get(self, prefs: Any, candidates: list) -> Optional[Any]:
        key = self._make_key(prefs, candidates)
        return self._cache.get(key)

    def set(self, prefs: Any, candidates: list, value: Any) -> None:
        key = self._make_key(prefs, candidates)
        if key in self._cache:
            self._order.remove(key)
        elif len(self._cache) >= self._max_size:
            oldest = self._order.pop(0)
            del self._cache[oldest]
        self._cache[key] = value
        self._order.append(key)
