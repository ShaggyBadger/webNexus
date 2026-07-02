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

    get canFetchStore() {
      const raw = `${this.storeNumber ?? ""}`.trim();
      return raw.length > 0;
    },

    get canCalculate() {
      return (
        !!this.selectedTank &&
        this.inputs.deliveryGallons !== "" &&
        this.inputs.currentInches !== ""
      );
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
      this.inputs.deliveryGallons = "";
      this.inputs.currentInches = "";
      this.results = null;
      this.chartData = null;
      this.destroyChart();
    },

    clearMessages() {
      this.error = null;
      this.info = null;
    },

    changeStore() {
      this.storeNumber = "";
      this.clearMessages();
      this.resetStoreState();
      this.scrollToStep("storeStepCard");
      this.$nextTick(() => this.$refs.storeNumberInput?.focus());
    },

    destroyChart() {
      if (this.chartInstance) {
        this.chartInstance.destroy();
        this.chartInstance = null;
      }
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

        this.info = `Store #${this.storeData.store_num} loaded. Select a tank to continue.`;
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
      this.selectedTank = tank;
      this.step = 3;
      this.results = null;
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
        };

        this.results = await this.apiPost(
          "/tankgauge/api/calculate-tank/",
          payload,
          "Calculation failed.",
        );
        this.step = 4;
        this.info = "Calculation complete. Review results and warning banner.";
        this.scrollToStep("resultsStepCard");
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
          pointRadius: 7,
          pointHoverRadius: 10,
          order: 1,
        });
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
