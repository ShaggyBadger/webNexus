function atgReviewQueueApp() {
  return {
    queue: [],
    showQueueColumn: true,
    selectedTicketId: null,
    selectedTicket: null,
    imageRotation: 0,
    panzoomInstance: null,
    panzoomStage: null,
    panzoomWheelHandler: null,
    fuelTypes: [],
    loadingQueue: false,
    saving: false,
    filters: {
      status: "ALL",
      storeNum: "",
      uploadedBy: "",
    },
    form: {
      storeNum: "",
      ticketTimestamp: "",
      notes: "",
      readings: [],
    },
    status: {
      type: "info",
      message: "",
    },

    init() {
      const fuelScript = document.getElementById("review-fuel-types-data");
      if (fuelScript?.textContent) {
        this.fuelTypes = JSON.parse(fuelScript.textContent);
      }
      this.loadQueue();
    },

    initializePanzoom() {
      this.destroyPanzoom();

      const stage = this.$refs.imageStage;
      const canvas = this.$refs.imageCanvas;
      if (!stage || !canvas || typeof Panzoom !== "function") {
        return;
      }

      const instance = Panzoom(canvas, {
        maxScale: 5,
        minScale: 1,
        step: 0.25,
        contain: "outside",
        cursor: "grab",
      });

      this.panzoomWheelHandler = (event) => instance.zoomWithWheel(event);
      stage.addEventListener("wheel", this.panzoomWheelHandler, {
        passive: false,
      });
      this.panzoomStage = stage;
      this.panzoomInstance = instance;
    },

    destroyPanzoom() {
      if (this.panzoomStage && this.panzoomWheelHandler) {
        this.panzoomStage.removeEventListener("wheel", this.panzoomWheelHandler);
      }
      this.panzoomStage = null;
      this.panzoomWheelHandler = null;

      if (this.panzoomInstance) {
        this.panzoomInstance.destroy();
        this.panzoomInstance = null;
      }
    },

    showStatus(message, type = "info") {
      this.status = { message, type };
    },

    statusClass() {
      if (this.status.type === "error") {
        return "border-danger text-danger bg-danger bg-opacity-10";
      }
      if (this.status.type === "success") {
        return "border-success text-success bg-success bg-opacity-10";
      }
      return "border-warning text-warning bg-warning bg-opacity-10";
    },

    toggleQueueColumn() {
      this.showQueueColumn = !this.showQueueColumn;
    },

    async fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      let payload = null;
      try {
        payload = await response.json();
      } catch (error) {
        payload = null;
      }

      if (!response.ok) {
        const baseMessage =
          payload?.error?.message || payload?.error || "Request failed.";
        const details = payload?.error?.details;
        const message =
          details && Object.keys(details).length > 0
            ? `${baseMessage} ${JSON.stringify(details)}`
            : baseMessage;
        throw new Error(message);
      }

      if (payload?.status === "success" && payload?.data !== undefined) {
        return payload.data;
      }
      return payload;
    },

    async loadQueue() {
      this.loadingQueue = true;
      try {
        const params = new URLSearchParams();
        if (this.filters.status && this.filters.status !== "ALL") {
          params.set("status", this.filters.status);
        }
        if (this.filters.storeNum.trim()) {
          params.set("store_num", this.filters.storeNum.trim());
        }
        if (this.filters.uploadedBy.trim()) {
          params.set("uploaded_by", this.filters.uploadedBy.trim());
        }

        const data = await this.fetchJson(`/atg/api/v1/review-queue/?${params.toString()}`);
        this.queue = data.tickets || [];
        if (this.queue.length > 0) {
          const exists = this.queue.some((item) => item.id === this.selectedTicketId);
          if (!exists) {
            await this.selectTicket(this.queue[0].id);
          }
        } else {
          this.selectedTicketId = null;
          this.selectedTicket = null;
          this.form.readings = [];
        }
      } catch (error) {
        this.showStatus(error.message, "error");
      } finally {
        this.loadingQueue = false;
      }
    },

    async selectTicket(ticketId) {
      this.selectedTicketId = ticketId;
      this.imageRotation = 0;
      this.destroyPanzoom();
      try {
        const data = await this.fetchJson(`/atg/api/v1/review-queue/${ticketId}/`);
        this.selectedTicket = data.ticket;
        this.form.storeNum = `${data.ticket.store_num ?? ""}`;
        this.form.ticketTimestamp = data.ticket.ticket_timestamp
          ? data.ticket.ticket_timestamp.slice(0, 16)
          : "";
        this.form.notes = data.ticket.notes || "";
        this.form.readings = (data.readings || []).map((reading) => ({
          tank_index: reading.tank_index ?? "",
          fuel_type: reading.fuel_type_id ?? "",
          volume: reading.volume ?? "",
          ullage: reading.ullage ?? "",
          height: reading.height ?? "",
          temp: reading.temp ?? "",
          water: reading.water ?? "",
          raw_line_text: reading.raw_line_text ?? "",
          confidence_score: reading.confidence_score ?? 1.0,
          is_user_corrected: true,
        }));
        if (this.form.readings.length === 0) {
          this.addReading();
        }
        this.$nextTick(() => {
          this.initializePanzoom();
        });
        this.showStatus("", "info");
      } catch (error) {
        this.showStatus(error.message, "error");
      }
    },

    rotateImageLeft() {
      this.imageRotation = (this.imageRotation - 90) % 360;
    },

    rotateImageRight() {
      this.imageRotation = (this.imageRotation + 90) % 360;
    },

    zoomInImage() {
      if (this.panzoomInstance) {
        this.panzoomInstance.zoomIn();
      }
    },

    zoomOutImage() {
      if (this.panzoomInstance) {
        this.panzoomInstance.zoomOut();
      }
    },

    resetImageView() {
      this.imageRotation = 0;
      if (this.panzoomInstance) {
        this.panzoomInstance.reset();
      }
    },

    addReading() {
      this.form.readings.push({
        tank_index: "",
        fuel_type: "",
        volume: "",
        ullage: "",
        height: "",
        temp: "",
        water: "",
        raw_line_text: "",
        confidence_score: 1.0,
        is_user_corrected: true,
      });
    },

    removeReading(index) {
      this.form.readings.splice(index, 1);
    },

    buildFinalizeReadings() {
      const normalized = [];
      const seenTankIndices = new Set();

      const isBlank = (reading) => {
        return (
          `${reading.tank_index ?? ""}`.trim() === "" &&
          `${reading.fuel_type ?? ""}`.trim() === "" &&
          `${reading.volume ?? ""}`.trim() === "" &&
          `${reading.ullage ?? ""}`.trim() === "" &&
          `${reading.height ?? ""}`.trim() === "" &&
          `${reading.temp ?? ""}`.trim() === "" &&
          `${reading.water ?? ""}`.trim() === ""
        );
      };

      for (const reading of this.form.readings) {
        if (isBlank(reading)) {
          continue;
        }

        const tankIndex = Number(reading.tank_index);
        const fuelType = Number(reading.fuel_type);
        const volume = Number(reading.volume);
        const ullage = Number(reading.ullage);
        const height = Number(reading.height);

        if (
          !tankIndex ||
          !fuelType ||
          Number.isNaN(volume) ||
          Number.isNaN(ullage) ||
          Number.isNaN(height)
        ) {
          throw new Error(
            "Each reading must include tank, fuel, volume, ullage, and height.",
          );
        }

        if (seenTankIndices.has(tankIndex)) {
          throw new Error(`Duplicate tank index ${tankIndex} detected.`);
        }
        seenTankIndices.add(tankIndex);

        const tempRaw = `${reading.temp ?? ""}`.trim();
        const waterRaw = `${reading.water ?? ""}`.trim();
        const tempValue = tempRaw === "" ? null : Number(tempRaw);
        const waterValue = waterRaw === "" ? null : Number(waterRaw);

        if (tempValue !== null && Number.isNaN(tempValue)) {
          throw new Error(`Temp must be numeric for tank ${tankIndex}.`);
        }
        if (waterValue !== null && Number.isNaN(waterValue)) {
          throw new Error(`Water must be numeric for tank ${tankIndex}.`);
        }

        normalized.push({
          tank_index: tankIndex,
          fuel_type: fuelType,
          volume,
          ullage,
          height,
          temp: tempValue,
          water: waterValue,
          raw_line_text: `${reading.raw_line_text ?? ""}`,
          confidence_score: 1.0,
          is_user_corrected: true,
        });
      }

      if (normalized.length === 0) {
        throw new Error("At least one non-empty reading is required.");
      }

      return normalized;
    },

    async finalizeTicket() {
      if (!this.selectedTicketId) {
        return;
      }

      let readings = [];
      try {
        readings = this.buildFinalizeReadings();
      } catch (error) {
        this.showStatus(error.message, "error");
        return;
      }

      this.saving = true;
      this.showStatus("Finalizing ticket...", "info");

      try {
        const payload = {
          store_num: `${this.form.storeNum ?? ""}`.trim(),
          ticket_timestamp: `${this.form.ticketTimestamp ?? ""}`.trim(),
          notes: `${this.form.notes ?? ""}`.trim(),
          readings,
        };

        await this.fetchJson(`/atg/api/v1/review-queue/${this.selectedTicketId}/finalize/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken":
              document.querySelector('meta[name="csrf-token"]')?.content || "",
          },
          body: JSON.stringify(payload),
        });

        this.showStatus("Ticket finalized successfully.", "success");
        await this.loadQueue();
      } catch (error) {
        this.showStatus(error.message, "error");
      } finally {
        this.saving = false;
      }
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("atgReviewQueueApp", atgReviewQueueApp);
});
