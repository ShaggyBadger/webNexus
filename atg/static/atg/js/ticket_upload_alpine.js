const DEFAULT_CAPACITY_VERIFICATION_REASON =
  "Capacity verified during Veeder-Root ticket review.";

function atgTicketUploadApp() {
  return {
    step: 1,
    searchQuery: "",
    selectedStore: null,
    loadingStore: false,
    loadingProfile: false,

    knownReadings: [],
    manualReadings: [],
    fuelTypes: [],

    notes: "",
    ticketTimestamp: "",

    statusMessage: "",
    statusType: "info",
    submitting: false,
    preflightRows: [],
    preflightReadings: [],
    overrideReasons: {},
    confirmedTokens: {},
    preflightCharts: {},

    init() {
      const fuelScript = document.getElementById("fuel-types-data");
      if (fuelScript?.textContent) {
        this.fuelTypes = JSON.parse(fuelScript.textContent);
      }
      this.$nextTick(() => this.$refs.storeNumberInput?.focus());
    },

    get canFetchStore() {
      return `${this.searchQuery ?? ""}`.trim().length > 0;
    },

    get hasStore() {
      return !!this.selectedStore;
    },

    get hasAnyReadings() {
      return this.knownReadings.length > 0 || this.manualReadings.length > 0;
    },

    clearStatus() {
      this.statusMessage = "";
    },

    resetPreflightState() {
      window.VeederPreflightSection.reset(this);
    },

    showStatus(message, type = "info") {
      this.statusMessage = message;
      this.statusType = type;
    },

    statusClass() {
      if (this.statusType === "error") {
        return "border-danger text-danger bg-danger bg-opacity-10";
      }
      if (this.statusType === "success") {
        return "border-success text-success bg-success bg-opacity-10";
      }
      return "border-warning text-warning bg-warning bg-opacity-10";
    },

    async lookupStore(query) {
      const response = await fetch(`/atg/api/v1/stores/?search=${encodeURIComponent(query)}`);
      if (!response.ok) {
        throw new Error("Store lookup failed.");
      }
      const results = await response.json();
      const normalizedQuery = `${query}`.trim().toLowerCase();
      return (
        results.find((item) => `${item.store_num}` === `${query}`) ||
        results.find((item) => `${item.store_pk}` === `${query}`) ||
        results.find((item) => `${item.name}`.toLowerCase() === normalizedQuery) ||
        results[0] ||
        null
      );
    },

    async fetchStoreByInput() {
      this.clearStatus();
      const q = `${this.searchQuery ?? ""}`.trim();
      if (this.loadingStore) {
        return;
      }
      if (!q) {
        this.showStatus("Enter a store or RISO number first.", "error");
        return;
      }

      this.loadingStore = true;
      this.showStatus("Fetching store form...", "info");
      try {
        const selected = await this.lookupStore(q);

        if (!selected) {
          throw new Error("No matching store found.");
        }

        await this.chooseStore(selected);
      } catch (error) {
        this.showStatus(error.message, "error");
      } finally {
        this.loadingStore = false;
      }
    },

    async chooseStore(store) {
      this.selectedStore = store;
      this.searchQuery = `${store.store_num ?? ""}`;
      this.step = 2;
      this.knownReadings = [];
      this.manualReadings = [];
      await this.loadStoreProfile();
    },

    clearStore() {
      this.selectedStore = null;
      this.searchQuery = "";
      this.knownReadings = [];
      this.manualReadings = [];
      this.resetPreflightState();
      this.step = 1;
      this.$nextTick(() => this.$refs.storeNumberInput?.focus());
    },

    normalizeClosestStore(closest) {
      return {
        store_pk: closest.store_pk,
        store_num: closest.store_num,
        name: closest.store_name,
        city: closest.city,
        state: closest.state,
      };
    },

    async fetchClosestStore() {
      if (this.loadingStore) {
        return;
      }

      if (!navigator.geolocation) {
        this.showStatus("Geolocation is not available in this browser.", "error");
        return;
      }

      this.loadingStore = true;
      this.showStatus("Detecting nearest store...", "info");
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          try {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            const response = await fetch(
              `/tankgauge/api/closest-store/?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`,
            );
            if (!response.ok) {
              throw new Error("Unable to detect nearest store.");
            }

            const payload = await response.json();
            const payloadData =
              payload && payload.status === "success" && payload.data
                ? payload.data
                : payload;
            const closest = payloadData?.results?.[0];
            if (!closest?.store_num) {
              throw new Error("No nearby store available.");
            }

            let resolvedStore = null;
            if (closest.store_pk) {
              resolvedStore = this.normalizeClosestStore(closest);
            } else {
              resolvedStore = await this.lookupStore(closest.store_num);
            }

            if (!resolvedStore) {
              throw new Error("Nearest store lookup failed.");
            }

            await this.chooseStore(resolvedStore);
            this.showStatus("Nearest store loaded.", "success");
          } catch (error) {
            this.showStatus(error.message, "error");
          } finally {
            this.loadingStore = false;
          }
        },
        () => {
          this.showStatus("Geolocation permission denied or unavailable.", "error");
          this.loadingStore = false;
        },
        {
          maximumAge: 60000,
          timeout: 10000,
          enableHighAccuracy: true,
        },
      );
    },

    async loadStoreProfile() {
      if (!this.selectedStore?.store_num) {
        return;
      }

      this.loadingProfile = true;
      try {
        const response = await fetch(
          `/atg/api/v1/stores/${this.selectedStore.store_num}/tank-profile/`,
        );
        if (!response.ok) {
          throw new Error("Failed to load tank profile");
        }
        const data = await response.json();
        this.knownReadings = (data.known_tanks || []).map((tank) => ({
          source: "known",
          profile_source: tank.source,
          verification_status: tank.verification_status,
          mapping_id: tank.mapping_id,
          tank_index: tank.tank_index,
          fuel_type_id: tank.fuel_type_id,
          fuel_type_name: tank.fuel_type_name,
          locked_identity: !!tank.locked_identity,
          baseline_capacity: tank.baseline_capacity,
          baseline_source: tank.baseline_source,
          physical_capacity_gallons_exact: tank.physical_capacity_gallons_exact ?? tank.capacity_gallons_exact,
          capacity_source: tank.capacity_source ?? tank.source,
          ullage_endpoint_percent_exact: tank.ullage_endpoint_percent_exact,
          basis_display_percent: tank.basis_display_percent,
          verification_warning: tank.verification_warning,
          capacity_verified: !!tank.capacity_verified,
          profile_version: tank.profile_version,
          capacity_verification_reason: DEFAULT_CAPACITY_VERIFICATION_REASON,
          capacity_verification_requested: false,
          max_depth: tank.max_depth,
          volume: "",
          height: "",
          ullage: "",
          expected_ullage: null,
        }));

        if (this.knownReadings.length === 0) {
          this.addManualReading();
          this.showStatus(
            "No known tank profile for this store yet. Use manual entries for this ticket.",
            "info",
          );
        } else {
          this.showStatus(`Store #${this.selectedStore.store_num} loaded.`, "success");
        }

        this.step = 2;
      } catch (error) {
        this.showStatus(error.message, "error");
      } finally {
        this.loadingProfile = false;
      }
    },

    addManualReading() {
      this.manualReadings.push({
        source: "manual",
        tank_index: "",
        fuel_type_id: "",
        volume: "",
        height: "",
        ullage: "",
        printed_physical_capacity_gallons: "",
      });
      this.step = Math.max(this.step, 2);
    },

    removeManualReading(idx) {
      this.manualReadings.splice(idx, 1);
    },

    get hasPreflightRows() {
      return this.preflightRows.length > 0;
    },

    canConfirmPreflight() {
      return window.VeederPreflightSection.canConfirm(this);
    },

    onKnownVolumeInput(reading) {
      const capacity = Number(reading.physical_capacity_gallons_exact ?? reading.baseline_capacity);
      if (!capacity || reading.volume === "") {
        reading.expected_ullage = null;
        reading.ullage = "";
        return;
      }

      const numericVolume = Number(reading.volume);
      if (Number.isNaN(numericVolume)) {
        return;
      }

      const basisPercent = Number(reading.ullage_endpoint_percent_exact);
      const endpointModifier = basisPercent > 0 ? basisPercent / 100 : 1;
      const expected = Number(
        (capacity * endpointModifier - numericVolume).toFixed(3),
      );
      reading.expected_ullage = expected;
      reading.ullage = expected;
    },

    async verifyCapacity(reading) {
      if (!reading.capacity_verification_requested) {
        return;
      }
      if (!reading.capacity_verification_reason?.trim()) {
        reading.capacity_verification_requested = false;
        this.showStatus("Enter a verification reason first.", "error");
        return;
      }
      try {
        const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
        const response = await fetch("/atg/api/v1/tank-profile/verify/", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          credentials: "same-origin",
          body: JSON.stringify({
            mapping_id: reading.mapping_id,
            physical_capacity_gallons: reading.physical_capacity_gallons_exact,
            ullage_endpoint_percent_exact: reading.ullage_endpoint_percent_exact || 100,
            profile_version: reading.profile_version,
            reason: reading.capacity_verification_reason,
          }),
        });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload?.error?.message || "Capacity verification failed.");
        }
        reading.capacity_verified = true;
        reading.verification_warning = null;
        reading.verification_status = "verified";
        reading.profile_version = payload.profile_version;
        this.showStatus("Tank capacity verified.", "success");
      } catch (error) {
        reading.capacity_verification_requested = false;
        this.showStatus(error.message, "error");
      }
    },

    buildPayloadReadings() {
      const readings = [];
      const seenIndices = new Set();

      const pushReading = (item, locked = false) => {
        const tankIndex = Number(item.tank_index);
        const fuelTypeId = Number(item.fuel_type_id);
        const volume = Number(item.volume);
        const ullage = Number(item.ullage);
        const height = Number(item.height);

        if (
          !tankIndex ||
          !fuelTypeId ||
          Number.isNaN(volume) ||
          Number.isNaN(ullage) ||
          Number.isNaN(height)
        ) {
          throw new Error("All readings require tank, fuel, volume, ullage, and height.");
        }
        if (tankIndex < 1) {
          throw new Error("Tank index must be a positive integer.");
        }
        if (seenIndices.has(tankIndex)) {
          throw new Error(`Duplicate tank index ${tankIndex} detected in this ticket.`);
        }
        seenIndices.add(tankIndex);

        readings.push({
          tank_index: tankIndex,
          fuel_type: fuelTypeId,
          volume,
          ullage,
          height,
          ...(item.printed_physical_capacity_gallons !== "" && item.printed_physical_capacity_gallons != null
            ? { printed_physical_capacity_gallons: Number(item.printed_physical_capacity_gallons) }
            : {}),
          is_user_corrected: true,
          confidence_score: 1.0,
          raw_line_text: locked
            ? `[LOCKED_PROFILE] expected_ullage=${item.expected_ullage ?? "n/a"}`
            : `[UNVERIFIED_PROFILE] expected_ullage=${item.expected_ullage ?? "n/a"}`,
        });
      };

      this.knownReadings.forEach((reading) => {
        if (
          reading.volume === "" &&
          reading.ullage === "" &&
          reading.height === ""
        ) {
          return;
        }
        pushReading(reading, !!reading.locked_identity);
      });

      this.manualReadings.forEach((reading) => {
        if (
          reading.volume === "" &&
          reading.ullage === "" &&
          reading.height === "" &&
          reading.tank_index === "" &&
          reading.fuel_type_id === ""
        ) {
          return;
        }
        pushReading(reading, false);
      });

      if (readings.length === 0) {
        throw new Error("At least one tank reading is required.");
      }

      return readings;
    },

    async submitTicket() {
      this.clearStatus();
      if (!this.selectedStore?.store_pk) {
        this.showStatus("Store selection is required.", "error");
        return;
      }

      let readings = [];
      try {
        readings = this.buildPayloadReadings();
      } catch (error) {
        this.showStatus(error.message, "error");
        return;
      }
      await window.VeederPreflightSection.runPreflight(this, readings);
    },

    async confirmAndTransmit() {
      await window.VeederPreflightSection.confirmAndTransmit(this);
    },

    cancelPreflightReview() {
      window.VeederPreflightSection.cancelReview(this);
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("atgTicketUploadApp", atgTicketUploadApp);
});
