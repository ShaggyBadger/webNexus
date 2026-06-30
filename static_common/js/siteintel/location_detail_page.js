(function () {
  function getMapTileLayer(mode) {
    if (mode === "DARK") {
      return L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        {
          attribution: "© OpenStreetMap contributors © CARTO",
          subdomains: "abcd",
          maxZoom: 20,
        },
      );
    }

    if (typeof window.getTacticalTileLayer === "function") {
      return window.getTacticalTileLayer(L);
    }

    return L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
      maxZoom: 19,
    });
  }

  function renderOverlay(map, overlayJson) {
    if (!overlayJson) {
      return;
    }

    try {
      const data = JSON.parse(overlayJson);
      L.geoJSON(data, {
        style: function (feature) {
          return {
            color: feature.properties && feature.properties.color
              ? feature.properties.color
              : "#ffb86c",
            weight: 4,
            opacity: 0.8,
          };
        },
        onEachFeature: function (feature, layer) {
          if (feature.properties && feature.properties.name) {
            layer.bindTooltip(feature.properties.name, {
              permanent: true,
              direction: "top",
              className: "tactical-label",
            });
          }
        },
      }).addTo(map);
    } catch (error) {
      console.error("SITEINTEL_OVERLAY_PARSE_FAILED", error);
    }
  }

  function createMapController() {
    const container = document.getElementById("intel-map");
    if (!container || typeof L === "undefined") {
      return null;
    }

    const lat = Number(container.dataset.lat);
    const lon = Number(container.dataset.lon);
    const siteName = container.dataset.siteName || "TARGET";
    const overlay = container.dataset.overlay || "";
    if (Number.isNaN(lat) || Number.isNaN(lon)) {
      return null;
    }

    const map = L.map("intel-map").setView([lat, lon], 13);
    const prefMeta = document.querySelector('meta[name="user-map-preference"]');
    const initialMode = prefMeta && prefMeta.content === "DARK" ? "DARK" : "STANDARD";
    let layer = getMapTileLayer(initialMode).addTo(map);

    L.marker([lat, lon]).addTo(map).bindPopup(`<span class="mono">TARGET: ${siteName}</span>`);
    renderOverlay(map, overlay);

    return {
      initialMode: initialMode,
      setMode: function (mode) {
        if (layer) {
          map.removeLayer(layer);
        }
        layer = getMapTileLayer(mode).addTo(map);
      },
    };
  }

  function normalizePayload(raw) {
    if (raw && raw.status === "success" && raw.data !== undefined) {
      return raw.data;
    }
    return raw;
  }

  window.siteLocationDetailApp = function () {
    return {
      intelLayer: "DEFAULT",
      mapMode: "STANDARD",
      mapController: null,
      selectedTank: null,
      tankProfileData: null,
      tankProfileLoading: false,
      tankProfileError: "",
      tankChartInstance: null,

      get intelHint() {
        if (this.intelLayer === "PERSONAL") {
          return "* YOU ARE VIEWING YOUR PRIVATE OBSERVATIONS.";
        }
        return this.$root.dataset.initialIntelMode === "PUBLIC"
          ? "* AUTHENTICATION REQUIRED TO VIEW PERSONAL LAYERS."
          : "* VIEWING SHARED LAYER. CREATE YOUR OWN TO OVERRIDE.";
      },

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
        const allPoints = official.concat(generated).concat(scatter);

        const maxDepthFromData = allPoints.length
          ? Math.max.apply(
              null,
              allPoints.map(function (point) {
                return Number(point.inches) || 0;
              }),
            )
          : null;
        const maxGallonsFromData = allPoints.length
          ? Math.max.apply(
              null,
              allPoints.map(function (point) {
                return Number(point.gallons) || 0;
              }),
            )
          : null;

        const maxDepth =
          this.selectedTank && this.selectedTank.maxDepth != null
            ? this.selectedTank.maxDepth
            : maxDepthFromData;
        const maxGallons =
          this.selectedTank && this.selectedTank.capacity != null
            ? this.selectedTank.capacity
            : maxGallonsFromData;

        return {
          maxDepth: maxDepth,
          maxGallons: maxGallons,
          ninetyPercentGallons: maxGallons != null ? maxGallons * 0.9 : null,
          veederEntries: scatter.length,
          officialPoints: official.length,
          generatedPoints: generated.length,
        };
      },

      init: function () {
        const initialMode = this.$root.dataset.initialIntelMode || "DEFAULT";
        this.intelLayer = initialMode === "PERSONAL" ? "PERSONAL" : "DEFAULT";
        this.mapController = createMapController();
        if (this.mapController) {
          this.setMapMode(this.mapController.initialMode);
        }
        this.bindSketchModal();
        this.autoSelectFirstTank();
      },

      setMapMode: function (mode) {
        this.mapMode = mode;
        if (this.mapController) {
          this.mapController.setMode(mode);
        }
      },

      bindSketchModal: function () {
        const sketchModal = document.getElementById("sketchModal");
        const modalSketchImg = this.$refs.modalSketchImg;
        if (!sketchModal || !modalSketchImg) {
          return;
        }

        sketchModal.addEventListener("show.bs.modal", function (event) {
          const trigger = event.relatedTarget;
          modalSketchImg.src = trigger && trigger.src ? trigger.src : "";
        });
      },

      autoSelectFirstTank: function () {
        const self = this;
        this.$nextTick(function () {
          const firstButton = self.$root.querySelector(".tank-config-btn");
          if (firstButton) {
            firstButton.click();
          }
        });
      },

      fetchJson: async function (url) {
        const response = await fetch(url);
        let raw = null;
        try {
          raw = await response.json();
        } catch (error) {
          raw = null;
        }

        const payload = normalizePayload(raw);
        if (!response.ok) {
          const message = payload && payload.error && payload.error.message
            ? payload.error.message
            : payload && payload.error
              ? payload.error
              : "Request failed.";
          throw new Error(message);
        }
        return payload;
      },

      selectTank: async function (tank) {
        this.selectedTank = tank;
        this.tankProfileData = null;
        this.tankProfileError = "";
        this.destroyTankChart();
        await this.loadTankProfile();
      },

      loadTankProfile: async function () {
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
          const self = this;
          this.$nextTick(function () {
            self.renderTankChart();
          });
        } catch (error) {
          this.tankProfileError = error.message;
        } finally {
          this.tankProfileLoading = false;
        }
      },

      destroyTankChart: function () {
        if (this.tankChartInstance) {
          this.tankChartInstance.destroy();
          this.tankChartInstance = null;
        }
      },

      renderTankChart: function () {
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
            data: official.map(function (point) {
              return { x: point.inches, y: point.gallons };
            }),
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
            data: generated.map(function (point) {
              return { x: point.inches, y: point.gallons };
            }),
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
            data: scatter.map(function (point) {
              return { x: point.inches, y: point.gallons };
            }),
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
          data: { datasets: datasets },
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

      formatMetric: function (value, unit) {
        if (value == null || Number.isNaN(Number(value))) {
          return "N/A";
        }
        return `${Math.round(Number(value)).toLocaleString()} ${unit}`;
      },
    };
  };
})();
