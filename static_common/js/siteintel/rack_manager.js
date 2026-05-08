/**
 * RackManager Module: webNexus
 * Handles fuel rack status tracking and check-in lifecycle.
 */

const RackManager = {
    racks: [],
    nearestRack: null,
    currentCoords: null,

    init() {
        console.log("RACK_MANAGER: Initializing...");
        this.fetchRacks();
        
        // TACTICAL_PULSE: Listen for GPS updates from the global TacticalGPS module
        document.addEventListener('webnexus:gps_pulse', (e) => {
            this.currentCoords = e.detail;
            this.updateNearestRack();
        });

        // ACTION_BIND: Link the check-in button logic
        const checkinBtn = document.getElementById('rack-checkin-btn');
        if (checkinBtn) {
            checkinBtn.addEventListener('click', () => this.handleCheckIn());
        }
    },

    /**
     * Fetches the authoritative list of racks and their current lockout statuses.
     */
    async fetchRacks() {
        try {
            const response = await fetch('/siteintel/api/rack-status/');
            if (response.ok) {
                const data = await response.json();
                this.racks = data.racks;
                
                // BOOTSTRAP: Update nearest rack immediately to clear "Scanning" state
                this.updateNearestRack();
            }
        } catch (error) {
            console.error("RACK_MANAGER: Failed to fetch rack statuses", error);
        }
    },

    /**
     * TACTICAL_ANALYSIS:
     * Calculates the closest physical fuel rack based on current GPS pulse.
     * Implements an 'Always-Up' fallback to ensure the UI is never stuck.
     */
    updateNearestRack() {
        let closest = null;
        let minDistance = Infinity;

        // 1. PRIMARY_SCAN: Try to find the closest rack if GPS is available
        if (this.currentCoords && this.racks.length > 0) {
            this.racks.forEach(rack => {
                if (rack.lat && rack.lon) {
                    const dist = this.haversine(
                        this.currentCoords.lat, 
                        this.currentCoords.lon, 
                        rack.lat, 
                        rack.lon
                    );
                    if (dist < minDistance) {
                        minDistance = dist;
                        closest = rack;
                    }
                }
            });
        }

        // 2. FAILSAFE_FALLBACK:
        // If GPS is lost or no racks have coordinates, we default to the first
        // rack in the list. This ensures the 'Check-In' button is always
        // functional even in 'Signal Blackout' conditions.
        if (!closest && this.racks.length > 0) {
            closest = this.racks[0];
        }

        this.nearestRack = closest;
        this.renderUI(minDistance);
    },

    /**
     * RENDER_UI:
     * Updates the homepage module with target name, distance, and lockout status.
     * Ensures high-contrast feedback for operational field use.
     */
    renderUI(distance) {
        const module = document.getElementById('fuel-rack-module');
        if (!module) return;

        const display = document.getElementById('rack-nearest-display');
        const indicator = document.getElementById('rack-status-indicator');
        const dot = document.getElementById('rack-status-dot');
        const text = document.getElementById('rack-status-text');
        const btn = document.getElementById('rack-checkin-btn');

        // STATE: No data available
        if (!this.racks.length) {
            display.innerText = "NO RACKS REGISTERED IN SECTOR";
            btn.disabled = true;
            return;
        }

        // STATE: Waiting for processing
        if (!this.nearestRack) {
            display.innerText = "DETERMINING NEAREST RACK...";
            btn.disabled = true;
            return;
        }

        // DISTANCE_NORMALIZATION: Convert miles to feet for field precision
        let distStr = "";
        if (distance !== Infinity && distance !== null) {
            distStr = ` (${(distance * 5280).toLocaleString()} FT)`;
        }

        display.innerHTML = `NEAREST: <span class="text-primary">${this.nearestRack.name.toUpperCase()}</span>${distStr}`;
        
        // TACTICAL_STATUS: Show colored indicator for lockout window
        const status = this.nearestRack.status;
        indicator.style.display = "block";
        text.innerText = status.label.toUpperCase();
        
        // COLOR_SCHEMA: Draculish/Tactical palette mapping
        const colors = {
            'GREEN': '#50fa7b',
            'YELLOW': '#f1fa8c',
            'RED': '#ff5555',
            'GREY': '#6272a4'
        };
        dot.style.color = colors[status.status_code] || 'grey';

        // ACTIVATE: Enable interaction
        btn.disabled = false;
        btn.innerText = `CHECK-IN @ ${this.nearestRack.name.split(' ')[0].toUpperCase()}`;
    },

    async handleCheckIn() {
        if (!this.nearestRack) return;

        const btn = document.getElementById('rack-checkin-btn');
        const originalText = btn.innerText;
        btn.disabled = true;
        btn.innerText = "RECORDING...";

        try {
            const response = await fetch('/siteintel/api/rack-checkin/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify({
                    rack_id: this.nearestRack.id,
                    lat: this.currentCoords ? this.currentCoords.lat : null,
                    lon: this.currentCoords ? this.currentCoords.lon : null,
                    accuracy: this.currentCoords ? this.currentCoords.accuracy : null
                })
            });

            if (response.ok) {
                const data = await response.json();
                // Update local status
                this.nearestRack.status = data.status;
                this.renderUI();
                
                // Visual feedback
                btn.innerText = "CHECK-IN SUCCESS";
                btn.classList.replace('btn-outline-warning', 'btn-success');
                
                setTimeout(() => {
                    btn.classList.replace('btn-success', 'btn-outline-warning');
                    btn.innerText = originalText;
                    btn.disabled = false;
                }, 3000);
            } else {
                throw new Error("Check-in failed");
            }
        } catch (error) {
            console.error("RACK_MANAGER: Check-in error", error);
            btn.innerText = "ERROR - RETRY";
            btn.disabled = false;
        }
    },

    haversine(lat1, lon1, lat2, lon2) {
        const R = 3956; // Miles
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    },

    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
};

document.addEventListener('DOMContentLoaded', () => {
    RackManager.init();
});
