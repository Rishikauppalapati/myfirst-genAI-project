import os
import streamlit as st
from dotenv import load_dotenv

# We need to make sure we can import from phase2 and phase3 which are inside the backend folder
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from phase2.config import UserPreferences
from phase3.orchestrator import generate_llm_recommendations

# Load environment variables (like GROQ_API_KEY)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "env", ".env"))

st.set_page_config(page_title="AI Restaurant Recommender", page_icon="🍽️", layout="centered")

def main():
    st.title("🍽️ AI Restaurant Recommender")
    st.markdown("Find the best restaurants matching your exact preferences, powered by AI.")

    with st.sidebar:
        st.header("Your Preferences")
        place = st.text_input("Place / City / Locality", placeholder="e.g. Koramangala or New Delhi")
        
        c_input = st.text_input("Cuisines (comma-separated)", placeholder="e.g. Italian, Cafe")
        cuisines = [c.strip() for c in c_input.split(",")] if c_input.strip() else []
        
        price_category = st.selectbox("Budget/Price Category", ["Any", "low", "medium", "high"])
        
        min_rating = st.slider("Minimum Rating", 1.0, 5.0, 4.0, 0.1)
        top_k = st.slider("Number of Recommendations", 1, 10, 5, 1)

    if st.button("Find Restaurants", type="primary"):
        prefs = UserPreferences(
            price_category=None if price_category == "Any" else price_category,
            max_price=None,
            place=place if place.strip() else None,
            min_rating=min_rating,
            cuisines=cuisines,
            top_k=top_k
        )

        with st.spinner("Searching catalog and generating recommendations..."):
            try:
                result = generate_llm_recommendations(prefs)
                
                recs = result.get("recommendations", [])
                explanation = result.get("explanation", "")
                
                if not recs:
                    st.warning(explanation or "No restaurants found matching your criteria. Try relaxing your filters.")
                else:
                    st.success("Here are your recommendations!")
                    st.markdown(f"**Explanation:** {explanation}")
                    
                    for i, r in enumerate(recs, 1):
                        with st.expander(f"{i}. {r.get('name', 'Unknown')} - {r.get('rating', 'N/A')} ⭐"):
                            st.write(f"**Place:** {r.get('place', 'N/A')}")
                            st.write(f"**Cuisines:** {', '.join(r.get('cuisines', []))}")
                            st.write(f"**Price:** {r.get('price', 'N/A')}")
                            
                            st.markdown("### Why Recommended?")
                            why = r.get("why_recommended", [])
                            if isinstance(why, list):
                                for reason in why:
                                    st.markdown(f"- {reason}")
                            else:
                                st.write(why)
                                
                            consider_if = r.get("consider_if")
                            if consider_if:
                                st.info(f"**Consider if:** {consider_if}")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
