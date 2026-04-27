/**
 * TACTICAL_MAP_MODULE
 * Handles Leaflet map initialization, tile layer management, and marker placement.
 * Optimized for dynamic switching between high-contrast tactical modes.
 */
import { IntelMapOverlay } from './intel_map_overlay.js';

export const IntelMap = {
    /**
     * Factory for creating tile layers based on operational requirements.
     * @param {string} preference - 'STANDARD' (OSM) or 'DARK' (CartoDB).
     * @param {object} L - The Leaflet library instance.
     * @returns {L.TileLayer}
     */
    createTileLayer: function(preference, L) {
        if (preference === 'DARK') {
            console.log("MAP_ENGINE: Generating Dark-Matter tactical layer.");
            return L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '© OpenStreetMap contributors © CARTO',
                subdomains: 'abcd',
                maxZoom: 20
            });
        }
        
        console.log("MAP_ENGINE: Generating Standard-OSM tactical layer.");
        return L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        });
    },

    /**
     * Initializes a map instance within a specified container.
     * @param {string} containerId - DOM ID of the map container.
     * @returns {object|null} - Controller object containing map instance and mode-switch methods.
     */
    init: function(containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.warn(`MAP_ENGINE_ABORT: Container [${containerId}] not found in DOM.`);
            return null;
        }

        // TACTICAL: Extract geospatial coordinates from dataset
        const lat = parseFloat(container.dataset.lat);
        const lon = parseFloat(container.dataset.lon);
        const siteName = container.dataset.siteName || "SELECTED_TARGET";
        const overlayData = container.dataset.overlay || "";

        if (isNaN(lat) || isNaN(lon)) {
            console.error("MAP_ENGINE_ERROR: Invalid or missing coordinates in dataset.");
            container.innerHTML = '<div class="alert alert-danger mono m-0">COORDINATE_ERROR: NO_VALID_GEOSPATIAL_DATA</div>';
            return null;
        }

        console.log(`MAP_ENGINE: Initializing target at [${lat}, ${lon}]`);

        // Initialize Leaflet Map Instance
        const map = L.map(containerId).setView([lat, lon], 13);

        // Determine Initial Preference (Profile-driven)
        const initialPref = document.querySelector('meta[name="user-map-preference"]')?.content || 'STANDARD';
        let currentTileLayer = this.createTileLayer(initialPref, L).addTo(map);

        // Define Tactical Marker Style
        const tacticalIcon = L.divIcon({
            className: 'tactical-marker',
            html: '<div style="background-color: #ffb86c; width: 12px; height: 12px; border: 2px solid #000; border-radius: 50%;"></div>',
            iconSize: [12, 12],
            iconAnchor: [6, 6]
        });

        // Plot Primary Target
        L.marker([lat, lon], {icon: tacticalIcon})
            .addTo(map)
            .bindPopup(`<span class="mono">TARGET: ${siteName}</span>`)
            .openPopup();
            
        // Render Tactical Overlays (Phase 2b Drawings)
        try {
            IntelMapOverlay.render(map, overlayData);
        } catch (err) {
            console.error("MAP_ENGINE_OVERLAY_ERROR:", err);
        }
            
        console.log(`MAP_ENGINE: Deployment successful for Site [${siteName}]`);

        /**
         * Returns core controller for dynamic view manipulation.
         */
        return {
            instance: map,
            tileLayer: currentTileLayer,
            /**
             * Hot-swaps the tile layer without refreshing the map instance.
             * @param {string} mode - 'STANDARD' or 'DARK'
             */
            setMode: (mode) => {
                console.log(`MAP_ENGINE: Switching to [${mode}] mode.`);
                if (currentTileLayer) map.removeLayer(currentTileLayer);
                currentTileLayer = this.createTileLayer(mode, L).addTo(map);
                return currentTileLayer;
            }
        };
    }
};
