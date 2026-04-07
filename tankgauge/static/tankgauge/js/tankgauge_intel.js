/**
 * TankGauge Delivery Intel Logic
 * Ported to modular structure.
 */

const TankGaugeIntel = {
    calcUrl: '',
    storeId: '',
    isPreset: false,
    calculatedTanks: {}, // Store results for mission summary
    intelInterval: null,

    /**
     * Entry point for all TankGauge pages.
     */
    init(config) {
        this.calcUrl = config.calcUrl || '';
        this.storeId = config.storeId || '';
        this.isPreset = config.isPreset || false;
        this.calculatedTanks = {};

        document.addEventListener("DOMContentLoaded", () => {
            // 1. Logic for RESULTS pages (DB and Preset)
            if (document.getElementById('tank-cards')) {
                this.bindCalcButtons();
            }

            // 2. Logic for the INITIAL PARAMETERS form
            if (document.getElementById('lock-nearest-btn') || document.getElementById('preset-711-btn')) {
                this.bindFormPresets();
                this.bindMainFormValidation();
                this.updateIntelUI();
                this.startIntelPulse();
            }
        });
    },

    /**
     * RESULTS PAGE: Bind calculation buttons
     */
    bindCalcButtons() {
        const calcButtons = document.querySelectorAll(".btn-ajax-calculate");
        calcButtons.forEach(btn => {
            btn.addEventListener("click", () => this.executeCalculation(btn));
        });
    },

    /**
     * RESULTS PAGE: Execute the AJAX calculation
     */
    async executeCalculation(btn) {
        const card = btn.closest(".tactical-card");
        this.clearErrors(card);

        const fuelType = card.dataset.fuelType;
        const deliveryInput = card.querySelector('input[name*="delivery_gallons"]');
        const inchesInput = card.querySelector('input[name*="current_inches"]');
        
        const deliveryValue = deliveryInput.value.trim();
        const inchesValue = inchesInput.value.trim();
        const maxDepth = parseFloat(card.dataset.maxDepth);

        let hasError = false;

        // 1. Current Inches Validation
        if (inchesValue === "") {
            this.showError(inchesInput, "OPERATIONAL_ERROR: CURRENT_INCHES REQUIRED");
            hasError = true;
        } else if (!/^\d*\.?\d+$/.test(inchesValue)) {
            this.showError(inchesInput, "PARAMETER_ERROR: NUMERIC ONLY");
            hasError = true;
        } else {
            const currentInches = parseFloat(inchesValue);
            if (currentInches < 0 || currentInches > maxDepth) {
                this.showError(inchesInput, `RANGE_ERROR: 0 - ${maxDepth}`);
                hasError = true;
            }
        }

        // 2. Delivery Gallons Validation
        let deliveryGallons = 0;
        if (deliveryValue !== "") {
            if (!/^\d+$/.test(deliveryValue)) {
                this.showError(deliveryInput, "PARAMETER_ERROR: POSITIVE INTEGER ONLY");
                hasError = true;
            } else {
                deliveryGallons = parseInt(deliveryValue);
            }
        }

        if (hasError) return;

        const currentInches = parseFloat(inchesValue);

        const originalText = btn.innerText;
        btn.innerHTML = '<i class="fas fa-microchip fa-spin me-2"></i>PROCESSING...';
        btn.disabled = true;

        try {
            const formData = new FormData();
            formData.append("store_id", this.storeId);
            formData.append("fuel_type", fuelType);
            formData.append("current_inches", currentInches);
            formData.append("delivery_gallons", deliveryGallons);

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

            const response = await fetch(this.calcUrl, {
                method: "POST",
                body: formData,
                headers: {
                    "X-CSRFToken": csrfToken || ""
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.updateResultsUI(card, data, fuelType);
            } else {
                const errText = await response.text();
                console.error("API Error Response:", response.status, errText);
                let errorMessage = "UNKNOWN_API_ERROR";
                try {
                    const errJson = JSON.parse(errText);
                    errorMessage = errJson.error || errorMessage;
                } catch(e) {}
                alert("CALCULATION_ERROR: " + errorMessage);
            }
        } catch (e) {
            console.error("Fetch Exception:", e);
            alert("SYSTEM_CRITICAL_ERROR: API_COMMUNICATION_FAILED (Check Console)");
        } finally {
            btn.innerText = originalText;
            btn.disabled = false;
        }
    },

    showError(input, message) {
        input.classList.add("is-invalid");
        input.style.borderColor = "#ff5555";
        input.style.boxShadow = "0 0 10px rgba(255, 85, 85, 0.3)";
        const feedback = input.parentNode.querySelector(".error-feedback");
        if (feedback) {
            feedback.innerText = message;
            feedback.style.display = "block";
        }
    },

    clearErrors(card) {
        const inputs = card.querySelectorAll(".tankgauge-form-control");
        inputs.forEach(input => {
            input.classList.remove("is-invalid");
            input.style.borderColor = "";
            input.style.boxShadow = "";
            const feedback = input.parentNode.querySelector(".error-feedback");
            if (feedback) {
                feedback.style.display = "none";
            }
        });
    },

    /**
     * RESULTS PAGE: Update the UI with calculation results
     */
    updateResultsUI(card, data, fuelType) {
        const resultsArea = card.querySelector(".ajax-results");
        const avail90Val = Math.max(0, data.avail_90);
        
        const avail90El = resultsArea.querySelector(".res-avail-90");
        const avail90Line = resultsArea.querySelector(".res-avail-90-line");
        const avail90Label = resultsArea.querySelector(".specs-label-avail");
        
        resultsArea.querySelector(".res-initial-inches").innerText = data.initial_inches;
        resultsArea.querySelector(".res-initial-vol").innerText = data.initial_gallons.toLocaleString();
        avail90El.innerText = avail90Val.toLocaleString();
        
        if (data.no_fit_warning) {
            avail90Line.style.setProperty("color", "#ff5555", "important");
            avail90Line.style.setProperty("font-weight", "900", "important");
            avail90El.style.setProperty("color", "#ff5555", "important");
            if (avail90Label) avail90Label.style.setProperty("color", "#ff5555", "important");
            avail90Line.classList.add("flicker");
        } else {
            avail90Line.style.color = "";
            avail90Line.style.fontWeight = "";
            avail90El.style.color = "";
            if (avail90Label) avail90Label.style.color = "";
            avail90Line.classList.remove("flicker");
        }

        resultsArea.querySelector(".res-bol-gallons").innerText = data.delivery_gallons.toLocaleString();
        resultsArea.querySelector(".res-final-vol").innerText = data.final_gallons.toLocaleString();
        resultsArea.querySelector(".res-final-depth").innerText = data.final_inches;
        
        // Track results for Mission Summary
        this.calculatedTanks[fuelType] = {
            delivery: data.delivery_gallons,
            noFit: data.no_fit_warning
        };

        const warningBox = resultsArea.querySelector(".no-fit-warning");
        if (warningBox) warningBox.style.display = data.no_fit_warning ? "block" : "none";
        
        resultsArea.style.display = "block";
        resultsArea.style.opacity = "0";
        setTimeout(() => {
            resultsArea.style.transition = "opacity 0.5s ease";
            resultsArea.style.opacity = "1";
        }, 10);

        this.updateMissionSummary();
    },

    /**
     * RESULTS PAGE: Update the final Mission Summary box
     */
    updateMissionSummary() {
        const summaryBox = document.getElementById("mission-summary");
        if (!summaryBox) return;

        let totalVol = 0;
        let anyNoFit = false;
        let tankCount = 0;

        for (const fuel in this.calculatedTanks) {
            totalVol += this.calculatedTanks[fuel].delivery;
            if (this.calculatedTanks[fuel].noFit) anyNoFit = true;
            tankCount++;
        }

        if (tankCount > 0) {
            summaryBox.style.display = "block";
            document.getElementById("summary-total-vol").innerText = totalVol.toLocaleString() + " G";
            
            const statusEl = document.getElementById("summary-status");
            const warningEl = document.getElementById("summary-warning");

            if (anyNoFit) {
                statusEl.innerText = "CRITICAL_WARNING";
                statusEl.style.color = "#ff5555";
                if (warningEl) warningEl.style.display = "block";
            } else {
                statusEl.innerText = "NOMINAL_CLEAR_TO_PUMP";
                statusEl.style.color = "#8da35d";
                if (warningEl) warningEl.style.display = "none";
            }
        }
    },

    /**
     * FORM PAGE: Bind "Lock Nearest" and "7-11 Standard" presets
     */
    bindFormPresets() {
        const storeInput = document.querySelector('input[name="store_number"]');
        if (!storeInput) return;

        const lockNearestBtn = document.getElementById('lock-nearest-btn');
        const preset711Btn = document.getElementById('preset-711-btn');

        if (lockNearestBtn) {
            lockNearestBtn.addEventListener('click', async () => {
                const originalText = lockNearestBtn.innerHTML;
                lockNearestBtn.innerHTML = '<i class="fas fa-satellite-dish fa-spin me-1"></i> ACQUIRING...';
                lockNearestBtn.disabled = true;

                try {
                    // TacticalGPS is global from base.html
                    const data = await TacticalGPS.pulse();
                    storeInput.value = data.store_num;
                    this.updateIntelUI(data);
                } catch (err) {
                    console.warn("Fresh Pulse Failed:", err);
                    const storedId = this.updateIntelUI();
                    if (storedId) storeInput.value = storedId;
                    else alert("OPERATIONAL ERROR: No GPS Signal Locked.");
                } finally {
                    lockNearestBtn.innerHTML = originalText;
                    lockNearestBtn.disabled = false;
                }
            });
        }

        if (preset711Btn) {
            preset711Btn.addEventListener('click', () => {
                storeInput.value = "7-11_STD";
                // Hide intel line for explicit manual override
                document.getElementById('intel-status-line').style.visibility = "hidden";
            });
        }
    },

    /**
     * FORM PAGE: Bind submission validation
     */
    bindMainFormValidation() {
        const form = document.querySelector("form");
        if (!form) return;

        form.addEventListener("submit", (e) => {
            const storeNumber = document.querySelector('input[name="store_number"]').value.trim();
            const fuelCheckboxes = document.querySelectorAll('input[name="fuel_types"]:checked');
            if (!storeNumber || fuelCheckboxes.length === 0) {
                e.preventDefault();
                alert("OPERATIONAL ERROR: TARGET_STORE_ID and FUEL_TYPE SELECTION REQUIRED");
            }
        });
    },

    /**
     * FORM PAGE: Update the "Signal Locked" UI feedback
     */
    updateIntelUI(data = null) {
        const intelStatusLine = document.getElementById('intel-status-line');
        const statusId = document.getElementById('intel-status-id');
        const statusDist = document.getElementById('intel-status-dist');
        const directIntelStatus = document.getElementById('direct-intel-status');
        const directIntelId = document.getElementById('direct-intel-id');
        const directIntelDist = document.getElementById('direct-intel-dist');

        if (!intelStatusLine) return null;

        if (data) {
            intelStatusLine.style.visibility = "visible";
            statusId.innerText = `#${data.store_num}`;
            statusDist.innerText = "SIGNAL_LOCKED";
            if (directIntelStatus) {
                directIntelStatus.style.visibility = "visible";
                directIntelId.innerText = `#${data.store_num}`;
                directIntelDist.innerText = `${data.distance_feet.toLocaleString()} FT`;
            }
            return data.store_num;
        }

        const rawData = localStorage.getItem("webnexus_closest_store_id");
        if (rawData) {
            try {
                const storeIntel = JSON.parse(rawData);
                const ageInMinutes = (Date.now() - storeIntel.timestamp) / 1000 / 60;
                if (ageInMinutes < 30) {
                    intelStatusLine.style.visibility = "visible";
                    statusId.innerText = `#${storeIntel.num}`;
                    statusDist.innerText = "SIGNAL_LOCKED";
                    return storeIntel.num;
                }
            } catch (e) {}
        }
        
        if (localStorage.getItem("webnexus_gps_optin") === "granted") {
            intelStatusLine.style.visibility = "visible";
            statusId.innerText = "SEARCHING...";
            statusDist.innerText = "PULSING";
        }
        return null;
    },

    /**
     * FORM PAGE: Start the 5-second pulse for Intel UI
     */
    startIntelPulse() {
        if (this.intelInterval) clearInterval(this.intelInterval);
        this.intelInterval = setInterval(() => this.updateIntelUI(), 5000);
    }
};
