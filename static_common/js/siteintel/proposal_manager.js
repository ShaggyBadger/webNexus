/**
 * PROPOSAL_MANAGER
 * Handles dynamic UI switching and specialized data entry for site proposals.
 * Manages Store, Fuel Rack, and Yard specific field visibility.
 */

export const ProposalManager = {
    init() {
        console.log("PROPOSAL_MANAGER: Initializing UI controller...");
        const typeSelect = document.getElementById('id_location_type');
        if (!typeSelect) return;

        this.setupToggles(typeSelect);
        
        // Initial trigger
        const initialTypeName = typeSelect.options[typeSelect.selectedIndex] ? typeSelect.options[typeSelect.selectedIndex].text : '';
        this.toggleSections(initialTypeName);

        // Initialize Rack Lane Configurator
        this.LaneConfig.init('lane-configurator-container', 'id_rack_config_json');
    },

    setupToggles(select) {
        select.addEventListener('change', (e) => {
            const typeName = e.target.options[e.target.selectedIndex].text;
            this.toggleSections(typeName);
        });
    },

    toggleSections(typeName) {
        console.log(`PROPOSAL_MANAGER: Switching to [${typeName}] mode.`);
        const upperType = typeName.toUpperCase();
        
        const storeSection = document.getElementById('store-fields-container');
        const rackSection = document.getElementById('rack-fields-container');
        const yardSection = document.getElementById('yard-fields-container');
        const tankSection = document.getElementById('tank-mapping-container');
        const quirksSection = document.getElementById('quirks-section-container');

        // Hide all first
        [storeSection, rackSection, yardSection, tankSection, quirksSection].forEach(el => {
            if (el) el.classList.add('d-none');
        });

        if (upperType.includes('RACK')) {
            if (rackSection) rackSection.classList.remove('d-none');
            // Quirks remain hidden for Racks
        } else if (upperType.includes('YARD')) {
            if (yardSection) yardSection.classList.remove('d-none');
            if (quirksSection) quirksSection.classList.remove('d-none');
        } else {
            // Default to Store for Gas Station or anything else
            if (storeSection) storeSection.classList.remove('d-none');
            if (tankSection) tankSection.classList.remove('d-none');
            if (quirksSection) quirksSection.classList.remove('d-none');
        }
    },

    /**
     * LANE_CONFIGURATOR
     * Visual tool for building the JSON configuration for fuel racks.
     */
    LaneConfig: {
        lanes: [],
        container: null,
        hiddenInput: null,
        fuelTypes: ['Regular', 'Plus', 'Premium', 'Diesel', 'Kerosene'],

        init(containerId, inputId) {
            this.container = document.getElementById(containerId);
            this.hiddenInput = document.getElementById(inputId);
            if (!this.container || !this.hiddenInput) return;

            // Load existing data
            if (this.hiddenInput.value && this.hiddenInput.value !== '{}') {
                try {
                    const data = JSON.parse(this.hiddenInput.value);
                    this.lanes = data.lanes || [];
                } catch (e) {
                    console.error("LANE_CONFIG: Failed to parse initial JSON.");
                }
            }

            this.render();
        },

        addLane() {
            const newLaneId = this.lanes.length > 0 ? Math.max(...this.lanes.map(l => l.id)) + 1 : 1;
            this.lanes.push({ id: newLaneId, arms: [] });
            this.saveAndRender();
        },

        removeLane(laneId) {
            this.lanes = this.lanes.filter(l => l.id !== laneId);
            this.saveAndRender();
        },

        toggleArm(laneId, product) {
            const lane = this.lanes.find(l => l.id === laneId);
            if (!lane) return;

            if (lane.arms.includes(product)) {
                lane.arms = lane.arms.filter(a => a !== product);
            } else {
                lane.arms.push(product);
            }
            this.saveAndRender();
        },

        saveAndRender() {
            this.hiddenInput.value = JSON.stringify({ lanes: this.lanes });
            this.render();
        },

        render() {
            if (!this.container) return;

            let html = `
                <div class="row g-3">
                    ${this.lanes.map((lane, idx) => `
                        <div class="col-md-6 col-lg-4">
                            <div class="lane-card p-2 border border-secondary bg-dark position-relative">
                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <span class="mono text-primary small">LANE_${lane.id.toString().padStart(2, '0')}</span>
                                    <button type="button" class="btn btn-outline-danger btn-xs py-0 px-1 mono" onclick="ProposalManager.LaneConfig.removeLane(${lane.id})" style="font-size: 0.6rem;">[ REMOVE ]</button>
                                </div>
                                <div class="d-flex flex-wrap gap-1">
                                    ${this.fuelTypes.map(ft => {
                                        const isActive = lane.arms.includes(ft);
                                        return `
                                            <button type="button" 
                                                class="btn btn-xs py-0 px-2 mono ${isActive ? 'btn-primary' : 'btn-outline-secondary'}" 
                                                style="font-size: 0.65rem;"
                                                onclick="ProposalManager.LaneConfig.toggleArm(${lane.id}, '${ft}')">
                                                ${ft.toUpperCase()}
                                            </button>
                                        `;
                                    }).join('')}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                    
                    <div class="col-12">
                        <button type="button" class="btn btn-outline-primary btn-sm mono mt-2" onclick="ProposalManager.LaneConfig.addLane()">
                            [ + ADD LANE ]
                        </button>
                    </div>
                </div>
            `;

            this.container.innerHTML = html;
        }
    }
};

// Tactical Export for global access via onclick (for legacy interop)
window.ProposalManager = ProposalManager;
