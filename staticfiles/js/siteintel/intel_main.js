/**
 * INTEL_MAIN_ORCHESTRATOR
 * Entry point for Site Intelligence JavaScript logic.
 * Coordinates modular initialization based on page context with safety safeguards.
 */
import { IntelMap } from './intel_map.js';
import { IntelNotes } from './intel_notes.js';
import { IntelSelector } from './intel_selector.js';
import { IntelMapDraw } from './intel_map_draw.js';
import { IntelMarkdown } from './intel_markdown.js';

document.addEventListener('DOMContentLoaded', () => {
    console.log("INTEL_SYSTEM: Initiating tactical boot sequence...");

    /**
     * Helper to safely initialize modules without blocking others.
     * Ensures a failure in one module doesn't crash the entire system.
     * @param {string} selector - The DOM element ID required for the module.
     * @param {function} initFn - The initialization logic to execute.
     */
    const safelyInit = (selector, initFn) => {
        if (document.getElementById(selector)) {
            try {
                console.log(`INTEL_SYSTEM: Initializing component [${selector}]...`);
                initFn();
            } catch (err) {
                console.error(`INTEL_SYSTEM_BOOT_ERROR [${selector}]:`, err);
            }
        }
    };

    // 1. SITE_DETAIL: Map and Field Notes
    safelyInit('intel-map', () => {
        const mapController = IntelMap.init('intel-map');
        IntelNotes.init();

        // TACTICAL: Map Mode Overrides (STD / DARK)
        // Allows agents to override their profile preference for the current view.
        const btnStd = document.getElementById('btn-map-standard');
        const btnDark = document.getElementById('btn-map-dark');

        if (btnStd && btnDark && mapController) {
            // Synchronize button state with active profile preference
            const pref = document.querySelector('meta[name="user-map-preference"]')?.content || 'STANDARD';
            console.log(`INTEL_SYSTEM: Applying initial map preference [${pref}]`);
            
            if (pref === 'DARK') {
                btnDark.classList.add('active');
                btnStd.classList.remove('active');
            } else {
                btnStd.classList.add('active');
                btnDark.classList.remove('active');
            }

            btnStd.addEventListener('click', () => {
                console.log("INTEL_SYSTEM: Manually overriding map to STANDARD mode.");
                mapController.setMode('STANDARD');
                btnStd.classList.add('active');
                btnDark.classList.remove('active');
            });

            btnDark.addEventListener('click', () => {
                console.log("INTEL_SYSTEM: Manually overriding map to DARK mode.");
                mapController.setMode('DARK');
                btnDark.classList.add('active');
                btnStd.classList.remove('active');
            });
        }
    });

    // 2. MAP_EDITOR: Tactical Overlay Tools
    safelyInit('map-edit-canvas', () => {
        const mapObj = IntelMap.init('map-edit-canvas');
        const map = mapObj ? mapObj.instance : null;
        if (!map) {
            console.error("INTEL_SYSTEM: Failed to acquire map instance for drawing tools.");
            return;
        }

        const hiddenField = 'id_geojson_data';
        const initialData = document.getElementById('map-edit-canvas').dataset.overlay;
        IntelMapDraw.init(map, hiddenField, initialData);
        console.log("INTEL_SYSTEM: Drawing canvas synchronized.");
    });

    // 3. INTEL_REPORT: Markdown Toolbar Integration
    safelyInit('intel-md-toolbar', () => {
        const textarea = document.querySelector('textarea');
        if (textarea) {
            if (!textarea.id) {
                textarea.id = 'site-intel-notes-textarea';
                console.warn("INTEL_SYSTEM: Textarea ID missing. Dynamic assignment successful.");
            }
            IntelMarkdown.init(textarea.id, 'intel-md-toolbar');
            console.log("INTEL_SYSTEM: Markdown engine active.");
        } else {
            console.error("INTEL_SYSTEM: Markdown toolbar found but no target textarea detected.");
        }
    });

    // 4. SITE_SELECTOR: Target Acquisition Interface
    safelyInit('site-lookup-input', () => {
        IntelSelector.init('site-lookup-input', 'site-lookup-results');
    });

    console.log("INTEL_SYSTEM: Operational. All tactical layers synchronized.");
});
