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
    const loadingState = document.getElementById('loading-state');
    const errorState = document.getElementById('error-state');
    const errorMessage = document.getElementById('error-message');
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
            placeSelect.innerHTML = '<option value="">Any Location</option>';
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

            // Initialize Choices.js
            if (window.Choices) {
                if (window.cuisinesChoices) window.cuisinesChoices.destroy();
                window.cuisinesChoices = new Choices(cuisineSelect, {
                    removeItemButton: true,
                    placeholder: true,
                    placeholderValue: 'Select cuisines...',
                    searchEnabled: true,
                    itemSelectText: '',
                    shouldSort: true
                });
            }
        } catch (error) {
            console.error('Error fetching options:', error);
        }
    }

    fetchOptions();

    // Helper to pick a relevant image based on cuisines and name
    function getRestaurantImage(cuisines, name) {
        const fallbackImages = [
            'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=400&q=80',
            'https://images.unsplash.com/photo-1552566626-52f8b828add9?w=400&q=80',
            'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=400&q=80',
            'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=400&q=80',
            'https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=400&q=80'
        ];
        const hash = (name || '').length + (cuisines || '').length;
        return fallbackImages[hash % fallbackImages.length];
    }

    const renderCard = (res) => {
        const cuisines = Array.isArray(res.cuisines) ? res.cuisines.join(', ') : (res.cuisines || 'N/A');
        const costValue = res.average_cost_for_two;
        const cost = costValue ? `₹${costValue.toLocaleString('en-IN')}` : '₹ N/A';
        const rating = res.rating ? parseFloat(res.rating).toFixed(1) : 'N/A';
        const location = res.locality ? `${res.locality}, ${res.city}` : (res.city || 'N/A');
        const img = getRestaurantImage(cuisines, res.name);

        return `
            <div class="card">
                <div class="card-image" style="background-image: url('${img}')">
                    <div class="card-rating">★ ${rating}</div>
                </div>
                <div class="card-body">
                    <h3 class="card-title">${res.name || 'Restaurant'}</h3>
                    <div class="detail-row price-row" style="margin-bottom: 15px;">
                        <span class="detail-label">Cost for Two:</span>
                        <span class="detail-value" style="font-weight: 700; color: var(--primary-color); font-size: 1.1rem;">${cost}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Location:</span>
                        <span class="detail-value">${location}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-label">Cuisines:</span>
                        <span class="detail-value">${cuisines}</span>
                    </div>
                    <p class="card-overview">${res.summary || ''}</p>
                </div>
            </div>
        `;
    };

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const place = document.getElementById('place').value;
        const cuisineSelect = document.getElementById('cuisines');
        const selectedCuisines = Array.from(cuisineSelect.selectedOptions)
            .map(opt => opt.value)
            .filter(val => val !== "");

        const priceCategory = document.getElementById('price_category').value;
        const minRating = parseFloat(document.getElementById('min_rating').value);

        const reqBody = {
            place: place,
            cuisines: selectedCuisines,
            price_category: priceCategory,
            min_rating: minRating,
            top_k: 9
        };

        resultsHeader.style.display = 'none';
        errorState.style.display = 'none';
        recommendationsGrid.innerHTML = '';
        loadingState.style.display = 'flex';

        resultsSection.scrollIntoView({ behavior: 'smooth' });

        try {
            const response = await fetch(`${API_URL}/recommend`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(reqBody)
            });

            if (!response.ok) throw new Error('Failed to fetch recommendations');

            const data = await response.json();
            loadingState.style.display = 'none';

            if (!data.recommendations || data.recommendations.length === 0) {
                errorMessage.textContent = data.explanation || "No recommendations found. Try adjusting your filters.";
                errorState.style.display = 'flex';
                return;
            }

            resultsHeader.style.display = 'block';

            const strict = data.recommendations.filter(r => !r.is_nearby);
            const nearby = data.recommendations.filter(r => r.is_nearby);

            // Add strict results
            strict.forEach(r => {
                recommendationsGrid.innerHTML += renderCard(r);
            });

            // Add nearby results with header
            if (nearby.length > 0) {
                const header = document.createElement('div');
                header.className = 'nearby-header';
                header.innerHTML = `<h3>Nearby Recommendations</h3>`;
                header.style.cssText = "width:100%; grid-column:1/-1; margin-top:3rem; padding-top:2rem; border-top:1px solid #eee; margin-bottom: 1.5rem;";
                recommendationsGrid.appendChild(header);

                nearby.forEach(r => {
                    recommendationsGrid.innerHTML += renderCard(r);
                });
            }

        } catch (err) {
            console.error(err);
            loadingState.style.display = 'none';
            errorMessage.textContent = "Oops! Something went wrong. Please check your connection and try again.";
            errorState.style.display = 'flex';
        }
    });
});
