/**
 * INTEL_MAIN_ORCHESTRATOR
 * Entry point for Site Intelligence JavaScript logic.
 * Coordinates modular initialization based on page context.
 */
import { IntelMap } from './intel_map.js';
import { IntelNotes } from './intel_notes.js';
import { IntelSelector } from './intel_selector.js';
import { IntelMapDraw } from './intel_map_draw.js';
import { IntelMarkdown } from './intel_markdown.js';

document.addEventListener('DOMContentLoaded', () => {
    // 1. Intelligence Detail Page Initialization
    if (document.getElementById('intel-map')) {
        IntelMap.init('intel-map');
        IntelNotes.init();
    }

    // 2. Map Drawing Interface (Phase 2b)
    if (document.getElementById('map-edit-canvas')) {
        const map = IntelMap.init('map-edit-canvas');
        const hiddenField = 'id_geojson_data';
        const initialData = document.getElementById('map-edit-canvas').dataset.overlay;
        IntelMapDraw.init(map, hiddenField, initialData);
    }

    // 3. Markdown Toolbar for Intel Reports
    if (document.getElementById('intel-md-toolbar')) {
        const textarea = document.querySelector('textarea');
        if (textarea) {
            if (!textarea.id) {
                textarea.id = 'site-intel-notes-textarea';
            }
            IntelMarkdown.init(textarea.id, 'intel-md-toolbar');
        }
    }

    // 4. Site Selector Page Initialization
    if (document.getElementById('site-lookup-input')) {
        IntelSelector.init('site-lookup-input', 'site-lookup-results');
    }

    console.log("INTEL_SYSTEM_INITIALIZED");
});
