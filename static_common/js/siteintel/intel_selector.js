/**
 * INTEL_SELECTOR_MODULE
 * Handles the site search and lookup logic on the selector page.
 */
export const IntelSelector = {
    init: function(inputId, resultsId) {
        const input = document.getElementById(inputId);
        const results = document.getElementById(resultsId);
        const form = document.getElementById('site-selector-form');

        if (!input || !results) return;

        const lookupUrl = input.dataset.lookupUrl;
        let timeout = null;

        const executeSearch = (immediate = false) => {
            clearTimeout(timeout);
            const query = input.value.trim();
            
            if (query.length < 2) {
                results.innerHTML = '';
                return;
            }

            if (immediate) {
                this.performLookup(query, lookupUrl, results);
            } else {
                timeout = setTimeout(() => {
                    this.performLookup(query, lookupUrl, results);
                }, 300);
            }
        };

        // 1. Live Search (Debounced)
        input.addEventListener('input', () => executeSearch(false));

        // 2. Form Submission (Enter Key fallback)
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                executeSearch(true);
            });
        }

        // 3. Enter Key (Force Immediate)
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                executeSearch(true);
            }
        });

        console.log("INTEL_SELECTOR_INITIALIZED");
    },

    performLookup: function(query, url, resultsContainer) {
        resultsContainer.innerHTML = '<div class="text-center text-primary mono py-3">[ SCANNING_STREAMS... ]</div>';

        fetch(`${url}?q=${encodeURIComponent(query)}`)
            .then(response => {
                if (!response.ok) throw new Error('NETWORK_RESPONSE_NOT_OK');
                return response.json();
            })
            .then(data => {
                resultsContainer.innerHTML = '';
                if (data.results && data.results.length > 0) {
                    data.results.forEach(site => {
                        const item = document.createElement('div');
                        item.className = 'selector-item p-3 mb-2 border border-secondary bg-dark-custom mono';
                        item.style.cursor = 'pointer';
                        item.innerHTML = `
                            <div class="text-primary fw-bold">#${site.store_num || ''} ${site.name}</div>
                            <div class="small text-muted-custom">${site.city} [CLICK_TO_ACQUIRE]</div>
                        `;
                        item.addEventListener('click', () => {
                            if (site.has_location) {
                                window.location.href = `/siteintel/site/${site.id}/`;
                            } else {
                                window.location.href = `/siteintel/init-location/${site.store_pk}/`;
                            }
                        });
                        resultsContainer.appendChild(item);
                    });
                } else {
                    resultsContainer.innerHTML = '<div class="text-center text-muted-custom mono py-3">[ NO_MATCHES_FOUND ]</div>';
                }
            })
            .catch(err => {
                console.error("SELECTOR_ERROR:", err);
                resultsContainer.innerHTML = '<div class="text-center text-danger mono py-3">[ SEARCH_FAILED ]</div>';
            });
    }
};
