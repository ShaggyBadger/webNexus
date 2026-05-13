/**
 * INTEL_NOTES_MODULE
 * Handles UI interactions for field intelligence notes, including layer switching.
 */
export const IntelNotes = {
    /**
     * Initializes the intelligence layer toggle and state management.
     */
    init: function() {
        console.log("INTEL_NOTES: Initializing dual-layer intelligence system...");
        
        const selector = document.getElementById('intel-layer-selector');
        const personalContainer = document.getElementById('intel-personal-container');
        const sharedContainer = document.getElementById('intel-shared-container');
        const hintDisplay = document.getElementById('intel-layer-hint');

        if (!selector || !personalContainer || !sharedContainer || !hintDisplay) {
            console.log("INTEL_NOTES: Layer selector or containers missing (likely anonymous access).");
            return;
        }

        // TACTICAL: Map mode to status text
        const hints = {
            'PERSONAL': '* YOU ARE VIEWING YOUR PRIVATE OBSERVATIONS.',
            'DEFAULT': '* VIEWING SHARED LAYER. CREATE YOUR OWN TO OVERRIDE.'
        };

        /**
         * Switches the visible data layer based on selector state.
         * @param {string} layer - 'PERSONAL' or 'DEFAULT'
         */
        const switchLayer = (layer) => {
            console.log(`INTEL_NOTES: Switching tactical layer to [${layer}]`);
            
            if (layer === 'PERSONAL') {
                personalContainer.classList.remove('d-none');
                sharedContainer.classList.add('d-none');
                hintDisplay.innerText = hints.PERSONAL;
            } else {
                sharedContainer.classList.remove('d-none');
                personalContainer.classList.add('d-none');
                hintDisplay.innerText = hints.DEFAULT;
            }
        };

        // Initialize event listener for manual override
        selector.addEventListener('change', (e) => {
            switchLayer(e.target.value);
        });

        console.log("INTEL_NOTES: System ready. Dual-layer sync active.");
    }
};
