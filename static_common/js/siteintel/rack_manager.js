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
        
        // Listen for GPS pulses
        document.addEventListener('webnexus:gps_pulse', (e) => {
            this.currentCoords = e.detail;
            this.updateNearestRack();
        });

        // Bind Check-in Button
        const checkinBtn = document.getElementById('rack-checkin-btn');
        if (checkinBtn) {
            checkinBtn.addEventListener('click', () => this.handleCheckIn());
        }
    },

    async fetchRacks() {
        try {
            const response = await fetch('/siteintel/api/rack-status/');
            if (response.ok) {
                const data = await response.json();
                this.racks = data.racks;
                this.updateNearestRack();
            }
        } catch (error) {
            console.error("RACK_MANAGER: Failed to fetch rack statuses", error);
        }
    },

    updateNearestRack() {
        if (!this.racks.length) return;

        let closest = null;
        let minDistance = Infinity;

        if (this.currentCoords) {
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

        // If no GPS or no racks with coords, default to first or keep current
        if (!closest && this.racks.length > 0) {
            closest = this.racks[0];
        }

        this.nearestRack = closest;
        this.renderUI(minDistance);
    },

    renderUI(distance) {
        const module = document.getElementById('fuel-rack-module');
        if (!module) return;

        const display = document.getElementById('rack-nearest-display');
        const indicator = document.getElementById('rack-status-indicator');
        const dot = document.getElementById('rack-status-dot');
        const text = document.getElementById('rack-status-text');
        const btn = document.getElementById('rack-checkin-btn');

        if (!this.nearestRack) {
            display.innerText = "NO RACKS REGISTERED IN SECTOR";
            return;
        }

        let distStr = "";
        if (distance !== Infinity) {
            distStr = ` (${(distance * 5280).toLocaleString()} FT)`;
        }

        display.innerHTML = `NEAREST: <span class="text-primary">${this.nearestRack.name.toUpperCase()}</span>${distStr}`;
        
        // Update Status
        const status = this.nearestRack.status;
        indicator.style.display = "block";
        text.innerText = status.label.toUpperCase();
        
        // Color mapping
        const colors = {
            'GREEN': '#50fa7b',
            'YELLOW': '#f1fa8c',
            'RED': '#ff5555',
            'GREY': '#6272a4'
        };
        dot.style.color = colors[status.status_code] || 'grey';

        // Enable button
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
