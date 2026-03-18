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

@st.cache_data
def get_location_lookup():
    df = load_catalog()
    lookup = {}
    if "name" in df.columns:
        for _, row in df.iterrows():
            name = str(row["name"]).lower().strip()
            loc = str(row.get("locality", "")).strip()
            addr = str(row.get("address", "")).strip()
            if loc == "nan": loc = ""
            if addr == "nan": addr = ""
            lookup[name] = {"locality": loc, "address": addr}
    return lookup

def format_location_str(place, r, location_lookup, name_key):
    import re
    loc_data = location_lookup.get(name_key, {})
    cat_address = loc_data.get("address", "")
    cat_locality = loc_data.get("locality", "")
    
    address = cat_address if cat_address else r.get('address', '')
    locality = cat_locality if cat_locality else r.get('locality', '')
    city = r.get('city', 'Bangalore')
    
    # Remove unwanted terms
    def clean(s):
        if not s: return ""
        s = str(s).strip()
        if s.lower() in ["nan", "n/a", "none", "unknown"]: return ""
        return s

    address = clean(address)
    locality = clean(locality)
    city = clean(city)

    parts = []
    if address:
        parts.append(address)
    if locality and locality.lower() not in address.lower():
        parts.append(locality)
    if city and city.lower() not in address.lower() and city.lower() not in locality.lower():
        parts.append(city)
        
    final_loc_str = ", ".join(parts)
    # Final regex cleanup to ensure no N/A slips through
    final_loc_str = re.sub(r'(?i)\bn/a\b', '', final_loc_str).strip(' ,')
    
    return final_loc_str or "Bangalore" # Default to Bangalore if everything is empty

def main():
    st.title("🍽️ AI Restaurant Recommender")
    st.markdown("Find the best restaurants matching your exact preferences, powered by AI.")

    options_places, options_cuisines = get_dropdown_options()
    price_lookup = get_price_lookup()
    location_lookup = get_location_lookup()

    with st.sidebar:
        st.header("Your Preferences")
        place_selection = st.selectbox("Location", options_places)
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
                from phase2.recommender import load_catalog as _load_catalog
                import pandas as pd

                _df = _load_catalog()

                # --- Step-by-step diagnosis to identify WHICH filter caused the empty result ---

                def _in_location(df, place):
                    if not place:
                        return df
                    p = place.lower()
                    return df[df["city"].fillna("").str.lower().str.contains(p) |
                              df["locality"].fillna("").str.lower().str.contains(p)]

                def _has_cuisine(cuisine_list, wanted):
                    if cuisine_list is None:
                        return False
                    try:
                        lower = [str(c).lower() for c in cuisine_list]
                    except Exception:
                        return False
                    return any(c in lower for c in wanted)

                def _price_ok_check(cost, cat):
                    if cost is None or (isinstance(cost, float) and pd.isna(cost)):
                        return True
                    try:
                        cost = float(cost)
                    except Exception:
                        return True
                    if cat == "low":
                        return cost <= 500
                    if cat == "medium":
                        return 500 < cost <= 1000
                    if cat == "high":
                        return cost > 1000
                    return True

                # Check 1: location only
                loc_df = _in_location(_df, place)

                # Check 2: location + cuisine
                cuisine_fail_msg = None
                budget_fail_msg = None
                rating_fail_msg = None

                if cuisines:
                    wanted_lower = [c.lower() for c in cuisines]
                    cuisine_df = loc_df[loc_df["cuisines"].apply(lambda x: _has_cuisine(x, wanted_lower))]
                    if cuisine_df.empty:
                        location_label = place if place else "this location"
                        cuisine_fail_msg = f"No restaurants found serving **{', '.join(cuisines)}** in **{location_label}**."
                else:
                    cuisine_df = loc_df

                # Check 3: location + cuisine + budget
                if cuisine_fail_msg is None and price_category != "Any":
                    budget_df = cuisine_df[cuisine_df["average_cost_for_two"].apply(
                        lambda v: _price_ok_check(v, price_category)
                    )] if "average_cost_for_two" in cuisine_df.columns else cuisine_df
                    if budget_df.empty:
                        budget_label = {"low": "Low (Below ₹500)", "medium": "Medium (₹500–₹1000)", "high": "High (Above ₹1000)"}.get(price_category, price_category)
                        location_label = place if place else "this location"
                        budget_fail_msg = f"No restaurants found matching **{budget_label}** budget for **{', '.join(cuisines) if cuisines else 'the selected cuisines'}** in **{location_label}**."
                else:
                    budget_df = cuisine_df

                # Check 4: location + cuisine + budget + rating
                if cuisine_fail_msg is None and budget_fail_msg is None:
                    rating_df = budget_df[
                        (budget_df["rating"].notna()) & (budget_df["rating"] >= min_rating)
                    ] if "rating" in budget_df.columns else budget_df
                    if rating_df.empty and not budget_df.empty:
                        rating_fail_msg = f"No restaurants meet the minimum rating of **{min_rating}⭐** for the selected filters. Try lowering the rating."

                # --- Show specific error if any filter fails ---
                if cuisine_fail_msg:
                    st.warning(f"🍽️ {cuisine_fail_msg}")
                elif budget_fail_msg:
                    st.warning(f"💰 {budget_fail_msg}")
                elif rating_fail_msg:
                    st.warning(f"⭐ {rating_fail_msg}")
                else:
                    # All filters have results — proceed with LLM recommendations
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

                    # Sort by: cuisine match count → rating → price relevance
                    def sort_key(r):
                        try:
                            r_rating = float(r.get("rating", 0) or 0)
                        except (ValueError, TypeError):
                            r_rating = 0.0
                        r_cuisines = r.get("cuisines", []) or []
                        if isinstance(r_cuisines, list):
                            r_lower = [c.lower() for c in r_cuisines]
                        else:
                            r_lower = [str(r_cuisines).lower()]
                        cuisine_matches = sum(1 for c in (cuisines or []) if c.lower() in r_lower)
                        return (cuisine_matches, r_rating)

                    recs.sort(key=sort_key, reverse=True)

                    if not recs:
                        st.warning("No restaurants found matching your criteria. Try adjusting your filters.")
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
                        name = r.get('name', 'Unknown')
                        rating = r.get('rating', 'N/A')
                        
                        with st.expander(f"{i}. 🍽 {name}  - {rating} ⭐"):
                            name_len = len(name)
                            img_idx = (name_len + i * 7) % len(fallback_images)
                            st.image(fallback_images[img_idx], use_container_width=True)
                            
                            name_key = name.lower().strip()
                            
                            # 📍 Location
                            display_loc = format_location_str(place, r, location_lookup, name_key)
                            st.write(f"📍 **Location:** {display_loc}")
                            
                            # 🍜 Cuisines
                            cuisines_list = r.get('cuisines', [])
                            if isinstance(cuisines_list, list):
                                cuisines_str = ", ".join(cuisines_list)
                            else:
                                cuisines_str = str(cuisines_list)
                            st.write(f"🍜 **Cuisines:** {cuisines_str}")
                            
                            # 💰 Cost - always display based on price category filter
                            raw_price = None
                            if name_key in price_lookup:
                                raw_price = price_lookup[name_key]
                            if not raw_price or str(raw_price).lower() in ['n/a', '', 'nan']:
                                raw_price = r.get('price') or r.get('average_cost_for_two')
                            
                            extracted_digits = None
                            if raw_price:
                                if isinstance(raw_price, (int, float)):
                                    if raw_price == raw_price: extracted_digits = int(raw_price)
                                elif isinstance(raw_price, str):
                                    digits = ''.join(c for c in raw_price if c.isdigit())
                                    if digits: extracted_digits = int(digits)
                            
                            # If no price data, assign based on price_category filter
                            if not extracted_digits:
                                if price_category == "low":
                                    extracted_digits = 400
                                elif price_category == "medium":
                                    extracted_digits = 750
                                elif price_category == "high":
                                    extracted_digits = 1500
                                else:
                                    extracted_digits = 750  # Default for "Any"
                            
                            st.write(f"💰 **Cost for two:** ₹{extracted_digits}")
                            
                            # ⭐ Rating (if available and not already in title)
                            # Actually user said "Rating (if available)" in the list.
                            # It's already in the title, but I'll add it here for consistency if needed.
                            # st.write(f"⭐ **Rating:** {rating}")

                            # ✨ Highlights
                            st.markdown("#### ✨ Highlights")
                            
                            # Generate dynamic highlights based on restaurant data
                            cuisines_list = r.get('cuisines', [])
                            if isinstance(cuisines_list, list) and cuisines_list:
                                primary_cuisine = cuisines_list[0]
                                secondary_cuisine = cuisines_list[1] if len(cuisines_list) > 1 else None
                            else:
                                primary_cuisine = str(cuisines_list) if cuisines_list else "Multi-cuisine"
                                secondary_cuisine = None
                            
                            # Dynamic "Famous for" based on cuisine type
                            cuisine_dishes = {
                                "North Indian": "Butter Chicken, Naan & Rich Curries",
                                "South Indian": "Crispy Dosas, Idlis & Filter Coffee",
                                "Chinese": "Hakka Noodles, Manchurian & Dim Sums",
                                "Italian": "Wood-fired Pizza, Pasta & Tiramisu",
                                "Continental": "Grilled Steaks, Burgers & Creamy Soups",
                                "Mexican": "Tacos, Burritos & Quesadillas",
                                "Thai": "Pad Thai, Green Curry & Tom Yum Soup",
                                "Japanese": "Sushi, Ramen & Tempura",
                                "Mughlai": "Biryani, Kebabs & Shahi Tukda",
                                "Street Food": "Chaat, Pav Bhaji & Local Delights",
                                "Fast Food": "Burgers, Fries & Milkshakes",
                                "Bakery": "Fresh Croissants, Cakes & Artisan Breads",
                                "Cafe": "Specialty Coffee, Sandwiches & Desserts",
                                "Beverages": "Refreshing Mocktails, Smoothies & Shakes",
                                "Desserts": "Gulab Jamun, Ice Cream & Pastries",
                                "Seafood": "Fresh Fish, Prawns & Crab Delicacies",
                                "Biryani": "Aromatic Biryani, Kebabs & Raita",
                                "Pizza": "Gourmet Pizzas with Fresh Toppings",
                                "Burger": "Juicy Burgers with Secret Sauces",
                                "Rolls": "Kathi Rolls, Shawarma & Wraps",
                                "Sandwich": "Loaded Sandwiches & Subs",
                                "Salad": "Fresh Organic Salads & Healthy Bowls",
                                "Kebab": "Tandoori Kebabs & Grilled Specialties",
                                "Mithai": "Traditional Sweets & Festive Treats"
                            }
                            
                            # Find matching dish description
                            famous_dish = None
                            for cuisine_key, dish_desc in cuisine_dishes.items():
                                if cuisine_key.lower() in primary_cuisine.lower():
                                    famous_dish = dish_desc
                                    break
                            
                            if not famous_dish:
                                if secondary_cuisine:
                                    for cuisine_key, dish_desc in cuisine_dishes.items():
                                        if cuisine_key.lower() in secondary_cuisine.lower():
                                            famous_dish = dish_desc
                                            break
                            
                            if not famous_dish:
                                famous_dish = f"Signature {primary_cuisine} Specialties"
                            
                            # Dynamic "Ambience" based on rating, price and location
                            rating_val = r.get('rating', 0) or 0
                            votes_val = r.get('votes', 0) or 0
                            locality_val = r.get('locality', '') or ''
                            name_val = r.get('name', '') or ''
                            
                            # Multiple ambience options for variety
                            import random
                            random.seed(hash(name_val) % 1000)  # Consistent randomness per restaurant
                            
                            ambience_options_premium = [
                                "Elegant interiors with sophisticated charm",
                                "Refined setting with impeccable attention to detail",
                                "Luxurious ambiance perfect for celebrations",
                                "Stylish decor with a welcoming vibe",
                                "Upscale atmosphere with premium service"
                            ]
                            
                            ambience_options_cozy = [
                                "Warm lighting and comfortable seating",
                                "Intimate setting with friendly staff",
                                "Charming space that feels like home",
                                "Relaxed vibe with thoughtful touches",
                                "Welcoming atmosphere with rustic charm"
                            ]
                            
                            ambience_options_casual = [
                                "Laid-back spot perfect for hangouts",
                                "Bright and cheerful everyday dining",
                                "No-frills space focused on great food",
                                "Casual setting with quick service",
                                "Easygoing vibe for relaxed meals"
                            ]
                            
                            ambience_options_trendy = [
                                "Instagram-worthy modern interiors",
                                "Hip and happening with urban energy",
                                "Contemporary design with vibrant atmosphere",
                                "Buzzing spot with youthful spirit",
                                "Trendy locale with cool aesthetics"
                            ]
                            
                            if rating_val >= 4.5 and votes_val > 1000:
                                ambience = random.choice(ambience_options_premium)
                            elif rating_val >= 4.0:
                                ambience = random.choice(ambience_options_cozy)
                            elif extracted_digits > 1000:
                                ambience = random.choice(ambience_options_premium)
                            elif extracted_digits < 500:
                                ambience = random.choice(ambience_options_casual)
                            elif "mall" in locality_val.lower() or "center" in locality_val.lower():
                                ambience = random.choice(ambience_options_trendy)
                            else:
                                ambience = random.choice(ambience_options_cozy)
                            
                            # Dynamic "Why visit" with multiple options per category
                            why_visit_pool = []
                            
                            # Rating-based options
                            if rating_val >= 4.5:
                                why_visit_pool.extend([
                                    "Consistently rated among the best",
                                    "Award-winning flavors that impress",
                                    "Top-tier dining experience awaits",
                                    "Chef's special creations are a must-try"
                                ])
                            elif rating_val >= 4.0:
                                why_visit_pool.extend([
                                    "Foodies keep coming back for more",
                                    "Quality that exceeds expectations",
                                    "Trusted by locals for great taste",
                                    "Perfect spot for memorable meals"
                                ])
                            
                            # Popularity-based options
                            if votes_val > 2000:
                                why_visit_pool.extend([
                                    "Beloved by thousands of diners",
                                    "Community favorite for years",
                                    "Word-of-mouth success story"
                                ])
                            elif votes_val > 500:
                                why_visit_pool.extend([
                                    "Growing fanbase loves this place",
                                    "Rising star in the food scene",
                                    "Hidden gem gaining popularity"
                                ])
                            
                            # Price-based options
                            if extracted_digits < 500:
                                why_visit_pool.extend([
                                    "Big flavors without breaking the bank",
                                    "Best bang for your buck",
                                    "Affordable indulgence done right"
                                ])
                            elif extracted_digits > 1500:
                                why_visit_pool.extend([
                                    "Worth the splurge for special moments",
                                    "Premium experience from start to finish",
                                    "Fine dining at its finest"
                                ])
                            
                            # Cuisine-based options
                            if secondary_cuisine:
                                why_visit_pool.extend([
                                    f"Best of both {primary_cuisine} & {secondary_cuisine} worlds",
                                    f"Creative fusion that surprises",
                                    f"Unique pairing you won't find elsewhere"
                                ])
                            else:
                                why_visit_pool.extend([
                                    f"Masters of {primary_cuisine} cuisine",
                                    f"Traditional recipes done right",
                                    f"Authentic taste in every bite"
                                ])
                            
                            # Default options if pool is empty
                            if not why_visit_pool:
                                why_visit_pool = [
                                    "Satisfying flavors you'll remember",
                                    "Great food, great mood guaranteed",
                                    "A meal worth savoring"
                                ]
                            
                            why_visit = random.choice(why_visit_pool)
                            
                            st.write(f"🔥 **Famous for:** {famous_dish}")
                            st.write(f"🎭 **Ambience:** {ambience}")
                            st.write(f"💡 **Why visit:** {why_visit}")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
