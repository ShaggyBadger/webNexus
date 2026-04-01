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
            netDisplay.className = "text-tactical-success";
        } else {
            netDisplay.innerText = "OFFLINE";
            netDisplay.className = "text-tactical-danger";
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
                const status = (data.db_status || "").trim().toUpperCase();
                dbDisplay.innerText = status;

                // Robust success check: Any status containing READY or OK is green
                if (status.includes("READY") || status.includes("OK")) {
                    dbDisplay.className = "text-tactical-success";
                } else {
                    dbDisplay.className = "text-tactical-danger";
                }
            } else {
                dbDisplay.innerText = "CONN_ERROR";
                dbDisplay.className = "text-tactical-danger";
            }

            // Latency Logic
            latencyDisplay.innerText = `${latency}ms`;
            if (latency < this.thresholds.good) {
                latencyDisplay.className = "text-tactical-success";
            } else if (latency < this.thresholds.warning) {
                latencyDisplay.className = "text-tactical-warning";
            } else {
                latencyDisplay.className = "text-tactical-danger";
            }

        } catch (error) {
            console.error("Health Check Failed:", error);
            dbDisplay.innerText = "LINK_LOST";
            dbDisplay.className = "text-tactical-danger";
            latencyDisplay.innerText = "ERR";
            latencyDisplay.className = "text-tactical-danger";
        }
    }
};

// Initial pulse and periodic update
document.addEventListener('DOMContentLoaded', () => {
    FieldIntel.update();
    setInterval(() => FieldIntel.update(), 15000); // 15s refresh for better feedback
});

window.addEventListener('online', () => FieldIntel.update());
window.addEventListener('offline', () => FieldIntel.update());
