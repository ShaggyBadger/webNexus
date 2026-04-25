/**
 * INTEL_MAP_OVERLAY_MODULE
 * Handles parsing and rendering GeoJSON tactical overlays on a Leaflet map.
 */
export const IntelMapOverlay = {
    /**
     * Renders GeoJSON data onto the provided map instance.
     * @param {L.Map} map - The Leaflet map instance.
     * @param {string} geoJsonString - The GeoJSON string from the database.
     */
    render: function(map, geoJsonString) {
        if (!geoJsonString || geoJsonString === "null" || geoJsonString === "") {
            console.log("OVERLAY_LOAD: No tactical data to render.");
            return null;
        }

        try {
            const data = JSON.parse(geoJsonString);
            
            const overlayLayer = L.geoJSON(data, {
                style: function(feature) {
                    // Custom tactical styling based on properties (if added in the future)
                    return {
                        color: feature.properties.color || "#ffb86c",
                        weight: 4,
                        opacity: 0.8
                    };
                },
                onEachFeature: function(feature, layer) {
                    if (feature.properties && feature.properties.name) {
                        layer.bindTooltip(feature.properties.name, {
                            permanent: true,
                            direction: 'top',
                            className: 'tactical-label'
                        });
                    }
                },
                pointToLayer: function(feature, latlng) {
                    // Custom markers for points (fuel drops)
                    return L.marker(latlng, {
                        icon: L.divIcon({
                            className: 'tactical-marker-overlay',
                            html: `<div style="background-color: ${feature.properties.color || '#ffb86c'}; width: 10px; height: 10px; border: 1px solid #000; border-radius: 50%;"></div>`,
                            iconSize: [10, 10]
                        })
                    }).bindPopup(feature.properties.name || "TACTICAL_POINT");
                }
            }).addTo(map);

            console.log("OVERLAY_LOAD: Tactical intelligence synchronized.");
            return overlayLayer;
        } catch (e) {
            console.error("OVERLAY_ERROR: Failed to parse GeoJSON.", e);
            return null;
        }
    }
};
