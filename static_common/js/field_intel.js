/**
 * Field Intel Module: webNexus
 * Manages operational indicators: Net State, DB Sync, and Latency.
 */

const FieldIntel = {
    endpoints: {
        health: '/system/health/'
    },

    // Latency Thresholds (ms)
    thresholds: {
        good: 200,
        warning: 500
    },

    async update() {
        this.checkNetState();
        await this.checkSystemHealth();
    },

    checkNetState() {
        const netDisplay = document.getElementById('intel-net-state');
        if (!netDisplay) return;

        if (navigator.onLine) {
            netDisplay.innerText = "SECURE_LINK";
            netDisplay.className = "text-tactical-success small mono";
        } else {
            netDisplay.innerText = "OFFLINE";
            netDisplay.className = "text-tactical-danger small mono";
        }
    },

    async checkSystemHealth() {
        const dbDisplay = document.getElementById('intel-db-status');
        const latencyDisplay = document.getElementById('intel-latency');
        if (!dbDisplay || !latencyDisplay) return;

        const startTime = performance.now();
        
        try {
            const response = await fetch(this.endpoints.health, { cache: 'no-store' });
            const endTime = performance.now();
            const latency = Math.round(endTime - startTime);

            // DB Status Logic
            if (response.ok) {
                const data = await response.json();
                dbDisplay.innerText = data.db_status;
                dbDisplay.className = data.db_status === "SYNC_OK" ? "text-tactical-success small mono" : "text-tactical-danger small mono";
            } else {
                dbDisplay.innerText = "CONN_ERROR";
                dbDisplay.className = "text-tactical-danger small mono";
            }

            // Latency Logic (Industry Standard)
            latencyDisplay.innerText = `${latency}ms`;
            if (latency < this.thresholds.good) {
                latencyDisplay.className = "text-tactical-success small mono";
            } else if (latency < this.thresholds.warning) {
                latencyDisplay.className = "text-tactical-warning small mono";
            } else {
                latencyDisplay.className = "text-tactical-danger small mono";
            }

        } catch (error) {
            dbDisplay.innerText = "LINK_LOST";
            dbDisplay.className = "text-tactical-danger small mono";
            latencyDisplay.innerText = "ERR";
            latencyDisplay.className = "text-tactical-danger small mono";
        }
    }
};

// Initial pulse and periodic update
document.addEventListener('DOMContentLoaded', () => {
    FieldIntel.update();
    setInterval(() => FieldIntel.update(), 30000);
});

window.addEventListener('online', () => FieldIntel.update());
window.addEventListener('offline', () => FieldIntel.update());
