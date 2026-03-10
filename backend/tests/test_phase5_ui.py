"""Phase 5 tests."""
import os
import sys

# Ensure streamit app can find the modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamlit.testing.v1 import AppTest

def test_phase5_ui_renders_and_responds():
    """Test that the Phase 5 Streamlit UI resolves and basic elements are present."""
    app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "streamlit_app", "app.py")
    
    at = AppTest.from_file(app_path)
    at.run(timeout=15)

    # The app should start without exceptions
    assert not at.exception
    
    # Check title
    assert at.title[0].value == "🍽️ AI Restaurant Recommender"
    
    # Check sidebar elements
    assert len(at.selectbox) >= 1
    assert "Place / City" in at.selectbox[0].label
    assert len(at.multiselect) >= 1
    assert "Cuisines" in at.multiselect[0].label
    
    # Click the button
    at.button[0].click().run(timeout=15)
    
    # Wait for the spinner and button execution
    # Depending on internet connection or API keys, it might fail or show "No restaurants found" or an error.
    # We mainly check that it didn't crash unexpectedly
    # If the API key is not set, it might show "An error occurred".
    
    # Since we didn't mock the groq API call, we just ensure no unhandled exceptions crashed the app.
    assert not at.exception
