/**
 * INTEL_MAP_DRAW_MODULE
 * OPERATIONAL FLOW:
 * Provides the Leaflet.draw interface for creating tactical map proposals.
 * Captures user drawings (arrows, routes, drops) and synchronizes them to a hidden
 * GeoJSON form field for administrative review.
 */
export const IntelMapDraw = {
    currentColor: '#ffb86c', // Default Tactical Amber
    drawControl: null,

    /**
     * TACTICAL_INITIALIZATION:
     * Sets up the drawing canvas, loads existing drawings, and attaches event listeners.
     * @param {L.Map} map - The Leaflet map instance.
     * @param {string} hiddenFieldId - ID of the form field to store GeoJSON.
     * @param {string} initialData - Existing GeoJSON data from the Location record.
     */
    init: function(map, hiddenFieldId, initialData) {
        const hiddenField = document.getElementById(hiddenFieldId);
        if (!hiddenField) {
            console.error("DRAW_ERROR: Target synchronization field not found.");
            return;
        }

        // The FeatureGroup that holds all editable shapes
        const drawnItems = new L.FeatureGroup();
        map.addLayer(drawnItems);

        // PERSISTENCE_RECOVERY: Load initial data into the editable group
        if (initialData && initialData !== "null" && initialData !== "") {
            try {
                const data = JSON.parse(initialData);
                L.geoJSON(data).eachLayer(layer => {
                    // Preserve tactical metadata (color/labels) from the digital twin
                    if (layer.feature && layer.feature.properties) {
                        const props = layer.feature.properties;
                        if (props.color && layer.setStyle) {
                            layer.setStyle({ color: props.color });
                        }
                        if (props.name) {
                            layer.bindTooltip(props.name, { 
                                permanent: true, 
                                direction: 'top', 
                                className: 'tactical-label' 
                            });
                        }
                    }
                    drawnItems.addLayer(layer);
                });
                console.log("DRAW_INIT: Recovered existing tactical intelligence.");
            } catch (e) {
                console.error("DRAW_INIT_ERROR: Failed to parse tactical overlay data.", e);
            }
        }

        // Initialize the Leaflet.draw interface
        this.updateDrawControl(map, drawnItems);

        /**
         * TACTICAL_SYNCHRONIZATION:
         * Converts the current drawing state to GeoJSON and updates the form.
         */
        const updateField = () => {
            const data = drawnItems.toGeoJSON();
            // Ensure every feature has its tactical properties set
            data.features.forEach((feature, index) => {
                const layer = Object.values(drawnItems._layers)[index];
                if (layer && layer.options && layer.options.color) {
                    feature.properties.color = layer.options.color;
                } else {
                    feature.properties.color = feature.properties.color || this.currentColor;
                }
            });
            hiddenField.value = JSON.stringify(data);
            console.log("DRAW_SYNC: Tactical intelligence captured.");
        };

        // EVENT_HANDLERS: Listen for tactical drawing creation/edits
        map.on(L.Draw.Event.CREATED, (e) => {
            const layer = e.layer;
            
            // TACTICAL_LABEL_PROMPT: Ask agent for identification text
            const label = prompt("ENTER_LABEL_TEXT (e.g. 'ENTRY ROUTE', 'TANK 1 DROP'):", "");
            
            // Apply currently active tactical color
            if (layer.setStyle) {
                layer.setStyle({ color: this.currentColor });
            }
            
            // Initialize GeoJSON properties if not present
            if (!layer.feature) layer.feature = { type: 'Feature', properties: {} };
            layer.feature.properties.color = this.currentColor;
            
            if (label) {
                layer.feature.properties.name = label;
                layer.bindTooltip(label, { 
                    permanent: true, 
                    direction: 'top', 
                    className: 'tactical-label' 
                }).openTooltip();
            }
            
            drawnItems.addLayer(layer);
            updateField();
            console.log(`TACTICAL_OBJECT_CREATED: ${label || 'UNIDENTIFIED'}`);
        });

        map.on(L.Draw.Event.EDITED, () => {
            updateField();
            console.log("TACTICAL_OBJECT_MODIFIED");
        });

        map.on(L.Draw.Event.DELETED, () => {
            updateField();
            console.log("TACTICAL_OBJECT_PURGED");
        });

        // Initialize the color selection interface
        this.bindColorPicker(map, drawnItems);

        // Perform initial synchronization
        updateField();
        
        console.log("INTEL_MAP_DRAW_READY: Tactical interface online.");
    },

    /**
     * TACTICAL_TOOL_UPDATE:
     * Re-initializes the drawing control to reflect current color/style choices.
     */
    updateDrawControl: function(map, drawnItems) {
        if (this.drawControl) {
            map.removeControl(this.drawControl);
        }

        const shapeOptions = {
            color: this.currentColor,
            weight: 4
        };

        this.drawControl = new L.Control.Draw({
            edit: {
                featureGroup: drawnItems
            },
            draw: {
                polygon: { shapeOptions: shapeOptions },
                polyline: { shapeOptions: shapeOptions },
                rectangle: { shapeOptions: shapeOptions },
                circle: false, // Tactical drawings use polygons/rectangles
                marker: {
                    icon: L.divIcon({
                        className: 'tactical-marker-draw',
                        html: `<div style="background-color: ${this.currentColor}; width: 12px; height: 12px; border: 2px solid #000; border-radius: 50%;"></div>`,
                        iconSize: [12, 12]
                    })
                },
                circlemarker: false
            }
        });
        map.addControl(this.drawControl);
    },

    /**
     * UI_INTEGRATION:
     * Binds HTML color swatches to the internal drawing state.
     */
    bindColorPicker: function(map, drawnItems) {
        const swatches = document.querySelectorAll('.color-swatch');
        swatches.forEach(swatch => {
            swatch.addEventListener('click', () => {
                // UI_FEEDBACK
                swatches.forEach(s => s.classList.remove('active'));
                swatch.classList.add('active');
                
                // STATE_UPDATE
                this.currentColor = swatch.dataset.color;
                
                // TOOL_RECONFIGURATION
                this.updateDrawControl(map, drawnItems);
                
                console.log(`TACTICAL_COLOR_ACTIVE: ${this.currentColor}`);
            });
        });
    }
};
