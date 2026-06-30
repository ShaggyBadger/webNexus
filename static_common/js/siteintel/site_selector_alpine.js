function siteSelectorApp() {
  return {
    query: "",
    results: [],
    loadingSearch: false,
    loadingGps: false,
    errorMessage: "",
    gpsStatus: "",
    panelLabel: "",
    showResultsPanel: false,
    canPropose: false,
    proposalHref: "",

    get lookupUrl() {
      return this.$root.dataset.lookupUrl;
    },

    get proximityUrl() {
      return this.$root.dataset.proximityUrl;
    },

    get proposalBaseUrl() {
      return this.$root.dataset.proposalUrl;
    },

    normalizePayload(raw) {
      if (raw && raw.status === "success" && raw.data !== undefined) {
        return raw.data;
      }
      return raw;
    },

    async fetchJson(url) {
      const response = await fetch(url);
      let raw = null;
      try {
        raw = await response.json();
      } catch (error) {
        raw = null;
      }

      const payload = this.normalizePayload(raw);
      if (!response.ok) {
        const message =
          payload?.error?.message || payload?.error || "Request failed. Try again.";
        throw new Error(message);
      }
      return payload;
    },

    setResults(results, label) {
      this.results = results || [];
      this.panelLabel = label;
      this.showResultsPanel = true;
    },

    runManualSearch() {
      const trimmed = (this.query || "").trim();
      this.errorMessage = "";
      this.canPropose = false;

      if (trimmed.length < 2) {
        this.showResultsPanel = false;
        this.results = [];
        return;
      }

      this.loadingSearch = true;
      this.fetchJson(`${this.lookupUrl}?q=${encodeURIComponent(trimmed)}`)
        .then((data) => {
          const matches = data?.results || [];
          this.setResults(matches, `MANUAL_SCAN_FOR: ${trimmed}`);
          this.canPropose = matches.length === 0;
          this.proposalHref = `${this.proposalBaseUrl}?store_num=${encodeURIComponent(trimmed)}`;
        })
        .catch((error) => {
          this.showResultsPanel = false;
          this.results = [];
          this.errorMessage = error.message;
        })
        .finally(() => {
          this.loadingSearch = false;
        });
    },

    scanNearbyStores() {
      this.errorMessage = "";
      this.canPropose = false;

      if (!navigator.geolocation) {
        this.errorMessage = "Geolocation is not supported in this browser.";
        return;
      }

      this.loadingGps = true;
      this.gpsStatus = "ACQUIRING GPS LOCK...";

      navigator.geolocation.getCurrentPosition(
        (position) => {
          const lat = position.coords.latitude;
          const lon = position.coords.longitude;
          this.gpsStatus = `LOCK_ACQUIRED: ${lat.toFixed(4)}, ${lon.toFixed(4)}`;

          this.fetchJson(`${this.proximityUrl}?lat=${lat}&lon=${lon}`)
            .then((data) => {
              const matches = data?.results || [];
              this.setResults(matches, "PROXIMITY_SCAN_RESULTS");
              if (!matches.length) {
                this.errorMessage = "No nearby stores found.";
              }
            })
            .catch((error) => {
              this.showResultsPanel = false;
              this.results = [];
              this.errorMessage = error.message;
            })
            .finally(() => {
              this.loadingGps = false;
              setTimeout(() => {
                this.gpsStatus = "";
              }, 3000);
            });
        },
        () => {
          this.loadingGps = false;
          this.gpsStatus = "";
          this.errorMessage = "GPS permission denied or unavailable.";
        },
        { enableHighAccuracy: true, timeout: 10000 },
      );
    },

    siteTitle(site) {
      const name = site.store_name || site.name || "UNKNOWN_SITE";
      return `#${site.store_num || "--"} ${name}`;
    },

    siteSubtitle(site) {
      const city = site.city || "UNKNOWN LOC";
      const hint = site.distance_display || "[CLICK_TO_ACQUIRE]";
      return `${city} ${hint}`;
    },

    openSite(site) {
      if (site.has_location) {
        const locationId = site.location_id || site.id;
        window.location.href = `/siteintel/site/${locationId}/`;
        return;
      }

      const storePk = site.store_pk || site.id;
      window.location.href = `/siteintel/init-location/${storePk}/`;
    },
  };
}

document.addEventListener("alpine:init", () => {
  window.Alpine.data("siteSelectorApp", siteSelectorApp);
});
