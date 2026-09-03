(function () {
  function nearbyStoresApp() {
    return {
      loading: false,
      stores: [],
      message: "",
      statusLabel: "GPS OPTIONAL",

      init: function () {
        if (!navigator.geolocation) {
          this.message = "GPS unavailable. USE SEARCH DIRECTORY for manual lookup.";
          return;
        }
        this.loading = true;
        navigator.geolocation.getCurrentPosition(
          this.loadNearby.bind(this),
          this.handleFailure.bind(this),
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 },
        );
      },

      loadNearby: async function (position) {
        try {
          const response = await fetch(
            `/tankgauge/api/closest-store/?lat=${position.coords.latitude}&lon=${position.coords.longitude}`,
          );
          if (!response.ok) throw new Error("Nearby lookup failed.");
          const raw = await response.json();
          const payload = raw && raw.status === "success" ? raw.data : raw;
          this.stores = payload.results || [];
          this.statusLabel = this.stores.length ? "POSITION LOCKED" : "NO STORES FOUND";
          if (!this.stores.length) this.message = "No nearby stores found.";
        } catch (error) {
          this.message = "Nearby lookup unavailable. USE SEARCH DIRECTORY.";
          this.statusLabel = "SIGNAL UNAVAILABLE";
        } finally {
          this.loading = false;
        }
      },

      handleFailure: function () {
        this.loading = false;
        this.statusLabel = "GPS OPTIONAL";
        this.message = "Location permission unavailable. USE SEARCH DIRECTORY.";
      },
    };
  }

  window.nearbyStoresApp = nearbyStoresApp;
})();
