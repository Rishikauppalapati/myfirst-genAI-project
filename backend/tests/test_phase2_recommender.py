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
        "score",
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

