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
        
        price_category = st.selectbox("Budget/Price Category", ["Any", "low", "medium", "high"])
        
        min_rating = st.slider("Minimum Rating", 1.0, 5.0, 4.0, 0.1)
        top_k = st.slider("Number of Recommendations", 1, 10, 5, 1)

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
                                
                                raw_price = r.get('price')
                                formatted_price = "N/A"
                                
                                # Try to get price from dataset lookup if it's missing or N/A
                                if not raw_price or str(raw_price) == 'N/A' or str(raw_price).strip() == '':
                                    name_key = r.get('name', '').lower().strip()
                                    if name_key in price_lookup:
                                        raw_price = price_lookup[name_key]
                                
                                if raw_price:
                                    if isinstance(raw_price, (int, float)):
                                        formatted_price = f"₹{int(raw_price)} for 2"
                                    elif isinstance(raw_price, str):
                                        # Extract digits if it's a string like "800 for two"
                                        digits = ''.join(c for c in raw_price if c.isdigit())
                                        if digits:
                                            formatted_price = f"₹{digits} for 2"
                                        else:
                                            formatted_price = raw_price
                                            
                                st.write(f"**Style:** {', '.join(r.get('cuisines', []))}")
                                st.write(f"**Price Approx:** {formatted_price}")
                                
                            with c2:
                                if r.get('summary'):
                                    st.info(f"**Overview:** {r.get('summary')}")
                            
                            st.markdown("#### Why Recommended?")
                            why = r.get("why_recommended", [])
                            if isinstance(why, list):
                                for reason in why:
                                    st.markdown(f"- {reason}")
                            else:
                                st.write(why)
                                
                            consider_if = r.get("consider_if")
                            if consider_if:
                                st.success(f"💡 **Consider if:** {consider_if}")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
