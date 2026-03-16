from __future__ import annotations

from typing import Any, Dict

from phase2.config import UserPreferences
from phase2.recommender import recommend
from phase3.prompting import call_groq_for_recommendations


def generate_llm_recommendations(prefs: UserPreferences, catalog_df: Any = None) -> Dict[str, Any]:
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
    base_recs = recommend(prefs, catalog_df=catalog_df)
    if not base_recs:
        return {
            "recommendations": [],
            "explanation": "No restaurants matched the given preferences in the catalog.",
        }

    llm_result = call_groq_for_recommendations(prefs, base_recs)
    
    base_map = {str(r.get('restaurant_id', '')): r for r in base_recs}
    recs = llm_result.get("recommendations", [])
    for r in recs:
        rid = str(r.get("restaurant_id", ""))
        base = base_map.get(rid, {})
        
        r["is_nearby"] = base.get("is_nearby", False)
        
        # Restore fields the LLM might have omitted or hallucinates as N/A
        for k in ["address", "locality", "city"]:
            if k not in r or not r[k] or str(r[k]).lower() == "n/a":
                r[k] = base.get(k, "")
                
        if "average_cost_for_two" not in r or not r["average_cost_for_two"] or str(r["average_cost_for_two"]).lower() == "n/a":
            r["average_cost_for_two"] = base.get("average_cost_for_two")
            
        if "rating" not in r or not r["rating"] or str(r["rating"]).lower() == "n/a":
            r["rating"] = base.get("rating")
            
    return llm_result


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

