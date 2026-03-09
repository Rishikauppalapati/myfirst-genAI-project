from __future__ import annotations

from typing import Any, Dict

from phase2.config import UserPreferences
from phase2.recommender import recommend
from phase3.prompting import call_groq_for_recommendations


def generate_llm_recommendations(prefs: UserPreferences) -> Dict[str, Any]:
    """
    Phase 3 orchestration:
    - Uses Phase 2 deterministic recommendations as grounded context.
    - Calls Groq LLM to produce clear, structured recommendations.

    Returns the parsed JSON structure from the LLM:
    {
      "recommendations": [...],
      "explanation": "..."
    }
    """
    base_recs = recommend(prefs)
    if not base_recs:
        return {
            "recommendations": [],
            "explanation": "No restaurants matched the given preferences in the catalog.",
        }

    return call_groq_for_recommendations(prefs, base_recs)


def main() -> None:
    """
    Convenience entrypoint for manual testing once GROQ_API_KEY is configured.
    This is not used by automated tests yet.
    """
    prefs = UserPreferences(
        price_category="medium",
        max_price=None,
        place=None,
        min_rating=4.0,
        cuisines=["Italian"],
        top_k=5,
    )

    result = generate_llm_recommendations(prefs)
    print(result)


if __name__ == "__main__":
    main()

