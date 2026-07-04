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
          max_depth: tank.max_depth,
          volume: "",
          height: "",
          ullage: "",
          expected_ullage: null,
          ullage_overridden: false,
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
      });
      this.step = Math.max(this.step, 2);
    },

    removeManualReading(idx) {
      this.manualReadings.splice(idx, 1);
    },

    onKnownVolumeInput(reading) {
      if (!reading.baseline_capacity || reading.volume === "") {
        reading.expected_ullage = null;
        return;
      }

      const numericVolume = Number(reading.volume);
      if (Number.isNaN(numericVolume)) {
        return;
      }

      const expected = Math.round(reading.baseline_capacity - numericVolume);
      reading.expected_ullage = expected;

      if (!reading.ullage_overridden) {
        reading.ullage = expected;
      }
    },

    markUllageOverridden(reading) {
      if (reading.source === "known") {
        reading.ullage_overridden = true;
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

      this.submitting = true;
      this.showStatus("Transmitting data package...", "info");

      const formData = new FormData();
      formData.append("store", this.selectedStore.store_pk);
      formData.append("notes", this.notes || "");
      if (this.ticketTimestamp) {
        formData.append("ticket_timestamp", this.ticketTimestamp);
      }
      formData.append("readings_json", JSON.stringify(readings));

      try {
        const response = await fetch("/atg/api/v1/tickets/", {
          method: "POST",
          headers: {
            "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
          },
          body: formData,
        });

        const rawText = await response.text();
        let result = {};
        if (rawText) {
          try {
            result = JSON.parse(rawText);
          } catch (error) {
            result = { error: rawText };
          }
        }

        if (!response.ok) {
          let errMsg = "Transmission failed.";
          if (typeof result.error === "string") {
            errMsg = result.error;
          } else if (result.error?.message) {
            errMsg = result.error.message;
          } else if (result.error) {
            errMsg = JSON.stringify(result.error);
          }
          throw new Error(errMsg);
        }

        this.showStatus("Mission complete. Ticket ingested successfully.", "success");
        setTimeout(() => {
          window.location.href = "/";
        }, 1400);
      } catch (error) {
        this.showStatus(error.message, "error");
      } finally {
        this.submitting = false;
      }
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("atgTicketUploadApp", atgTicketUploadApp);
});
