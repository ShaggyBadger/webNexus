function tankGaugeApp() {
  return {
    step: 1,
    storeNumber: "",
    storeData: null,
    tanks: [],
    selectedTank: null,
    inputs: {
      deliveryGallons: "",
      currentInches: "",
    },
    results: null,
    selectedDisplayMode: "MATHEMATICAL",
    activeProfileKey: null,
    chartData: null,
    chartInstance: null,
    loading: {
      store: false,
      calculate: false,
      chart: false,
    },
    error: null,
    info: null,
    csrfToken: document.querySelector('meta[name="csrf-token"]')?.content || "",
    quickCapture: {
      submitting: false,
      statusType: "info",
      statusMessage: "",
      maxUploadSizeBytes: 12 * 1024 * 1024,
      allowedMimeTypes: ["image/jpeg", "image/png", "image/webp", "image/heic"],
    },

    get canFetchStore() {
      const raw = `${this.storeNumber ?? ""}`.trim();
      return raw.length > 0;
    },

    get canCalculate() {
      return (
        !!this.selectedTank &&
        `${this.inputs.deliveryGallons}`.trim() !== "" &&
        `${this.inputs.currentInches}`.trim() !== ""
      );
    },

    get activeProfile() {
      if (!this.results || !this.results.profiles) {
        return null;
      }
      return this.results.profiles[this.activeProfileKey] || null;
    },

    get hasMultipleProfiles() {
      if (!this.results || !this.results.profiles) {
        return false;
      }
      return Boolean(this.results.profiles.OFFICIAL && this.results.profiles.MATHEMATICAL);
    },

    get resolvedDisplayMode() {
      if (!this.selectedTank) {
        return "MATHEMATICAL";
      }
      if (this.isModeAvailable(this.selectedDisplayMode)) {
        return this.selectedDisplayMode;
      }
      if (this.isModeAvailable("MATHEMATICAL")) {
        return "MATHEMATICAL";
      }
      return "OFFICIAL";
    },

    get selectedLimits() {
      if (!this.selectedTank) {
        return null;
      }
      if (this.results?.active_profile?.capacity) {
        return this.results.active_profile.capacity;
      }
      const limitsByMode = this.selectedTank.limits_by_mode || {};
      return limitsByMode[this.resolvedDisplayMode] || this.selectedTank.limits || null;
    },

    get selectedLimitWarnings() {
      return this.selectedLimits?.warnings || [];
    },

    get activeProfileWarnings() {
      return this.activeProfile?.warnings || [];
    },

    get chartTableRows() {
      const officialChart = this.chartData?.series?.official_chart || [];
      const generatedCurve = this.chartData?.series?.generated_curve || [];
      if (officialChart.length === 0 && generatedCurve.length === 0) {
        return [];
      }

      const officialByInches = new Map(
        officialChart.map((point) => [Number(point.inches), Number(point.gallons)]),
      );
      const veederByInches = new Map(
        generatedCurve.map((point) => [Number(point.inches), Number(point.gallons)]),
      );

      const allInches = Array.from(
        new Set([...officialByInches.keys(), ...veederByInches.keys()]),
      ).sort((left, right) => left - right);

      return allInches.map((inches) => {
        const officialGallons = officialByInches.has(inches)
          ? officialByInches.get(inches)
          : null;
        const veederGallons = veederByInches.has(inches) ? veederByInches.get(inches) : null;

        let deltaGallons = null;
        let deltaPercent = null;
        if (officialGallons !== null && veederGallons !== null) {
          deltaGallons = veederGallons - officialGallons;
          if (officialGallons !== 0) {
            deltaPercent = (deltaGallons / officialGallons) * 100;
          }
        }

        return {
          inches,
          officialGallons,
          veederGallons,
          deltaGallons,
          deltaPercent,
        };
      });
    },

    get activeModeReason() {
      const selectedAvailability = this.getModeAvailability(this.selectedDisplayMode);
      if (!selectedAvailability) {
        return null;
      }
      return selectedAvailability.available ? null : selectedAvailability.reason;
    },

    get prefersReducedMotion() {
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    },

    scrollToStep(stepRef) {
      this.$nextTick(() => {
        const target = this.$refs[stepRef];
        if (!target) {
          return;
        }

        target.scrollIntoView({
          behavior: this.prefersReducedMotion ? "auto" : "smooth",
          block: "start",
        });
      });
    },

    resetStoreState() {
      this.step = 1;
      this.storeData = null;
      this.tanks = [];
      this.resetTankState();
    },

    resetTankState() {
      this.selectedTank = null;
      this.selectedDisplayMode = "MATHEMATICAL";
      this.inputs.deliveryGallons = "";
      this.inputs.currentInches = "";
      this.results = null;
      this.activeProfileKey = null;
      this.chartData = null;
      this.destroyChart();
    },

    preferredModeForTank(tank) {
      const availableModes = tank?.available_modes || [];
      const hasMath = availableModes.some(
        (item) => item.mode === "MATHEMATICAL" && item.available,
      );
      if (hasMath) {
        return "MATHEMATICAL";
      }
      return "OFFICIAL";
    },

    init() {
      if (!Array.isArray(window.__webnexusFeedbackProviders)) {
        window.__webnexusFeedbackProviders = [];
      }
      this.feedbackProvider = () => ({ tankgauge: this.feedbackMetadata() });
      window.__webnexusFeedbackProviders.push(this.feedbackProvider);

      this.feedbackMetadataListener = (event) => {
        if (!event || !event.detail) {
          return;
        }
        event.detail.metadata = {
          ...(event.detail.metadata || {}),
          tankgauge: this.feedbackMetadata(),
        };
      };
      window.addEventListener("feedback-request-metadata", this.feedbackMetadataListener);
      this.$nextTick(() => this.$refs.storeNumberInput?.focus());
    },

    feedbackMetadata() {
      const officialPoints = this.chartData?.series?.official_chart?.length || 0;
      const generatedPoints = this.chartData?.series?.generated_curve?.length || 0;
      const scatterPoints = this.chartData?.series?.scatter_points?.length || 0;
      return {
        step: this.step,
        store_number_input: this.storeNumber,
        store_data: this.storeData,
        selected_tank: this.selectedTank,
        input_values: {
          delivery_gallons: this.inputs.deliveryGallons,
          current_inches: this.inputs.currentInches,
        },
        calculation_results: this.results,
        selected_display_mode: this.selectedDisplayMode,
        chart_summary: {
          official_points: officialPoints,
          generated_points: generatedPoints,
          veeder_points: scatterPoints,
        },
      };
    },

    clearMessages() {
      this.error = null;
      this.info = null;
    },

    triggerQuickCapturePicker() {
      if (this.quickCapture.submitting) {
        return;
      }
      this.quickCapture.statusMessage = "";
      this.$refs.quickCaptureImageInput?.click();
    },

    async onQuickCaptureFileChange(event) {
      const selectedFile = event.target?.files?.[0] || null;
      if (!selectedFile) {
        return;
      }
      this.quickCapture.statusMessage = "";
      await this.submitQuickCapture(selectedFile);
      if (event.target) {
        event.target.value = "";
      }
    },

    showQuickCaptureStatus(message, type = "info") {
      this.quickCapture.statusMessage = message;
      this.quickCapture.statusType = type;
    },

    quickCaptureStatusClass() {
      if (this.quickCapture.statusType === "error") {
        return "border-danger text-danger bg-danger bg-opacity-10";
      }
      if (this.quickCapture.statusType === "success") {
        return "border-success text-success bg-success bg-opacity-10";
      }
      return "border-warning text-warning bg-warning bg-opacity-10";
    },

    validateQuickCaptureFile(file) {
      if (!file) {
        throw new Error("Ticket image is required.");
      }

      if (file.size > this.quickCapture.maxUploadSizeBytes) {
        const maxMb = Math.floor(this.quickCapture.maxUploadSizeBytes / (1024 * 1024));
        throw new Error(`Ticket image exceeds ${maxMb}MB. Compress and retry.`);
      }

      if (file.type && !this.quickCapture.allowedMimeTypes.includes(file.type)) {
        throw new Error("Unsupported image type. Use JPEG, PNG, WEBP, or HEIC.");
      }
    },

    resolveQuickCaptureStoreContext() {
      const storeNum = `${this.storeData?.store_num ?? this.storeNumber ?? ""}`.trim();
      const risoNum = `${this.storeData?.riso_num ?? ""}`.trim();
      return { storeNum, risoNum };
    },

    async submitQuickCapture(file) {
      if (this.quickCapture.submitting) {
        return;
      }

      try {
        this.validateQuickCaptureFile(file);
      } catch (error) {
        this.showQuickCaptureStatus(error.message, "error");
        return;
      }

      this.quickCapture.submitting = true;
      this.showQuickCaptureStatus("Uploading ticket image...", "info");

      const payload = new FormData();
      payload.append("image", file);

      const { storeNum, risoNum } = this.resolveQuickCaptureStoreContext();

      if (storeNum) {
        payload.append("store_num", storeNum);
      }
      if (risoNum) {
        payload.append("riso_num", risoNum);
      }
      payload.append("ticket_timestamp", new Date().toISOString());

      try {
        const response = await fetch("/atg/api/v1/tickets/quick-capture/", {
          method: "POST",
          headers: {
            "X-CSRFToken": this.csrfToken,
          },
          body: payload,
        });

        let raw = null;
        try {
          raw = await response.json();
        } catch (error) {
          raw = null;
        }

        if (!response.ok) {
          throw new Error(this.extractErrorMessage(raw, "Unable to submit ticket image."));
        }

        const data = this.extractSuccessData(raw);
        const ticketId = data?.ticket_id || "UNKNOWN";
        this.showQuickCaptureStatus(`Ticket submitted. Queue ID: ${ticketId}`, "success");
      } catch (error) {
        this.showQuickCaptureStatus(error.message, "error");
      } finally {
        this.quickCapture.submitting = false;
      }
    },

    changeStore() {
      this.storeNumber = "";
      this.clearMessages();
      this.resetStoreState();
      this.scrollToStep("storeStepCard");
      this.$nextTick(() => this.$refs.storeNumberInput?.focus());
    },

    getModeAvailability(mode) {
      const availableModes = this.results?.available_modes || this.selectedTank?.available_modes || [];
      return availableModes.find((item) => item.mode === mode) || null;
    },

    isModeAvailable(mode) {
      const modeAvailability = this.getModeAvailability(mode);
      return Boolean(modeAvailability && modeAvailability.available);
    },

    async setDisplayMode(mode) {
      if (!this.isModeAvailable(mode)) {
        return;
      }
      if (this.selectedDisplayMode === mode) {
        return;
      }

      this.selectedDisplayMode = mode;
      this.activeProfileKey = this.resolvedDisplayMode;

      if (this.canCalculate && !this.loading.calculate) {
        await this.calculateTelemetry();
      }
    },

    destroyChart() {
      if (this.chartInstance) {
        this.chartInstance.destroy();
        this.chartInstance = null;
      }
    },

    buildReadingDotDataset() {
      const profile = this.activeProfile;
      if (!profile) {
        return null;
      }
      if (profile.initial_inches == null || profile.initial_gallons == null) {
        return null;
      }
      return {
        label: "Current Reading",
        data: [{ x: profile.initial_inches, y: profile.initial_gallons }],
        backgroundColor: "#50fa7b",
        borderColor: "#ffffff",
        borderWidth: 2,
        showLine: false,
        pointRadius: 6,
        pointHoverRadius: 9,
        order: 0,
      };
    },

    formatChartGallons(value) {
      if (value === null || value === undefined || Number.isNaN(value)) {
        return "-";
      }
      return Number(value).toFixed(1);
    },

    formatDeltaCell(row) {
      if (row.deltaGallons === null || row.deltaGallons === undefined) {
        return "-";
      }
      const gallons = `${row.deltaGallons >= 0 ? "+" : ""}${Number(row.deltaGallons).toFixed(1)} gal`;
      if (row.deltaPercent === null || row.deltaPercent === undefined) {
        return gallons;
      }
      const pct = `${row.deltaPercent >= 0 ? "+" : ""}${Number(row.deltaPercent).toFixed(1)}%`;
      return `${gallons} (${pct})`;
    },

    deltaClass(row) {
      if (row.deltaGallons === null || row.deltaGallons === undefined) {
        return "text-muted-custom";
      }
      if (row.deltaGallons > 0) {
        return "text-tactical-warning";
      }
      if (row.deltaGallons < 0) {
        return "text-info";
      }
      return "text-muted-custom";
    },

    async apiGet(url, fallbackMessage) {
      const response = await fetch(url);
      let data = null;
      try {
        data = await response.json();
      } catch (error) {
        data = null;
      }

      if (!response.ok) {
        throw new Error(this.extractErrorMessage(data, fallbackMessage));
      }
      return this.extractSuccessData(data);
    },

    async apiPost(url, payload, fallbackMessage) {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": this.csrfToken,
        },
        body: JSON.stringify(payload),
      });

      let data = null;
      try {
        data = await response.json();
      } catch (error) {
        data = null;
      }

      if (!response.ok) {
        throw new Error(this.extractErrorMessage(data, fallbackMessage));
      }
      return this.extractSuccessData(data);
    },

    extractSuccessData(data) {
      if (data && data.status === "success" && data.data !== undefined) {
        return data.data;
      }
      return data;
    },

    extractErrorMessage(data, fallbackMessage) {
      if (!data) {
        return fallbackMessage;
      }

      if (typeof data.error === "string") {
        return data.error;
      }

      if (data.error && typeof data.error.message === "string") {
        return data.error.message;
      }

      return fallbackMessage;
    },

    async fetchStoreTanks() {
      if (!this.canFetchStore || this.loading.store) {
        return;
      }

      this.loading.store = true;
      this.clearMessages();
      this.resetStoreState();
      this.info = "Loading store data...";

      try {
        const normalizedStoreNumber = `${this.storeNumber}`.trim();
        this.storeNumber = normalizedStoreNumber;
        const data = await this.apiGet(
          `/tankgauge/api/stores/${normalizedStoreNumber}/tanks/`,
          "Store not found or unavailable.",
        );
        this.storeData = data.store;
        this.tanks = (data.tanks || []).slice().sort((a, b) => {
          const left = a.tank_index || 999;
          const right = b.tank_index || 999;
          return left - right;
        });

        if (this.tanks.length === 0) {
          this.error = "No tanks are mapped for this store.";
          this.info = null;
          return;
        }

        const primaryId = this.storeData.store_num || this.storeData.riso_num;
        this.info = `Store ${primaryId} loaded. Select a tank to continue.`;
        this.step = 2;
        this.scrollToStep("tankStepCard");

        if (this.tanks.length === 1) {
          this.info = "One tank found. Auto-selected for faster entry.";
          await this.selectTank(this.tanks[0]);
        }
      } catch (error) {
        this.error = error.message;
        this.info = null;
      } finally {
        this.loading.store = false;
      }
    },

    async fetchClosestStore() {
      if (!navigator.geolocation || this.loading.store) {
        this.error = "Geolocation is not available in this browser.";
        return;
      }

      this.clearMessages();
      this.info = "Detecting your location...";
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          this.loading.store = true;
          try {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            const data = await this.apiGet(
              `/tankgauge/api/closest-store/?lat=${lat}&lon=${lon}`,
              "Unable to locate nearest store.",
            );

            if (!data.results || data.results.length === 0) {
              throw new Error("No nearby stores found.");
            }

            this.storeNumber = data.results[0].store_num;
            this.loading.store = false;
            await this.fetchStoreTanks();
          } catch (error) {
            this.error = error.message;
            this.info = null;
          } finally {
            this.loading.store = false;
          }
        },
        () => {
          this.error = "Geolocation permission denied or unavailable.";
          this.info = null;
        },
      );
    },

    async selectTank(tank) {
      const switchingTanks = this.selectedTank && this.selectedTank.id !== tank.id;
      if (switchingTanks) {
        this.inputs.deliveryGallons = "";
        this.inputs.currentInches = "";
        this.results = null;
        this.activeProfileKey = null;
      }
      this.selectedTank = tank;
      this.selectedDisplayMode = this.preferredModeForTank(tank);
      this.activeProfileKey = this.resolvedDisplayMode;
      this.step = 3;
      this.info = `Tank ${tank.tank_index || "?"} selected. Enter delivery telemetry.`;
      this.scrollToStep("inputStepCard");
      this.$nextTick(() => this.$refs.deliveryGallonsInput?.focus());
      await this.fetchChartData();
    },

    async calculateTelemetry() {
      if (!this.canCalculate || this.loading.calculate) {
        return;
      }

      this.loading.calculate = true;
      this.clearMessages();
      this.info = "Running telemetry calculation...";

      try {
        const payload = {
          store_id: this.storeData.store_num,
          fuel_type: this.selectedTank.fuel_type,
          tank_id: this.selectedTank.id,
          tank_index: this.selectedTank.tank_index,
          current_inches: parseFloat(this.inputs.currentInches),
          delivery_gallons: parseFloat(this.inputs.deliveryGallons),
          display_mode: this.selectedDisplayMode,
        };

        this.results = await this.apiPost(
          "/tankgauge/api/calculate-tank/",
          payload,
          "Calculation failed.",
        );
        if (this.results.status === "SUCCESS") {
          this.activeProfileKey = this.results.mode;
        } else {
          this.activeProfileKey = null;
        }
        this.step = 4;
        this.info = "Calculation complete. Review tank fill projection.";
        this.scrollToStep("resultsStepCard");
        this.renderChart();
      } catch (error) {
        this.error = error.message;
        this.info = null;
      } finally {
        this.loading.calculate = false;
      }
    },

    async fetchChartData() {
      if (!this.selectedTank || this.loading.chart) {
        return;
      }

      this.loading.chart = true;
      this.error = null;

      try {
        this.chartData = await this.apiGet(
          `/tankgauge/api/tanks/${this.selectedTank.id}/chart-data/`,
          "Failed to fetch chart data.",
        );
        this.renderChart();
      } catch (error) {
        this.error = error.message;
      } finally {
        this.loading.chart = false;
      }
    },

    renderChart() {
      const canvas = document.getElementById("tankChart");
      if (!canvas || !this.chartData?.series) {
        return;
      }

      this.destroyChart();

      const datasets = [];
      const officialChart = this.chartData.series.official_chart || [];
      const generatedCurve = this.chartData.series.generated_curve || [];
      const scatterPoints = this.chartData.series.scatter_points || [];

      if (officialChart.length > 0) {
        datasets.push({
          label: "Official Tank Chart",
          data: officialChart.map((point) => ({
            x: point.inches,
            y: point.gallons,
          })),
          borderColor: "#a0aec0",
          backgroundColor: "transparent",
          borderWidth: 4,
          fill: false,
          showLine: true,
          pointRadius: 0,
          tension: 0.3,
          order: 3,
        });
      }

      if (generatedCurve.length > 0) {
        datasets.push({
          label: "Generated Curve (Math)",
          data: generatedCurve.map((point) => ({
            x: point.inches,
            y: point.gallons,
          })),
          borderColor: "#ffb86c",
          backgroundColor: "transparent",
          borderWidth: 2,
          borderDash: [8, 4],
          fill: false,
          showLine: true,
          pointRadius: 0,
          tension: 0.3,
          order: 2,
        });
      }

      if (scatterPoints.length > 0) {
        datasets.push({
          label: "Veeder-Root Readings",
          data: scatterPoints.map((point) => ({
            x: point.inches,
            y: point.gallons,
          })),
          backgroundColor: "#e94560",
          borderColor: "#ffffff",
          borderWidth: 1.5,
          showLine: false,
          pointRadius: 4,
          pointHoverRadius: 6,
          order: 1,
        });
      }

      const readingDataset = this.buildReadingDotDataset();
      if (readingDataset) {
        datasets.push(readingDataset);
      }

      this.chartInstance = new Chart(canvas, {
        type: "scatter",
        data: { datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              type: "linear",
              title: { display: true, text: "Depth (Inches)", color: "#a0aec0" },
              grid: { color: "#2a2e33" },
              ticks: { color: "#a0aec0" },
            },
            y: {
              title: {
                display: true,
                text: "Volume (Gallons)",
                color: "#a0aec0",
              },
              grid: { color: "#2a2e33" },
              ticks: { color: "#a0aec0" },
            },
          },
          plugins: {
            legend: { labels: { color: "#f8f9fa" } },
            tooltip: {
              callbacks: {
                label: (ctx) =>
                  `${ctx.dataset.label}: ${ctx.parsed.x}" / ${ctx.parsed.y} Gal`,
              },
            },
          },
        },
      });
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("tankGaugeApp", tankGaugeApp);
});
