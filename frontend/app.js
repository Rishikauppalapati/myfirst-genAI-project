// Automatically use relative /api in production, and localhost:8000 in dev
const API_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000/api'
    : '/api';

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const minRatingInput = document.getElementById('min_rating');
    const ratingValDisplay = document.getElementById('rating-val');
    const form = document.getElementById('recommend-form');

    const resultsSection = document.getElementById('results-section');
    const resultsHeader = document.getElementById('results-header');
    const explanationText = document.getElementById('explanation-text');
    const loadingState = document.getElementById('loading-state');
    const errorState = document.getElementById('error-state');
    const errorMessage = document.getElementById('errorMessage');
    const recommendationsGrid = document.getElementById('recommendations-grid');

    // Update rating display when slider moves
    minRatingInput.addEventListener('input', (e) => {
        ratingValDisplay.textContent = parseFloat(e.target.value).toFixed(1);
    });

    // Fetch initial options for dropdowns
    async function fetchOptions() {
        try {
            const response = await fetch(`${API_URL}/options`);
            if (!response.ok) throw new Error('Failed to fetch options');

            const data = await response.json();

            // Populate places
            const placeSelect = document.getElementById('place');
            placeSelect.innerHTML = '<option value="">Any Place</option>';
            data.places.forEach(place => {
                const option = document.createElement('option');
                option.value = place;
                option.textContent = place;
                placeSelect.appendChild(option);
            });

            // Populate cuisines
            const cuisineSelect = document.getElementById('cuisines');
            cuisineSelect.innerHTML = '<option value="">Any Cuisine</option>';
            data.cuisines.forEach(cuisine => {
                const option = document.createElement('option');
                option.value = cuisine;
                option.textContent = cuisine;
                cuisineSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Error fetching options:', error);
            document.getElementById('place').innerHTML = '<option value="">Error loading places</option>';
            document.getElementById('cuisines').innerHTML = '<option value="">Error loading cuisines</option>';
        }
    }

    // Call initially
    fetchOptions();

    // Helper to format ratings
    function getRatingClass(rating) {
        if (!rating) return 'okay';
        if (rating >= 4.5) return 'excellent';
        if (rating >= 4.0) return 'good';
        if (rating >= 3.0) return 'okay';
        return 'poor';
    }

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Get form values
        const place = document.getElementById('place').value;

        // Collect multiple cuisines
        const cuisineSelect = document.getElementById('cuisines');
        const selectedCuisines = Array.from(cuisineSelect.selectedOptions)
            .map(opt => opt.value)
            .filter(val => val !== "");

        const priceCategory = document.getElementById('price_category').value;
        const minRating = parseFloat(document.getElementById('min_rating').value);

        // Prepare request body
        const reqBody = {
            place: place,
            cuisines: selectedCuisines,
            price_category: priceCategory,
            min_rating: minRating,
            top_k: 6 // Ask for 6 recommendations to fill a 3-column grid nicely
        };

        // UI States
        resultsHeader.style.display = 'none';
        errorState.style.display = 'none';
        recommendationsGrid.innerHTML = '';
        loadingState.style.display = 'flex';

        // Scroll to results section smoothly
        resultsSection.scrollIntoView({ behavior: 'smooth' });

        try {
            const response = await fetch(`${API_URL}/recommend`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(reqBody)
            });

            if (!response.ok) {
                let errorMsg = 'Network response was not ok';
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.detail || errorData.message || errorMsg;
                } catch (e) { }
                throw new Error(errorMsg);
            }

            const data = await response.json();

            // Hide loading
            loadingState.style.display = 'none';

            if (!data.recommendations || data.recommendations.length === 0) {
                // Show error state gracefully
                document.getElementById('error-message').textContent = data.explanation || "No recommendations found. Try relaxing your filters.";
                errorState.style.display = 'flex';
                return;
            }

            // Show results
            resultsHeader.style.display = 'block';

            // Render cards
            data.recommendations.forEach(rec => {
                const card = document.createElement('div');
                card.className = 'card';

                const ratingValue = rec.rating ? parseFloat(rec.rating).toFixed(1) : 'N/A';
                const ratingClass = getRatingClass(rec.rating);

                let reasonsHtml = '';
                if (rec.why_recommended) {
                    reasonsHtml = `<div class="card-reasons">
                        <h4>Why Recommended</h4>
                        <ul>`;

                    if (Array.isArray(rec.why_recommended)) {
                        rec.why_recommended.forEach(reason => {
                            reasonsHtml += `<li>${reason}</li>`;
                        });
                    } else {
                        reasonsHtml += `<li>${rec.why_recommended}</li>`;
                    }
                    reasonsHtml += `</ul></div>`;
                }

                let considerIfHtml = '';
                if (rec.consider_if) {
                    considerIfHtml = `<div class="consider-if"><strong>Consider If:</strong> ${rec.consider_if}</div>`;
                }

                const cuisinesList = Array.isArray(rec.cuisines) ? rec.cuisines.join(', ') : (rec.cuisines || 'N/A');

                let summaryHtml = '';
                if (rec.summary) {
                    summaryHtml = `<div class="detail-row" style="margin-top: 10px; flex-direction: column;">
                        <span class="detail-label" style="margin-bottom: 5px;">Overview:</span>
                        <span class="detail-value" style="font-size: 0.9rem;">${rec.summary}</span>
                    </div>`;
                }

                // Curated high-quality food and restaurant images for reliable fallbacks
                const fallbackImages = [
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
                ];

                // Deterministically pick an image based on the restaurant name length + index to simulate randomness without repeating across all cards
                const nameLength = rec.name ? rec.name.length : Math.floor(Math.random() * 10);
                const randomId = (nameLength + Math.floor(Math.random() * 100)) % fallbackImages.length;
                const imageUrl = fallbackImages[randomId];

                // Deduplicate Place string (e.g., "Church Street, Church Street")
                let displayPlace = rec.place || reqBody.place || 'N/A';
                if (displayPlace !== 'N/A') {
                    const placeParts = displayPlace.split(',').map(p => p.trim());
                    let uniqueParts = [...new Set(placeParts)];

                    // If we only have one part (e.g. "Church Street") and it's not the requested city 
                    // AND we have a requested city, append it!
                    if (uniqueParts.length === 1 && reqBody.place && uniqueParts[0].toLowerCase() !== reqBody.place.toLowerCase()) {
                        uniqueParts.push(reqBody.place);
                    }

                    displayPlace = uniqueParts.join(', ');
                }

                card.innerHTML = `
                    <img src="${imageUrl}" alt="${rec.name || 'Restaurant Image'}" class="card-img-placeholder" onerror="this.src='https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=400&q=80'">
                    <div class="card-header">
                        <h3 class="card-title">${rec.name || 'Unknown'}</h3>
                        <span class="rating-badge ${ratingClass}">${ratingValue} ⭐</span>
                    </div>
                    <div class="card-body">
                        <div class="detail-row">
                            <span class="detail-label">City:</span>
                            <span class="detail-value">${displayPlace}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Cuisines:</span>
                            <span class="detail-value">${cuisinesList}</span>
                        </div>
                        ${summaryHtml}
                        ${reasonsHtml}
                        ${considerIfHtml}
                    </div>
                `;

                recommendationsGrid.appendChild(card);
            });

        } catch (error) {
            console.error('Error fetching recommendations:', error);
            loadingState.style.display = 'none';

            let displayMsg = error.message;
            if (displayMsg.toLowerCase().includes('fetch')) {
                displayMsg = 'Failed to connect to the backend API. Please make sure the FastAPI server is running with `uvicorn backend.main:app`';
            }

            document.getElementById('error-message').textContent = displayMsg || 'An error occurred while fetching recommendations. Please try again.';
            errorState.style.display = 'flex';
        }
    });
});
