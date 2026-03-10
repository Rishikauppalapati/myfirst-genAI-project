import os
import streamlit as st
from dotenv import load_dotenv

# We need to make sure we can import from phase2 and phase3 which are inside the backend folder
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from phase2.config import UserPreferences
from phase2.recommender import load_catalog
from phase3.orchestrator import generate_llm_recommendations

# Load environment variables (like GROQ_API_KEY)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "env", ".env"))

st.set_page_config(page_title="AI Restaurant Recommender", page_icon="🍽️", layout="centered")

# Custom CSS for UI polish
st.markdown("""
<style>
/* Make sure dropdowns show a pointer hand cursor */
div[data-baseweb="select"] {
    cursor: pointer !important;
}
div[data-baseweb="select"] * {
    cursor: pointer !important;
}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def get_dropdown_options():
    df = load_catalog()
    cities = df["city"].dropna().unique().tolist()
    places = sorted([p for p in set(cities) if p and str(p).strip()])
    
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
    return ["Any"] + places, cuisines

@st.cache_data
def get_price_lookup():
    df = load_catalog()
    lookup = {}
    if "average_cost_for_two" in df.columns and "name" in df.columns:
        for name, cost in zip(df["name"], df["average_cost_for_two"]):
            if name == name and cost == cost:  # Not NaN
                lookup[str(name).lower().strip()] = cost
    return lookup

def main():
    st.title("🍽️ AI Restaurant Recommender")
    st.markdown("Find the best restaurants matching your exact preferences, powered by AI.")

    options_places, options_cuisines = get_dropdown_options()
    price_lookup = get_price_lookup()

    with st.sidebar:
        st.header("Your Preferences")
        place_selection = st.selectbox("Place / City / Locality", options_places)
        place = None if place_selection == "Any" else place_selection
        
        cuisines = st.multiselect("Cuisines", options_cuisines, placeholder="Select cuisines")
        
        price_options = {
            "Any": "Any",
            "Low (Below ₹500)": "low",
            "Medium (₹500 - ₹1000)": "medium",
            "High (Above ₹1000)": "high"
        }
        price_selection = st.select_slider("Budget/Price Category", options=list(price_options.keys()))
        price_category = price_options[price_selection]
        
        min_rating = st.slider("Minimum Rating", 1.0, 5.0, 4.0, 0.1)
        
        # Ensure we fetch enough candidates, especially if multiple cuisines are selected
        # The user requested a minimum of 5, or more if multiple preferences are applied.
        top_k = max(5, len(cuisines) * 2) if cuisines and len(cuisines) > 1 else 5

    if st.button("Find Restaurants", type="primary"):
        prefs = UserPreferences(
            price_category=None if price_category == "Any" else price_category,
            max_price=None,
            place=place,
            min_rating=min_rating,
            cuisines=cuisines,
            top_k=top_k
        )

        with st.spinner("Searching catalog and generating recommendations..."):
            try:
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
                
                # Sort by rating
                def get_rating(r):
                    try:
                        return float(r.get("rating", 0) or 0)
                    except (ValueError, TypeError):
                        return 0.0
                recs.sort(key=get_rating, reverse=True)
                
                if not recs:
                    st.warning("No restaurants found matching your criteria even after relaxing filters. Try modifying your search.")
                else:
                    st.success("Here are your recommendations!")
                    # The user requested to remove the visible insight text but keep it clean
                    
                    fallback_images = [
                        'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=400&q=80',
                        'https://images.unsplash.com/photo-1552566626-52f8b828add9?w=400&q=80',
                        'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=400&q=80',
                        'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=400&q=80',
                        'https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=400&q=80',
                        'https://images.unsplash.com/photo-1544025162-d76694265947?w=400&q=80',
                        'https://images.unsplash.com/photo-1559339352-11d035aa65de?w=400&q=80',
                        'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=400&q=80',
                        'https://images.unsplash.com/photo-1502301103665-0b95cc738daf?w=400&q=80',
                        'https://images.unsplash.com/photo-1498654896293-37aacf113fd9?w=400&q=80'
                    ]
                    
                    for i, r in enumerate(recs, 1):
                        with st.expander(f"{i}. {r.get('name', 'Unknown')} - {r.get('rating', 'N/A')} ⭐"):
                            name_len = len(r.get('name', '')) if r.get('name') else 0
                            img_idx = (name_len + i * 7) % len(fallback_images)
                            st.image(fallback_images[img_idx], use_column_width=True)
                            
                            c1, c2 = st.columns(2)
                            with c1:
                                display_place = r.get('place', 'N/A')
                                if place and place.lower() not in display_place.lower():
                                    display_place = f"{display_place}, {place}"
                                st.write(f"**Place:** {display_place}")
                                
                                raw_price = None
                                formatted_price = "N/A"
                                
                                # ALWAYS Prefer the actual catalog dataset price over the LLM hallucination
                                name_key = r.get('name', '').lower().strip()
                                if name_key in price_lookup:
                                    raw_price = price_lookup[name_key]
                                
                                # If missing from catalog, gracefully fall back to LLM's guess
                                if not raw_price or str(raw_price) == 'N/A' or str(raw_price).strip() == '':
                                    raw_price = r.get('price')
                                
                                if raw_price:
                                    if isinstance(raw_price, (int, float)):
                                        formatted_price = f"~ ₹{int(raw_price)} for 2"
                                    elif isinstance(raw_price, str):
                                        # Extract digits if it's a string like "800 for two"
                                        digits = ''.join(c for c in raw_price if c.isdigit())
                                        if digits:
                                            formatted_price = f"~ ₹{digits} for 2"
                                        else:
                                            # If there's some text but no digits, it might be literally 'N/A'
                                            formatted_price = raw_price if "n/a" not in raw_price.lower() else "Price Varies"
                                else:
                                    formatted_price = "Price Varies"
                                            
                                st.write(f"**Cuisines:** {', '.join(r.get('cuisines', []))}")
                                st.write(f"**Price Approx:** {formatted_price}")
                                
                            with c2:
                                st.markdown("#### Overview")
                                summary = r.get("summary", "")
                                if not summary:
                                    # Fallback if summary is missing but why_recommended exists (legacy support/robustness)
                                    why = r.get("why_recommended", [])
                                    if isinstance(why, list):
                                        summary = " ".join(why)
                                    else:
                                        summary = str(why)
                                
                                st.write(summary)
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
