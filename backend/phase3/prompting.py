from __future__ import annotations

import json
from typing import Any, Dict, List

from groq import Groq

from phase2.config import UserPreferences
from phase3.config import GroqConfig, get_groq_api_key


def build_system_prompt() -> str:
    return (
        "You are an AI restaurant recommendation assistant. "
        "You receive a list of restaurants retrieved from a catalog and user preferences. "
        "You MUST only use the provided restaurants. Do not invent new places. "
        "Respond strictly in JSON matching the requested schema."
    )


def build_user_prompt(prefs: UserPreferences, candidates: List[Dict[str, Any]]) -> str:
    payload = {
        "user_preferences": {
            "price_category": prefs.price_category,
            "max_price": prefs.max_price,
            "place": prefs.place,
            "min_rating": prefs.min_rating,
            "cuisines": prefs.cuisines,
            "top_k": prefs.top_k,
        },
        "candidate_restaurants": candidates,
        "instructions": (
            "Select the best restaurants for the user from the candidates. "
            "You MUST provide at least 5 recommendations if there are enough candidates. "
            "Write a unique, creative, and mouth-watering 3-4 sentence overview for each restaurant. "
            "Each overview must be distinct in style and tone—avoid repetitive patterns. "
            "STRICT RULES: "
            "1. Do NOT include 'Why Recommended', 'Consider If', or bullet points of any kind. "
            "2. Do NOT mention the location/city name in the overview (it's already shown on the card). "
            "3. Focus on the sensory experience: the aroma, the specific signature dishes, and the unique vibe. "
            "4. If multiple cuisines are requested, any restaurant serving AT LEAST ONE of those cuisines is considered a perfect match (OR logic). "
            "Return ONLY valid JSON with this exact structure for every recommendation:\n"
            "{\n"
            '  "recommendations": [\n'
            "    {\n"
            '      "restaurant_id": string,\n'
            '      "name": string,\n'
            '      "cuisines": [string, ...],\n'
            '      "rating": number,\n'
            '      "average_cost_for_two": number,\n'
            '      "summary": string\n'
            "    }, ...\n"
            "  ],\n"
            '  "explanation": string\n'
            "}\n"
            "Do not include any extra keys or text outside this JSON."
        ),
    }
    return json.dumps(payload, indent=2)


def call_groq_for_recommendations(
    prefs: UserPreferences, candidates: List[Dict[str, Any]], config: GroqConfig | None = None
) -> Dict[str, Any]:
    """
    Call Groq LLM to turn deterministic recommendations into clear, grounded text.

    This function assumes GROQ_API_KEY is configured; it will raise a RuntimeError otherwise.
    """
    cfg = config or GroqConfig()
    api_key = get_groq_api_key(cfg)

    client = Groq(api_key=api_key)

    system_msg = build_system_prompt()
    user_msg = build_user_prompt(prefs, candidates)

    completion = client.chat.completions.create(
        model=cfg.model,
        temperature=cfg.temperature,
        max_tokens=cfg.max_output_tokens,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
    )

    content = completion.choices[0].message.content
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Groq response was not valid JSON: {exc}") from exc

    return parsed

