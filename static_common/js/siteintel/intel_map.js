/**
 * TACTICAL_MAP_MODULE
 * Handles Leaflet map initialization and marker placement for site intelligence.
 */
import { IntelMapOverlay } from './intel_map_overlay.js';

export const IntelMap = {
    init: function(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const lat = parseFloat(container.dataset.lat);
        const lon = parseFloat(container.dataset.lon);
        const siteName = container.dataset.siteName || "SELECTED_TARGET";
        const overlayData = container.dataset.overlay || "";

        if (isNaN(lat) || isNaN(lon)) {
            console.error("MAP_ERROR: Invalid coordinates provided.");
            container.innerHTML = '<div class="alert alert-danger mono m-0">COORDINATE_ERROR: NO_VALID_GEOSPATIAL_DATA</div>';
            return;
        }

        // Initialize Map (High-Contrast Satellite/Tactical style)
        const map = L.map(containerId).setView([lat, lon], 13);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(map);

        // Custom Tactical Icon
        const tacticalIcon = L.divIcon({
            className: 'tactical-marker',
            html: '<div style="background-color: #ffb86c; width: 12px; height: 12px; border: 2px solid #000; border-radius: 50%;"></div>',
            iconSize: [12, 12],
            iconAnchor: [6, 6]
        });

        L.marker([lat, lon], {icon: tacticalIcon})
            .addTo(map)
            .bindPopup(`<span class="mono">TARGET: ${siteName}</span>`)
            .openPopup();
            
        // Render Tactical Overlays (Phase 2b)
        IntelMapOverlay.render(map, overlayData);
            
        console.log(`MAP_INITIALIZED: Targeting Lat ${lat}, Lon ${lon}`);
        return map; // Return instance for drawing tool linkage
    }
};
