/**
 * TankGauge Delivery Intel Logic
 */

const TankGaugeIntel = {
    calcUrl: '',
    storeId: '',
    isPreset: false,

    init(config) {
        this.calcUrl = config.calcUrl;
        this.storeId = config.storeId;
        this.isPreset = config.isPreset || false;

        document.addEventListener("DOMContentLoaded", () => {
            this.bindCalcButtons();
            this.bindFormPresets();
        });
    },

    bindCalcButtons() {
        const calcButtons = document.querySelectorAll(".btn-ajax-calculate");
        calcButtons.forEach(btn => {
            btn.addEventListener("click", () => this.executeCalculation(btn));
        });
    },

    async executeCalculation(btn) {
        const card = btn.closest(".tactical-card");
        const fuelType = card.dataset.fuelType;
        const deliveryInput = card.querySelector('input[name*="delivery_gallons"]');
        const inchesInput = card.querySelector('input[name*="current_inches"]');
        
        const deliveryValue = deliveryInput.value.trim();
        const inchesValue = inchesInput.value.trim();
        const maxDepth = parseFloat(card.dataset.maxDepth);

        // 1. Current Inches Validation
        if (inchesValue === "") {
            alert("OPERATIONAL_ERROR: CURRENT_INCHES REQUIRED");
            return;
        }
        
        // Strict number check (allows decimals, no letters)
        if (!/^\d*\.?\d+$/.test(inchesValue)) {
            alert("PARAMETER_ERROR: CURRENT_INCHES MUST BE A POSITIVE NUMBER.");
            return;
        }

        const currentInches = parseFloat(inchesValue);
        if (currentInches < 0 || currentInches > maxDepth) {
            alert(`PARAMETER_ERROR: DEPTH MUST BE BETWEEN 0 AND ${maxDepth}.`);
            return;
        }

        // 2. Delivery Gallons Validation (must be integer >= 0)
        let deliveryGallons = 0;
        if (deliveryValue !== "") {
            if (!/^\d+$/.test(deliveryValue)) {
                alert("PARAMETER_ERROR: DELIVERY_GALLONS MUST BE A POSITIVE INTEGER (NO DECIMALS/STRINGS).");
                return;
            }
            deliveryGallons = parseInt(deliveryValue);
        }

        const originalText = btn.innerText;
        btn.innerHTML = '<i class="fas fa-microchip fa-spin me-2"></i>PROCESSING...';
        btn.disabled = true;

        try {
            const formData = new FormData();
            formData.append("store_id", this.storeId);
            formData.append("fuel_type", fuelType);
            formData.append("current_inches", currentInches);
            formData.append("delivery_gallons", deliveryGallons);

            const response = await fetch(this.calcUrl, {
                method: "POST",
                body: formData,
                headers: {
                    "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.updateResultsUI(card, data);
            } else {
                const err = await response.json();
                alert("CALCULATION_ERROR: " + (err.error || "UNKNOWN"));
            }
        } catch (e) {
            console.error(e);
            alert("SYSTEM_CRITICAL_ERROR: API_COMMUNICATION_FAILED");
        } finally {
            btn.innerText = originalText;
            btn.disabled = false;
        }
    },

    updateResultsUI(card, data) {
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
        
        const warningBox = resultsArea.querySelector(".no-fit-warning");
        if (warningBox) warningBox.style.display = data.no_fit_warning ? "block" : "none";
        
        resultsArea.style.display = "block";
        resultsArea.style.opacity = "0";
        setTimeout(() => {
            resultsArea.style.transition = "opacity 0.5s ease";
            resultsArea.style.opacity = "1";
        }, 10);
    },

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
                    const data = await TacticalGPS.pulse();
                    storeInput.value = data.store_num;
                    if (window.updateIntelUI) window.updateIntelUI(data);
                } catch (err) {
                    console.warn("Fresh Pulse Failed:", err);
                    if (window.updateIntelUI) {
                        const storedId = window.updateIntelUI();
                        if (storedId) storeInput.value = storedId;
                        else alert("OPERATIONAL ERROR: No GPS Signal Locked.");
                    }
                } finally {
                    lockNearestBtn.innerHTML = originalText;
                    lockNearestBtn.disabled = false;
                }
            });
        }

        if (preset711Btn) {
            preset711Btn.addEventListener('click', () => {
                storeInput.value = "7-11_STD";
            });
        }
    }
};
