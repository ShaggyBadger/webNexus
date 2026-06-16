/**
 * UST Verification Module: webNexus
 * Handles GPS-triggered proximity banners and one-tap verification workflows.
 */

const USTVerification = {
    activeTarget: null,
    activePermit: null,
    confirmModal: null,
    updateModal: null,

    init() {
        console.log("USTVerification: Initializing...");
        
        const banner = document.getElementById('ust-verification-banner');
        // We only initialize the proximity listener if the banner exists (e.g., Homepage)
        if (banner) {
            document.addEventListener('webnexus:gps_pulse', (e) => {
                this.handleGpsPulse(e.detail.lat, e.detail.lon);
            });
        }

        // Initialize Modals if they exist in the DOM
        const confirmEl = document.getElementById('ustConfirmModal');
        const updateEl = document.getElementById('ustUpdateModal');
        
        if (confirmEl) this.confirmModal = new bootstrap.Modal(confirmEl);
        if (updateEl) this.updateModal = new bootstrap.Modal(updateEl);

        // Button Listeners (if elements exist)
        const confirmBtn = document.getElementById('ust-confirm-btn');
        const updateBtn = document.getElementById('ust-update-btn');
        const confirmSubmitBtn = document.getElementById('ust-modal-confirm-submit');
        const updateSubmitBtn = document.getElementById('ust-modal-update-submit');

        if (confirmBtn) confirmBtn.addEventListener('click', () => this.showConfirmModal());
        if (updateBtn) updateBtn.addEventListener('click', () => this.showUpdateModal());
        if (confirmSubmitBtn) confirmSubmitBtn.addEventListener('click', () => this.submitConfirmation());
        if (updateSubmitBtn) updateSubmitBtn.addEventListener('click', () => this.submitUpdate());
    },

    async handleGpsPulse(lat, lon) {
        try {
            const response = await fetch(`/siteintel/api/stores/nearby/?lat=${lat}&lng=${lon}`);
            if (!response.ok) return;
            
            const nearbyStores = await response.json();
            if (nearbyStores.length > 0) {
                // Focus on the closest store
                const target = nearbyStores[0];
                this.activeTarget = target;
                this.fetchAndRenderBanner(target);
            } else {
                this.hideBanner();
            }
        } catch (error) {
            console.error("UST_GPS_TRIGGER_ERROR:", error);
        }
    },

    async fetchAndRenderBanner(target) {
        try {
            const response = await fetch(`/siteintel/api/stores/${target.id}/ust-permit/`);
            if (response.ok) {
                const permit = await response.json();
                this.activePermit = permit;
                this.renderBanner(target, permit);
            } else if (response.status === 404) {
                // No permit record at all - RED warning
                this.activePermit = null;
                this.renderBanner(target, null);
            }
        } catch (error) {
            console.error("UST_BANNER_FETCH_ERROR:", error);
        }
    },

    renderBanner(target, permit) {
        const banner = document.getElementById('ust-verification-banner');
        const card = document.getElementById('ust-banner-card');
        const targetName = document.getElementById('ust-target-name');
        const statusText = document.getElementById('ust-status-text');
        const expiryInfo = document.getElementById('ust-expiry-info');

        if (!banner) return;

        targetName.innerText = `#${target.store_num} ${target.name}`;
        banner.classList.remove('d-none');

        // Status Logic (Mirroring Backend)
        const status = permit ? permit.status : "RED";
        
        card.style.borderColor = this.getStatusColor(status);
        statusText.style.color = this.getStatusColor(status);

        if (status === "GREEN") {
            statusText.innerText = "UST PERMIT VALID";
            expiryInfo.innerText = `EXPIRES: ${permit.expiration_date}`;
        } else if (status === "ORANGE") {
            statusText.innerText = "UST PERMIT EXPIRING SOON";
            expiryInfo.innerText = `EXPIRES: ${permit.expiration_date} (REPLACEMENT NEEDED)`;
        } else {
            statusText.innerText = "WARNING: UST PERMIT EXPIRED";
            expiryInfo.innerText = permit ? `EXPIRED ON: ${permit.expiration_date}` : "NO AUTHORITATIVE PERMIT ON RECORD";
        }
    },

    hideBanner() {
        const banner = document.getElementById('ust-verification-banner');
        if (banner) banner.classList.add('d-none');
        this.activeTarget = null;
        this.activePermit = null;
    },

    getStatusColor(status) {
        switch(status) {
            case "GREEN": return "#50fa7b";
            case "ORANGE": return "#ffb86c";
            case "RED": return "#ff5555";
            default: return "#f8f8f2";
        }
    },

    showConfirmModal() {
        if (!this.activeTarget) return;
        document.getElementById('modal-target-name').innerText = this.activeTarget.name;
        document.getElementById('modal-target-expiry').innerText = this.activePermit ? this.activePermit.expiration_date : "N/A";
        this.confirmModal.show();
    },

    /**
     * Shows the update modal.
     * @param {number} storeId - Optional store ID if called from Site Intelligence page.
     */
    async showUpdateModal(storeId = null) {
        const id = storeId || (this.activeTarget ? this.activeTarget.id : null);
        if (!id) return;

        // If we don't have activeTarget (meaning we're on the Site Intel page), fetch basic info
        if (!this.activeTarget || this.activeTarget.id != id) {
            try {
                const response = await fetch(`/siteintel/api/stores/${id}/ust-permit/`);
                if (response.ok) {
                    this.activePermit = await response.json();
                    this.activeTarget = { id: id, name: "CURRENT_SITE" }; // Minimal mock for modal context
                } else {
                    this.activePermit = null;
                    this.activeTarget = { id: id, name: "CURRENT_SITE" };
                }
            } catch (e) {
                console.error("UST_UPDATE_FETCH_ERROR:", e);
                return;
            }
        }

        const form = document.getElementById('ust-update-form');
        form.reset();
        
        if (this.activePermit) {
            form.elements['permit_number'].value = this.activePermit.permit_number || '';
            form.elements['expiration_date'].value = this.activePermit.expiration_date;
            form.elements['issue_date'].value = this.activePermit.issue_date || '';
        }
        
        this.updateModal.show();
    },

    async submitConfirmation() {
        const notes = document.getElementById('ust-confirm-notes').value;
        try {
            const response = await fetch(`/siteintel/api/stores/${this.activeTarget.id}/ust-verifications/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                },
                body: JSON.stringify({
                    verification_type: 'confirmed',
                    notes: notes
                })
            });

            if (response.ok) {
                this.confirmModal.hide();
                window.location.reload();
            }
        } catch (error) {
            console.error("UST_CONFIRM_ERROR:", error);
            alert("TACTICAL_ERROR: Failed to record verification.");
        }
    },

    async submitUpdate() {
        const form = document.getElementById('ust-update-form');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch(`/siteintel/api/stores/${this.activeTarget.id}/ust-permit/`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                },
                body: JSON.stringify(data)
            });

            if (response.ok) {
                this.updateModal.hide();
                window.location.reload();
            } else {
                const errData = await response.json();
                alert("SYNC_FAILED: " + JSON.stringify(errData));
            }
        } catch (error) {
            console.error("UST_UPDATE_ERROR:", error);
            alert("TACTICAL_ERROR: Failed to update permit.");
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    USTVerification.init();
});
