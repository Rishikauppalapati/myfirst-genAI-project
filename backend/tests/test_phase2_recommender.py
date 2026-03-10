from phase2.config import UserPreferences
from phase2.recommender import load_catalog, recommend


def test_phase2_recommend_returns_some_results():
    """
    End-to-end test for Phase 2 deterministic recommendations.
    Uses very loose preferences to ensure we get at least one recommendation.
    """
    catalog_df = load_catalog()

    prefs = UserPreferences(
        price_category=None,
        max_price=None,
        place=None,
        min_rating=None,
        cuisines=[],
        top_k=5,
    )

    results = recommend(prefs, catalog_df=catalog_df)

    assert isinstance(results, list)
    assert len(results) > 0
    assert len(results) <= prefs.top_k

    required_keys = {
        "restaurant_id",
        "name",
        "city",
        "locality",
        "cuisines",
        "average_cost_for_two",
        "rating",
    }
    for r in results:
        assert required_keys.issubset(r.keys())


def test_phase2_respects_top_k():
    catalog_df = load_catalog()

    prefs = UserPreferences(
        price_category=None,
        max_price=None,
        place=None,
        min_rating=None,
        cuisines=[],
        top_k=3,
    )

    results = recommend(prefs, catalog_df=catalog_df)
    assert 0 < len(results) <= 3


def test_phase2_multiple_cuisines_and_locality_fallback():
    catalog_df = load_catalog()

    prefs = UserPreferences(
        price_category=None,
        max_price=None,
        place="SomePlaceThatDoesntExistInCatalog123", # Force fallback
        min_rating=None,
        cuisines=["Asian", "Italian"], # Multiple cuisines
        top_k=5,
    )

    results = recommend(prefs, catalog_df=catalog_df)
    
    # We should get results because it should fall back from the missing place
    # to find matching cuisines anywhere.
    assert len(results) > 0
    assert len(results) <= 5
    
    # Verify that returned results match AT LEAST ONE of the requested cuisines
    for r in results:
        r_cuisines = [c.lower() for c in r.get("cuisines", [])]
        assert "asian" in r_cuisines or "italian" in r_cuisines

