function missionlogApp() {
  return {
    view: "active",
    loading: true,
    submitting: false,
    showEntryForm: false,
    activeMission: null,
    missions: [],
    fuelTypes: [],
    autoCalculateTotalMiles: true,
    errorMessage: "",
    successMessage: "",
    agentLabel: "RECOGNIZING...",
    showModeConfirm: false,
    pendingMode: "",
    showUpgradeConfirm: false,
    showCompleteConfirm: false,
    form: {
      shift_start: "",
      hours_on_duty: "",
      hours_on_duty_not_driving: "",
      total_miles: "",
      start_miles: "",
      end_miles: "",
      notes: "",
      truck_fuel: { gallons: "", price_per_gallon: "" },
      deliveries: [],
      entry_type: "basic",
      total_gallons: "",
    },

    get entryType() {
      return this.form.entry_type;
    },
    set entryType(val) {
      this.form.entry_type = val;
    },

    async init() {
      await this.fetchAgentInfo();
      await this.loadFuelTypes();
      await this.refreshActiveMission();
      if (!this.form.deliveries.length) {
        this.addDelivery();
      }
    },

    resetForm() {
      this.form = {
        shift_start: "",
        hours_on_duty: "",
        hours_on_duty_not_driving: "",
        total_miles: "",
        start_miles: "",
        end_miles: "",
        notes: "",
        truck_fuel: { gallons: "", price_per_gallon: "" },
        deliveries: [],
        entry_type: "basic",
        total_gallons: "",
      };
      this.addDelivery();
      this.activeMission = null;
      this.autoCalculateTotalMiles = true;
      this.showEntryForm = false;
      this.showModeConfirm = false;
      this.pendingMode = "";
      this.showUpgradeConfirm = false;
      this.showCompleteConfirm = false;
    },

    beginNewEntry() {
      this.showEntryForm = true;
      this.errorMessage = "";
      this.successMessage = "";
      this.showCompleteConfirm = false;
      if (!this.form.shift_start) {
        this.form.shift_start = this.toDateTimeLocal(new Date().toISOString());
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    },

    toggleCompleteConfirm() {
      this.showCompleteConfirm = !this.showCompleteConfirm;
    },

    confirmCompleteMission() {
      this.showCompleteConfirm = false;
      this.submitMission(true);
    },

    confirmAndSetEntryType(newType) {
      if (this.form.entry_type === newType) {
        return;
      }
      if (this.activeMission) {
        return;
      }

      const startMiles = this.toNumeric(this.form.start_miles);
      const endMiles = this.toNumeric(this.form.end_miles);
      const hoursOnDuty = this.toNumeric(this.form.hours_on_duty);
      const hoursNotDriving = this.toNumeric(this.form.hours_on_duty_not_driving);
      const totalGallons = this.toNumeric(this.form.total_gallons);
      
      const hasDeliveries = this.form.deliveries.length > 0 && 
        (this.form.deliveries[0].store_number_or_riso !== "" || 
         (this.form.deliveries[0].fuel_entries && this.form.deliveries[0].fuel_entries.length > 0 && String(this.form.deliveries[0].fuel_entries[0].gallons || "").trim() !== ""));

      const isDirty = (hoursOnDuty !== null || hoursNotDriving !== null || totalGallons !== null || startMiles !== null || endMiles !== null || this.form.notes !== "" || hasDeliveries);

      if (isDirty) {
        this.pendingMode = newType;
        this.showModeConfirm = true;
      } else {
        this.form.entry_type = newType;
        this.showModeConfirm = false;
      }
    },

    executeModeSwitch() {
      const targetType = this.pendingMode;
      this.resetForm();
      this.form.entry_type = targetType;
      this.showModeConfirm = false;
      this.pendingMode = "";
      this.showEntryForm = true;
    },

    async executeUpgradeToAdvanced() {
      // If there's no saved mission yet, just flip the form mode locally.
      // There's nothing persisted on the server to upgrade.
      if (!this.activeMission) {
        this.form.entry_type = "advanced";
        this.showUpgradeConfirm = false;
        return;
      }

      this.submitting = true;
      this.errorMessage = "";
      this.successMessage = "";
      try {
        const endpoint = `/missionlog/api/missions/post-trip/${this.activeMission.id}/`;
        const payload = {
          ...this.buildPayload(false),
          entry_type: "advanced",
        };
        
        const data = await this.fetchJson(endpoint, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": this.getCsrfToken(),
          },
          body: JSON.stringify(payload),
        });

        if (data.mission) {
          this.activeMission = data.mission;
          this.hydrateFormFromMission(data.mission);
          this.successMessage = "Upgraded to Advanced mode. You can now log deliveries.";
        }
        this.showUpgradeConfirm = false;
      } catch (error) {
        console.error("MISSIONLOG_UPGRADE_FAILED", error);
        this.errorMessage = error.message;
      } finally {
        this.submitting = false;
      }
    },

    toNumeric(value) {
      if (value === undefined || value === null || String(value).trim() === "") {
        return null;
      }
      const parsed = Number(value);
      return Number.isNaN(parsed) ? null : parsed;
    },

    onMileageInput() {
      if (!this.autoCalculateTotalMiles) {
        return;
      }
      const start = this.toNumeric(this.form.start_miles);
      const end = this.toNumeric(this.form.end_miles);
      if (start === null || end === null) {
        this.form.total_miles = "";
        return;
      }
      this.form.total_miles = String(end - start);
    },

    onMileageModeToggle() {
      if (this.autoCalculateTotalMiles) {
        this.onMileageInput();
      }
    },

    getDefaultFuelTypeId() {
      if (!this.fuelTypes.length) {
        return "";
      }
      for (let i = 0; i < this.fuelTypes.length; i += 1) {
        if ((this.fuelTypes[i].name || "").toUpperCase() === "REGULAR") {
          return this.fuelTypes[i].id;
        }
      }
      return this.fuelTypes[0].id;
    },

    addDelivery() {
      this.form.deliveries.push({
        store_number_or_riso: "",
        storeValid: null,
        storeName: "",
        loading: false,
        debounceTimer: null,
        fuel_entries: [{ fuel_type_id: this.getDefaultFuelTypeId(), gallons: "" }],
      });
    },

    removeDelivery(index) {
      if (index < 0 || index >= this.form.deliveries.length) {
        return;
      }
      const delivery = this.form.deliveries[index];
      if (delivery.debounceTimer) {
        clearTimeout(delivery.debounceTimer);
      }
      this.form.deliveries.splice(index, 1);
      if (!this.form.deliveries.length) {
        this.addDelivery();
      }
    },

    addFuelEntry(deliveryIndex) {
      this.form.deliveries[deliveryIndex].fuel_entries.push({
        fuel_type_id: this.getDefaultFuelTypeId(),
        gallons: "",
      });
    },

    removeFuelEntry(deliveryIndex, fuelIndex) {
      const entries = this.form.deliveries[deliveryIndex].fuel_entries;
      entries.splice(fuelIndex, 1);
      if (!entries.length) {
        this.addFuelEntry(deliveryIndex);
      }
    },

    normalizePayload(raw) {
      if (raw && raw.status === "success" && raw.data !== undefined) {
        return raw.data;
      }
      return raw;
    },

    async fetchJson(url, options) {
      const response = await fetch(url, options || {});
      let raw = null;
      try {
        raw = await response.json();
      } catch (error) {
        raw = null;
      }

      const data = this.normalizePayload(raw);
      if (!response.ok) {
        const message =
          (data && data.error && data.error.message) ||
          (data && data.message) ||
          "MissionLog request failed.";
        throw new Error(message);
      }
      return data;
    },

    getCsrfToken() {
      const fromMeta = document.querySelector('meta[name="csrf-token"]');
      if (fromMeta && fromMeta.content) {
        return fromMeta.content;
      }
      const cookiePair = document.cookie
        .split(";")
        .map((item) => item.trim())
        .find((item) => item.startsWith("csrftoken="));
      return cookiePair ? decodeURIComponent(cookiePair.split("=")[1]) : "";
    },

    async fetchAgentInfo() {
      try {
        const data = await this.fetchJson("/missionlog/api/agent-info/");
        this.agentLabel = data.callsign || data.username || "UNKNOWN_AGENT";
      } catch (error) {
        console.warn("MISSIONLOG_AGENT_INFO_FAILED", error);
        this.agentLabel = "UNKNOWN_AGENT";
      }
    },

    async loadFuelTypes() {
      try {
        const data = await this.fetchJson("/missionlog/api/fuel-types/");
        this.fuelTypes = data.fuel_types || [];
      } catch (error) {
        console.error("MISSIONLOG_FUEL_TYPES_FAILED", error);
        this.errorMessage = error.message;
      }
    },

    hydrateFormFromMission(mission) {
      if (!mission) {
        return;
      }
      this.form.shift_start = this.toDateTimeLocal(mission.shift_start);
      this.form.hours_on_duty = mission.hours_on_duty != null ? String(mission.hours_on_duty) : "";
      this.form.hours_on_duty_not_driving =
        mission.hours_on_duty_not_driving != null
          ? String(mission.hours_on_duty_not_driving)
          : "";
      this.form.start_miles = mission.start_miles != null ? String(mission.start_miles) : "";
      this.form.end_miles = mission.end_miles != null ? String(mission.end_miles) : "";
      this.form.total_miles = mission.total_miles != null ? String(mission.total_miles) : "";
      this.form.notes = mission.notes || "";
      this.form.entry_type = mission.entry_type || "basic";
      this.form.total_gallons = mission.total_gallons != null ? String(mission.total_gallons) : "";

      if (mission.fuel_logs && mission.fuel_logs.length) {
        const fuel = mission.fuel_logs[0];
        this.form.truck_fuel = {
          gallons: fuel.gallons != null ? String(fuel.gallons) : "",
          price_per_gallon: fuel.price_per_gallon != null ? String(fuel.price_per_gallon) : "",
        };
      } else {
        this.form.truck_fuel = { gallons: "", price_per_gallon: "" };
      }

      const deliveries = [];
      const orders = mission.order_numbers || [];
      for (let i = 0; i < orders.length; i += 1) {
        const purchaseOrders = orders[i].purchase_orders || [];
        for (let p = 0; p < purchaseOrders.length; p += 1) {
          const loads = purchaseOrders[p].loads || [];
          for (let l = 0; l < loads.length; l += 1) {
            const load = loads[l];
            const storeKey = load.store_num != null ? String(load.store_num) : "";
            if (!storeKey) {
              continue;
            }
            let delivery = deliveries.find((item) => item.store_number_or_riso === storeKey);
            if (!delivery) {
              delivery = {
                store_number_or_riso: storeKey,
                storeValid: true,
                storeName: load.store_name || "",
                loading: false,
                debounceTimer: null,
                fuel_entries: [],
              };
              deliveries.push(delivery);
            }
            delivery.fuel_entries.push({
              fuel_type_id: load.fuel_type_id,
              gallons: load.gross_gal != null ? String(load.gross_gal) : "",
            });
          }
        }
      }

      this.form.deliveries = deliveries.length ? deliveries : [];
      if (!this.form.deliveries.length) {
        this.addDelivery();
      }

      const start = this.toNumeric(this.form.start_miles);
      const end = this.toNumeric(this.form.end_miles);
      const total = this.toNumeric(this.form.total_miles);
      if (start !== null && end !== null && total !== null) {
        this.autoCalculateTotalMiles = end - start === total;
      } else {
        this.autoCalculateTotalMiles = true;
      }
    },

    toDateTimeLocal(isoValue) {
      if (!isoValue) {
        return "";
      }
      const parsed = new Date(isoValue);
      if (Number.isNaN(parsed.getTime())) {
        return "";
      }
      const offsetMs = parsed.getTimezoneOffset() * 60000;
      return new Date(parsed.getTime() - offsetMs).toISOString().slice(0, 16);
    },

    async refreshActiveMission() {
      this.loading = true;
      this.errorMessage = "";
      this.successMessage = "";
      try {
        const data = await this.fetchJson("/missionlog/api/missions/active/");
        if (data.active) {
          this.activeMission = data.mission;
          this.hydrateFormFromMission(data.mission);
          this.showEntryForm = true;
        } else {
          this.resetForm();
          this.showEntryForm = false;
        }
      } catch (error) {
        console.error("MISSIONLOG_ACTIVE_MISSION_FETCH_FAILED", error);
        this.errorMessage = error.message;
      } finally {
        this.loading = false;
      }
    },

    buildPayload(isCompleted) {
      if (this.form.entry_type === "basic") {
        return {
          shift_start: this.form.shift_start,
          entry_type: "basic",
          total_gallons: this.toNumeric(this.form.total_gallons),
          hours_on_duty_not_driving: this.toNumeric(this.form.hours_on_duty_not_driving),
          is_completed: Boolean(isCompleted),
        };
      }

      const startMiles = this.toNumeric(this.form.start_miles);
      const endMiles = this.toNumeric(this.form.end_miles);
      const derivedTotalMiles =
        startMiles !== null && endMiles !== null ? endMiles - startMiles : null;
      const totalMiles = this.autoCalculateTotalMiles
        ? derivedTotalMiles
        : this.toNumeric(this.form.total_miles);

      const payload = {
        shift_start: this.form.shift_start,
        entry_type: this.form.entry_type,
        total_gallons: null,
        hours_on_duty: this.form.hours_on_duty || null,
        hours_on_duty_not_driving: this.form.hours_on_duty_not_driving || null,
        total_miles: totalMiles,
        start_miles: this.form.start_miles || null,
        end_miles: this.form.end_miles || null,
        notes: this.form.notes || "",
        is_completed: Boolean(isCompleted),
        truck_fuel: {
          gallons: this.form.truck_fuel.gallons || null,
          price_per_gallon: this.form.truck_fuel.price_per_gallon || null,
        },
        deliveries: this.form.deliveries
          .map((delivery) => ({
            store_number_or_riso: (delivery.store_number_or_riso || "").trim(),
            fuel_entries: (delivery.fuel_entries || [])
              .map((fuel) => ({
                fuel_type_id: fuel.fuel_type_id,
                gallons: fuel.gallons,
              }))
              .filter((fuel) => String(fuel.gallons || "").trim() !== ""),
          }))
          .filter((delivery) => {
            return (
              delivery.store_number_or_riso !== "" ||
              (delivery.fuel_entries && delivery.fuel_entries.length > 0)
            );
          }),
      };
      if (!payload.truck_fuel.gallons || !payload.truck_fuel.price_per_gallon) {
        payload.truck_fuel = null;
      }
      return payload;
    },

    async submitMission(isCompleted) {
      this.showCompleteConfirm = false;
      this.submitting = true;
      this.errorMessage = "";
      this.successMessage = "";
      try {
        const payload = this.buildPayload(isCompleted);
        const endpoint = this.activeMission
          ? `/missionlog/api/missions/post-trip/${this.activeMission.id}/`
          : "/missionlog/api/missions/post-trip/";
        const method = this.activeMission ? "PUT" : "POST";

        const data = await this.fetchJson(endpoint, {
          method,
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": this.getCsrfToken(),
          },
          body: JSON.stringify(payload),
        });

        if (data.mission && !data.mission.is_completed) {
          this.activeMission = data.mission;
          this.hydrateFormFromMission(data.mission);
          this.successMessage = "Progress saved. Mission state synced.";
        } else {
          this.resetForm();
          this.successMessage = "Mission completed and archived.";
        }

        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (error) {
        console.error("MISSIONLOG_SUBMIT_FAILED", error);
        this.errorMessage = error.message;
      } finally {
        this.submitting = false;
      }
    },

    async cancelActiveMission() {
      if (!this.activeMission) {
        return;
      }

      const missionId = this.activeMission.id;
      const confirmed = window.confirm(
        "Cancel the active mission? This will permanently delete it and reset MissionLog.",
      );
      if (!confirmed) {
        return;
      }

      this.submitting = true;
      this.errorMessage = "";
      this.successMessage = "";
      try {
        await this.fetchJson(`/missionlog/api/missions/${missionId}/`, {
          method: "DELETE",
          headers: {
            "X-CSRFToken": this.getCsrfToken(),
          },
        });

        this.resetForm();
        this.view = "active";
        this.missions = [];
        this.successMessage = `Mission #${missionId} cancelled and removed.`;
        window.scrollTo({ top: 0, behavior: "smooth" });
      } catch (error) {
        console.error("MISSIONLOG_CANCEL_FAILED", error);
        this.errorMessage = error.message;
      } finally {
        this.submitting = false;
      }
    },

    async validateStore(index) {
      const delivery = this.form.deliveries[index];
      if (!delivery) {
        return;
      }
      if (delivery.debounceTimer) {
        clearTimeout(delivery.debounceTimer);
      }
      const query = (delivery.store_number_or_riso || "").trim();
      if (!query) {
        delivery.storeValid = null;
        delivery.storeName = "";
        delivery.loading = false;
        return;
      }

      delivery.loading = true;
      delivery.storeValid = null;
      delivery.debounceTimer = window.setTimeout(async () => {
        try {
          const data = await this.fetchJson(`/missionlog/api/stores/validate/?q=${encodeURIComponent(query)}`);
          delivery.storeValid = Boolean(data.valid);
          delivery.storeName = data.store ? data.store.store_name : "";
        } catch (error) {
          console.warn("MISSIONLOG_STORE_VALIDATE_FAILED", error);
          delivery.storeValid = false;
          delivery.storeName = "";
        } finally {
          delivery.loading = false;
        }
      }, 500);
    },

    async loadMissionHistory() {
      this.loading = true;
      this.errorMessage = "";
      try {
        const data = await this.fetchJson("/missionlog/api/missions/");
        this.missions = data.missions || [];
      } catch (error) {
        console.error("MISSIONLOG_HISTORY_FETCH_FAILED", error);
        this.errorMessage = error.message;
      } finally {
        this.loading = false;
      }
    },

    async switchToHistory() {
      this.view = "history";
      if (!this.missions.length) {
        await this.loadMissionHistory();
      }
    },

    formatIso(value) {
      if (!value) {
        return "N/A";
      }
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) {
        return value;
      }
      return parsed.toLocaleString();
    },

    formatDateOnly(value) {
      if (!value) {
        return "N/A";
      }
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) {
        return value;
      }
      return parsed.toLocaleDateString();
    },

    formatGallonsPerHour(mission) {
      if (!mission) {
        return "N/A";
      }

      const dutyNotDriving = this.toNumeric(mission.hours_on_duty_not_driving);
      if (dutyNotDriving === null || dutyNotDriving <= 0) {
        return "N/A";
      }

      let totalGallons = this.toNumeric(mission.total_gallons);
      
      if (totalGallons === null || totalGallons === 0) {
        totalGallons = 0;
        const orders = mission.order_numbers || [];
        for (let i = 0; i < orders.length; i += 1) {
          const purchaseOrders = orders[i].purchase_orders || [];
          for (let p = 0; p < purchaseOrders.length; p += 1) {
            const loads = purchaseOrders[p].loads || [];
            for (let l = 0; l < loads.length; l += 1) {
              const gallons = this.toNumeric(loads[l].gross_gal);
              if (gallons !== null) {
                totalGallons += gallons;
              }
            }
          }
        }
      }

      const rate = totalGallons / dutyNotDriving;
      return `${rate.toFixed(1)} gal/hr`;
    },
  };
}

window.missionlogApp = missionlogApp;
