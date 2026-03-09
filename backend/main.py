import os
import sys
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Ensure we can import from phase2 and phase3 which are now in the same backend folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from phase2.config import UserPreferences
from phase2.recommender import load_catalog
from phase3.orchestrator import generate_llm_recommendations

# Load environment variables (like GROQ_API_KEY)
load_dotenv(os.path.join(os.path.dirname(__file__), "env", ".env"))

app = FastAPI(title="AI Restaurant Recommender API")

# Allow CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RecommendationRequest(BaseModel):
    place: Optional[str] = None
    cuisines: List[str] = []
    price_category: Optional[str] = None
    min_rating: float = 4.0
    top_k: int = 5

@app.get("/api/options")
def get_options():
    try:
        df = load_catalog()
        
        # Get unique cities only, dropping localities to keep dropdown crisp
        cities = df["city"].dropna().unique().tolist()
        places = sorted(list(set(cities)))
        # Filter out empty strings
        places = [p for p in places if p and str(p).strip()]

        # Get unique cuisines
        cuisines_set = set()
        for cuisine_list in df["cuisines"].dropna():
            if hasattr(cuisine_list, '__iter__') and not isinstance(cuisine_list, str):
                for c in cuisine_list:
                    if c and str(c).strip():
                        cuisines_set.add(str(c).strip())
            elif isinstance(cuisine_list, str):
                for c in cuisine_list.split(','):
                    if c and c.strip():
                        cuisines_set.add(c.strip())
        cuisines = sorted(list(cuisines_set))

        return {
            "places": places,
            "cuisines": cuisines
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/recommend")
def get_recommendations(req: RecommendationRequest):
    try:
        prefs = UserPreferences(
            price_category=None if req.price_category == "Any" else req.price_category,
            max_price=None,
            place=req.place.strip() if req.place else None,
            min_rating=req.min_rating,
            cuisines=[c for c in req.cuisines if c.strip()], # Filter empty strings
            top_k=req.top_k
        )
        
        result = generate_llm_recommendations(prefs)
        recs = result.get("recommendations", [])
        explanation = result.get("explanation", "")
        
        # Fallback 1: If no recommendations, relax cuisines and price
        if not recs and (prefs.cuisines or prefs.price_category):
            prefs.cuisines = []
            prefs.price_category = None
            explanation = "We couldn't find exact matches, so we removed cuisine and price constraints to show you these options:\n"
            result = generate_llm_recommendations(prefs)
            recs = result.get("recommendations", [])
            
        # Fallback 2: If still no recommendations, relax rating and place
        if not recs and (prefs.min_rating > 3.0 or prefs.place):
            prefs.min_rating = 3.0
            prefs.place = None
            explanation = "We couldn't find matches nearby, so we expanded our search broadly:\n"
            result = generate_llm_recommendations(prefs)
            recs = result.get("recommendations", [])

        # Deduplicate recommendations by name
        unique_recs = []
        seen = set()
        for r in recs:
            name = (r.get("name") or "").lower().strip()
            if name and name not in seen:
                seen.add(name)
                unique_recs.append(r)
        
        recs = unique_recs
        
        # Order by rating descending
        def get_rating(r):
            try:
                return float(r.get("rating", 0) or 0)
            except (ValueError, TypeError):
                return 0.0
                
        recs.sort(key=get_rating, reverse=True)
        
        if not recs:
            # We explicitly handle the empty case here
            return {
                "recommendations": [],
                "explanation": "No recommendations returned even after relaxing filters. Try modifying your search."
            }
            
        return {
            "recommendations": recs,
            "explanation": explanation
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
