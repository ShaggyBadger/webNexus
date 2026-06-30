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
        
        // Initialize Modals if they exist in the DOM
        const confirmEl = document.getElementById('ustConfirmModal');
        const updateEl = document.getElementById('ustUpdateModal');
        
        if (confirmEl) this.confirmModal = new bootstrap.Modal(confirmEl);
        if (updateEl) this.updateModal = new bootstrap.Modal(updateEl);

        // Button Listeners (for modals)
        const confirmSubmitBtn = document.getElementById('ust-modal-confirm-submit');
        const updateSubmitBtn = document.getElementById('ust-modal-update-submit');

        if (confirmSubmitBtn) confirmSubmitBtn.addEventListener('click', () => this.submitConfirmation());
        if (updateSubmitBtn) updateSubmitBtn.addEventListener('click', () => this.submitUpdate());
    },

    /**
     * Ensures we have the permit and target data for the given store ID.
     */
    async ensureActiveContext(storeId) {
        if (this.activeTarget && this.activeTarget.id == storeId) return true;

        try {
            const response = await fetch(`/siteintel/api/stores/${storeId}/ust-permit/`);
            if (response.ok) {
                this.activePermit = await response.json();
                // We use a simplified target since we're already on the page or have the ID
                this.activeTarget = { id: storeId, name: document.getElementById('modal-target-name')?.innerText || "CURRENT_SITE" };
                return true;
            } else if (response.status === 404) {
                this.activePermit = null;
                this.activeTarget = { id: storeId, name: "CURRENT_SITE" };
                return true;
            }
        } catch (e) {
            console.error("UST_CONTEXT_FETCH_ERROR:", e);
        }
        return false;
    },

    async showConfirmModal(storeId) {
        if (!storeId) return;
        const ready = await this.ensureActiveContext(storeId);
        if (!ready) return;

        document.getElementById('modal-target-name').innerText = this.activeTarget.name === "CURRENT_SITE" ? "" : this.activeTarget.name;
        
        // Format YYYY-MM-DD to MM/YYYY for display
        let displayExpiry = "N/A";
        if (this.activePermit && this.activePermit.expiration_date) {
            const parts = this.activePermit.expiration_date.split('-');
            if (parts.length >= 2) {
                displayExpiry = `${parts[1]}/${parts[0]}`;
            }
        }
        document.getElementById('modal-target-expiry').innerText = displayExpiry;
        this.confirmModal.show();
    },

    async showUpdateModal(storeId) {
        if (!storeId) return;
        const ready = await this.ensureActiveContext(storeId);
        if (!ready) return;

        const form = document.getElementById('ust-update-form');
        form.reset();
        
        if (this.activePermit) {
            // Input type="month" expects YYYY-MM
            if (this.activePermit.expiration_date) {
                form.elements['expiration_date'].value = this.activePermit.expiration_date.substring(0, 7);
            }
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
        const data = {
            expiration_date: formData.get('expiration_date'),
            verification_notes: formData.get('verification_notes') || '',
        };

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
