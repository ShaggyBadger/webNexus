import { IntelMap } from "./intel_map.js";

function buildHints() {
  return {
    PERSONAL: "* YOU ARE VIEWING YOUR PRIVATE OBSERVATIONS.",
    DEFAULT: "* VIEWING SHARED LAYER. CREATE YOUR OWN TO OVERRIDE.",
    PUBLIC: "* AUTHENTICATION REQUIRED TO VIEW PERSONAL LAYERS.",
  };
}

function siteLocationDetailApp() {
  return {
    intelLayer: "DEFAULT",
    mapMode: "STANDARD",
    mapController: null,
    selectedTank: null,
    tankProfileData: null,
    tankProfileLoading: false,
    tankProfileError: "",
    tankChartInstance: null,

    get tankDisplayTitle() {
      if (!this.selectedTank) {
        return "--";
      }
      return `T${this.selectedTank.tankIndex} ${this.selectedTank.fuelType}`;
    },

    get tankStats() {
      const series = this.tankProfileData && this.tankProfileData.series
        ? this.tankProfileData.series
        : {};
      const official = series.official_chart || [];
      const generated = series.generated_curve || [];
      const scatter = series.scatter_points || [];
      const allPoints = [...official, ...generated, ...scatter];

      const maxDepthFromData = allPoints.length
        ? Math.max(...allPoints.map((point) => Number(point.inches) || 0))
        : null;
      const maxGallonsFromData = allPoints.length
        ? Math.max(...allPoints.map((point) => Number(point.gallons) || 0))
        : null;

      const maxDepth = this.selectedTank?.maxDepth ?? maxDepthFromData;
      const maxGallons = this.selectedTank?.capacity ?? maxGallonsFromData;

      return {
        maxDepth,
        maxGallons,
        ninetyPercentGallons: maxGallons != null ? maxGallons * 0.9 : null,
        veederEntries: scatter.length,
        officialPoints: official.length,
        generatedPoints: generated.length,
      };
    },

    get intelHint() {
      const hints = buildHints();
      if (this.intelLayer === "PERSONAL") {
        return hints.PERSONAL;
      }
      return this.$root.dataset.initialIntelMode === "PUBLIC"
        ? hints.PUBLIC
        : hints.DEFAULT;
    },

    init() {
      const initialMode = this.$root.dataset.initialIntelMode || "DEFAULT";
      this.intelLayer = initialMode === "PERSONAL" ? "PERSONAL" : "DEFAULT";
      this.initMap();
      this.bindSketchModal();
      this.autoSelectFirstTank();
    },

    autoSelectFirstTank() {
      this.$nextTick(() => {
        const firstTankButton = this.$root.querySelector(".tank-config-btn");
        if (firstTankButton) {
          firstTankButton.click();
        }
      });
    },

    async fetchJson(url) {
      const response = await fetch(url);
      let raw = null;
      try {
        raw = await response.json();
      } catch (error) {
        raw = null;
      }

      const payload = raw && raw.status === "success" && raw.data ? raw.data : raw;
      if (!response.ok) {
        const message = payload?.error?.message || payload?.error || "Request failed.";
        throw new Error(message);
      }
      return payload;
    },

    async selectTank(tank) {
      this.selectedTank = tank;
      this.tankProfileData = null;
      this.tankProfileError = "";
      this.destroyTankChart();
      await this.loadTankProfile();
    },

    async loadTankProfile() {
      if (!this.selectedTank || !this.selectedTank.id) {
        return;
      }

      this.tankProfileLoading = true;
      this.tankProfileError = "";
      try {
        const data = await this.fetchJson(
          `/tankgauge/api/tanks/${this.selectedTank.id}/chart-data/`,
        );
        this.tankProfileData = data;
        this.$nextTick(() => {
          this.renderTankChart();
        });
      } catch (error) {
        this.tankProfileError = error.message;
      } finally {
        this.tankProfileLoading = false;
      }
    },

    destroyTankChart() {
      if (this.tankChartInstance) {
        this.tankChartInstance.destroy();
        this.tankChartInstance = null;
      }
    },

    renderTankChart() {
      if (typeof Chart === "undefined" || !this.$refs.tankProfileChart) {
        return;
      }

      const series = this.tankProfileData && this.tankProfileData.series
        ? this.tankProfileData.series
        : {};
      const official = series.official_chart || [];
      const generated = series.generated_curve || [];
      const scatter = series.scatter_points || [];

      this.destroyTankChart();

      const datasets = [];

      if (official.length) {
        datasets.push({
          label: "Official Tank Chart",
          data: official.map((point) => ({ x: point.inches, y: point.gallons })),
          borderColor: "#a0aec0",
          backgroundColor: "transparent",
          borderWidth: 4,
          fill: false,
          showLine: true,
          pointRadius: 0,
          tension: 0.25,
          order: 3,
        });
      }

      if (generated.length) {
        datasets.push({
          label: "Generated Curve",
          data: generated.map((point) => ({ x: point.inches, y: point.gallons })),
          borderColor: "#ffb86c",
          backgroundColor: "transparent",
          borderWidth: 2,
          borderDash: [8, 4],
          fill: false,
          showLine: true,
          pointRadius: 0,
          tension: 0.25,
          order: 2,
        });
      }

      if (scatter.length) {
        datasets.push({
          label: "Veeder-Root Readings",
          data: scatter.map((point) => ({ x: point.inches, y: point.gallons })),
          backgroundColor: "#e94560",
          borderColor: "#ffffff",
          borderWidth: 1,
          pointRadius: 5,
          pointHoverRadius: 7,
          showLine: false,
          order: 1,
        });
      }

      this.tankChartInstance = new Chart(this.$refs.tankProfileChart, {
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
              title: { display: true, text: "Volume (Gallons)", color: "#a0aec0" },
              grid: { color: "#2a2e33" },
              ticks: { color: "#a0aec0" },
            },
          },
          plugins: {
            legend: {
              labels: { color: "#d9dce3", boxWidth: 14 },
            },
          },
        },
      });
    },

    formatMetric(value, unit) {
      if (value == null || Number.isNaN(Number(value))) {
        return "N/A";
      }
      return `${Math.round(Number(value)).toLocaleString()} ${unit}`;
    },

    initMap() {
      this.mapController = IntelMap.init("intel-map");
      const prefMeta = document.querySelector('meta[name="user-map-preference"]');
      const pref = prefMeta && prefMeta.content ? prefMeta.content : "STANDARD";
      this.setMapMode(pref === "DARK" ? "DARK" : "STANDARD");
    },

    setMapMode(mode) {
      this.mapMode = mode;
      if (this.mapController) {
        this.mapController.setMode(mode);
      }
    },

    bindSketchModal() {
      const sketchModal = document.getElementById("sketchModal");
      if (!sketchModal || !this.$refs.modalSketchImg) {
        return;
      }

      sketchModal.addEventListener("show.bs.modal", (event) => {
        const trigger = event.relatedTarget;
        this.$refs.modalSketchImg.src = trigger && trigger.src ? trigger.src : "";
      });
    },
  };
}

function registerAlpineComponent() {
  window.Alpine.data("siteLocationDetailApp", siteLocationDetailApp);
}

function parseNumericValue(value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function bootstrapWithoutAlpine() {
  const root = document.querySelector('[data-initial-intel-mode]');
  if (!root) {
    return;
  }

  const app = siteLocationDetailApp();
  app.$root = root;
  app.$refs = {
    modalSketchImg: document.getElementById("modal-sketch-img"),
    tankProfileChart: document.querySelector("[x-ref='tankProfileChart']"),
  };
  app.$nextTick = (callback) => window.setTimeout(callback, 0);
  app.init();

  const personalContainer = document.getElementById("intel-personal-container");
  const sharedContainer = document.getElementById("intel-shared-container");
  const hintDisplay = document.getElementById("intel-layer-hint");
  const layerSelector = document.getElementById("intel-layer-selector");

  const updateLayerView = () => {
    const layer = layerSelector ? layerSelector.value : "DEFAULT";
    if (personalContainer) {
      personalContainer.style.display = layer === "PERSONAL" ? "block" : "none";
    }
    if (sharedContainer) {
      sharedContainer.style.display = layer === "PERSONAL" ? "none" : "block";
    }
    if (hintDisplay) {
      hintDisplay.textContent =
        layer === "PERSONAL"
          ? "* YOU ARE VIEWING YOUR PRIVATE OBSERVATIONS."
          : "* VIEWING SHARED LAYER. CREATE YOUR OWN TO OVERRIDE.";
    }
  };

  if (layerSelector) {
    layerSelector.addEventListener("change", updateLayerView);
    updateLayerView();
  }

  const standardBtn = document.getElementById("btn-map-standard");
  const darkBtn = document.getElementById("btn-map-dark");
  if (standardBtn && darkBtn) {
    const setActiveMapButton = (mode) => {
      standardBtn.classList.toggle("active", mode === "STANDARD");
      darkBtn.classList.toggle("active", mode === "DARK");
    };

    standardBtn.addEventListener("click", () => {
      app.setMapMode("STANDARD");
      setActiveMapButton("STANDARD");
    });
    darkBtn.addEventListener("click", () => {
      app.setMapMode("DARK");
      setActiveMapButton("DARK");
    });
  }

  const tankButtons = Array.from(document.querySelectorAll(".tank-config-btn"));
  tankButtons.forEach((button) => {
    button.addEventListener("click", () => {
      tankButtons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      app.selectTank({
        id: Number(button.dataset.tankId),
        tankIndex: parseNumericValue(button.dataset.tankIndex),
        fuelType: button.dataset.fuelType || "UNKNOWN",
        capacity: parseNumericValue(button.dataset.capacity),
        maxDepth: parseNumericValue(button.dataset.maxDepth),
        model: button.dataset.model || "UNKNOWN",
      });
    });
  });

  const firstTankButton = tankButtons[0];
  if (firstTankButton) {
    firstTankButton.click();
  }

  document.querySelectorAll("[x-cloak]").forEach((element) => {
    element.removeAttribute("x-cloak");
  });
}

if (window.Alpine) {
  registerAlpineComponent();
} else {
  document.addEventListener("alpine:init", registerAlpineComponent);
}

window.siteLocationDetailApp = siteLocationDetailApp;

document.addEventListener("DOMContentLoaded", () => {
  if (!window.Alpine) {
    bootstrapWithoutAlpine();
  }
});
