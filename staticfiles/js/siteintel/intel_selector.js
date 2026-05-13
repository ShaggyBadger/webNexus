/**
 * INTEL_SELECTOR_MODULE
 * Handles high-speed site search and target acquisition logic.
 * Optimized for field use with both live-scan (debounced) and immediate execution.
 */
export const IntelSelector = {
    /**
     * Initializes the selector interface.
     * @param {string} inputId - ID of the text input for store numbers.
     * @param {string} resultsId - ID of the container where results will be rendered.
     */
    init: function(inputId, resultsId) {
        console.log("INTEL_SELECTOR: Initializing target acquisition system...");
        
        const input = document.getElementById(inputId);
        const results = document.getElementById(resultsId);
        const form = document.getElementById('site-selector-form');
        const searchButton = document.getElementById('search-button');
        const proximityBtn = document.getElementById('proximity-scan-button');
        const proximityStatus = document.getElementById('proximity-status');

        if (!input || !results) {
            console.error("INTEL_SELECTOR_ERROR: Critical UI components missing (input/results).");
            return;
        }

        const lookupUrl = input.dataset.lookupUrl;
        const proximityUrl = form ? form.dataset.proximityUrl : null;
        let timeout = null;

        /**
         * Orchestrates the search request with optional debounce.
         * @param {boolean} immediate - If true, bypasses the debounce timeout for instant execution.
         */
        const executeSearch = (immediate = false) => {
            clearTimeout(timeout);
            const query = input.value.trim();
            
            // TACTICAL: Minimum 2 characters required to prevent database flooding
            if (query.length < 2) {
                results.innerHTML = '';
                return;
            }

            if (immediate) {
                console.log(`INTEL_SELECTOR: Executing immediate scan for ID [${query}]`);
                this.performLookup(query, lookupUrl, results);
            } else {
                // TACTICAL: 300ms debounce for smoother "as-you-type" experience
                timeout = setTimeout(() => {
                    console.log(`INTEL_SELECTOR: Executing debounced scan for ID [${query}]`);
                    this.performLookup(query, lookupUrl, results);
                }, 300);
            }
        };

        // 1. LIVE_SCAN: Triggers as the agent types
        input.addEventListener('input', () => {
            executeSearch(false);
        });

        // 2. FORM_SUBMISSION: Handles 'Enter' key and button clicks inside form
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault(); // Stop page refresh
                executeSearch(true);
            });
        }

        // 3. MANUAL_OVERRIDE: Physical search button click
        if (searchButton) {
            searchButton.addEventListener('click', (e) => {
                e.preventDefault();
                executeSearch(true);
            });
        }

        // 4. KEYBOARD_HOTKEY: Force immediate search on 'Enter' (Redundant safeguard)
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                executeSearch(true);
            }
        });

        // 5. PROXIMITY_SCAN: GPS-based site acquisition
        if (proximityBtn && proximityUrl) {
            proximityBtn.addEventListener('click', () => {
                this.scanNearbyStores(proximityUrl, results, proximityStatus);
            });
        }

        console.log("INTEL_SELECTOR: System ready. Awaiting target ID.");
    },

    /**
     * Communicates with the API to retrieve site intelligence.
     * @param {string} query - The store/riso ID to search for.
     * @param {string} url - API endpoint URL.
     * @param {HTMLElement} resultsContainer - DOM element for rendering results.
     */
    performLookup: function(query, url, resultsContainer) {
        // Show scanning state to provide feedback on slow connections
        resultsContainer.innerHTML = '<div class="text-center text-primary mono py-3">[ SCANNING_STREAMS... ]</div>';

        fetch(`${url}?q=${encodeURIComponent(query)}`)
            .then(response => {
                if (!response.ok) throw new Error(`API_RESPONSE_ERROR: ${response.status}`);
                return response.json();
            })
            .then(data => {
                resultsContainer.innerHTML = '';
                if (data.results && data.results.length > 0) {
                    this.renderResults(data.results, resultsContainer);
                } else {
                    console.warn(`INTEL_SELECTOR: No matches found for ID [${query}]`);
                    resultsContainer.innerHTML = `
                        <div class="text-center py-3">
                            <div class="text-muted-custom mono mb-3">[ NO_MATCHES_FOUND ]</div>
                            <div class="d-grid">
                                <a href="/siteintel/propose/?store_num=${encodeURIComponent(query)}" class="btn btn-outline-primary btn-sm mono">
                                    [ INITIATE PROPOSAL FOR #${query} ]
                                </a>
                            </div>
                        </div>
                    `;
                }
            })
            .catch(err => {
                console.error("INTEL_SELECTOR_CRITICAL_FAILURE:", err);
                resultsContainer.innerHTML = '<div class="text-center text-danger mono py-3">[ SCAN_FAILED: LINK_ERROR ]</div>';
            });
    },

    /**
     * Acquires user GPS coordinates and searches for nearby stores.
     */
    scanNearbyStores: function(url, resultsContainer, statusElement) {
        if (!navigator.geolocation) {
            console.error("INTEL_SELECTOR: Geolocation not supported.");
            alert("GEOLOCATION_NOT_SUPPORTED");
            return;
        }

        statusElement.classList.remove('d-none');
        statusElement.innerText = "ACQUIRING GPS LOCK...";
        resultsContainer.innerHTML = '<div class="text-center text-primary mono py-3">[ INITIALIZING_GPS_SCAN... ]</div>';

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;
                statusElement.innerText = `LOCK_ACQUIRED: ${lat.toFixed(4)}, ${lon.toFixed(4)}`;

                fetch(`${url}?lat=${lat}&lon=${lon}`)
                    .then(response => response.json())
                    .then(data => {
                        resultsContainer.innerHTML = '';
                        if (data.results && data.results.length > 0) {
                            this.renderResults(data.results, resultsContainer, true);
                        } else {
                            resultsContainer.innerHTML = '<div class="text-center text-muted-custom mono py-3">[ NO_STORES_IN_RANGE ]</div>';
                        }
                    })
                    .catch(err => {
                        console.error("INTEL_SELECTOR: Proximity scan failed.", err);
                        resultsContainer.innerHTML = '<div class="text-center text-danger mono py-3">[ SCAN_FAILED: LINK_ERROR ]</div>';
                    })
                    .finally(() => {
                        setTimeout(() => statusElement.classList.add('d-none'), 3000);
                    });
            },
            (error) => {
                console.error("INTEL_SELECTOR: GPS acquisition failed.", error);
                statusElement.innerText = "GPS_ERROR: PERMISSION_DENIED";
                resultsContainer.innerHTML = '<div class="text-center text-danger mono py-3">[ GPS_LOCK_FAILED ]</div>';
                setTimeout(() => statusElement.classList.add('d-none'), 3000);
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    },

    /**
     * Renders result cards into the container.
     */
    renderResults: function(results, container, showDistance = false) {
        console.log(`INTEL_SELECTOR: Rendering ${results.length} targets.`);
        results.forEach(site => {
            const item = document.createElement('div');
            item.className = 'selector-item p-3 mb-2 border border-secondary bg-dark-custom mono';
            item.style.cursor = 'pointer';
            
            const distanceMarkup = showDistance ? `<div class="badge bg-primary text-dark float-end">${site.distance_display}</div>` : '';

            // TACTICAL: High-contrast result card
            item.innerHTML = `
                ${distanceMarkup}
                <div class="text-primary fw-bold">#${site.store_num || ''} ${site.store_name || site.name}</div>
                <div class="small text-muted-custom">${site.city} [CLICK_TO_ACQUIRE]</div>
            `;
            
            item.addEventListener('click', () => {
                console.log(`INTEL_SELECTOR: Target Acquired - Store #${site.store_num}`);
                if (site.has_location) {
                    const id = site.location_id || site.id;
                    window.location.href = `/siteintel/site/${id}/`;
                } else {
                    // TACTICAL: Auto-initialize location if it doesn't exist yet
                    const pk = site.store_pk || site.id;
                    window.location.href = `/siteintel/init-location/${pk}/`;
                }
            });
            container.appendChild(item);
        });
    }
};
