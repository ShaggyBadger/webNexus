/**
 * INTEL_SELECTOR_MODULE
 * Handles the site search and lookup logic on the selector page.
 */
export const IntelSelector = {
    init: function(inputId, resultsId) {
        const input = document.getElementById(inputId);
        const results = document.getElementById(resultsId);
        if (!input || !results) return;

        const lookupUrl = input.dataset.lookupUrl;
        let timeout = null;

        input.addEventListener('input', (e) => {
            clearTimeout(timeout);
            const query = e.target.value.trim();
            
            if (query.length < 2) {
                results.innerHTML = '';
                return;
            }

            timeout = setTimeout(() => {
                this.performLookup(query, lookupUrl, results);
            }, 300);
        });
        
        console.log("INTEL_SELECTOR_READY");
    },

    performLookup: function(query, url, resultsContainer) {
        fetch(`${url}?q=${encodeURIComponent(query)}`)
            .then(response => response.json())
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
                                // Redirect to a view that ensures location exists before showing intel
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
            });
    }
};
