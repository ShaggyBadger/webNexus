function atgReviewQueueApp() {
  return {
    queue: [],
    selectedTicketId: null,
    selectedTicket: null,
    imageRotation: 0,
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

    async fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      let payload = null;
      try {
        payload = await response.json();
      } catch (error) {
        payload = null;
      }

      if (!response.ok) {
        const message =
          payload?.error?.message || payload?.error || "Request failed.";
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

    async finalizeTicket() {
      if (!this.selectedTicketId) {
        return;
      }

      this.saving = true;
      this.showStatus("Finalizing ticket...", "info");

      try {
        const payload = {
          store_num: `${this.form.storeNum ?? ""}`.trim(),
          ticket_timestamp: `${this.form.ticketTimestamp ?? ""}`.trim(),
          notes: `${this.form.notes ?? ""}`.trim(),
          readings: this.form.readings,
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
