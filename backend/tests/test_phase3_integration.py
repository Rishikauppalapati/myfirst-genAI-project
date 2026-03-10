import pytest

from phase2.config import UserPreferences
from phase3.config import get_groq_api_key
from phase3.orchestrator import generate_llm_recommendations


@pytest.mark.integration
def test_phase3_generate_llm_recommendations_with_groq():
    """
    Integration test for Phase 3 that hits the real Groq API.
    This requires GROQ_API_KEY to be set (or present in .env / env/.env).
    If the key is missing, the test is skipped instead of failing.
    """
    try:
        _ = get_groq_api_key()
    except RuntimeError as exc:
        pytest.skip(str(exc))

    prefs = UserPreferences(
        price_category="medium",
        max_price=None,
        place=None,
        min_rating=4.0,
        cuisines=["Italian"],
        top_k=3,
    )

    result = generate_llm_recommendations(prefs)

    assert isinstance(result, dict)
    assert "recommendations" in result
    assert "explanation" in result

    recs = result["recommendations"]
    assert isinstance(recs, list)
    assert len(recs) <= prefs.top_k

    if recs:
        first = recs[0]
        for key in ("restaurant_id", "name", "summary"):
            assert key in first

