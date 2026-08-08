function homepageHub() {
  return {
    clockLabel: "00:00:00L",
    intervalId: null,

    // Store identification state
    storeNum: null,
    storeName: null,
    city: null,
    state: null,
    distanceDisplay: null,
    vaporManifold: null,
    veederReadings: false,

    init() {
      console.log('[homepageHub] init() called');
      this.updateClock();
      this.intervalId = window.setInterval(() => this.updateClock(), 1000);

      // Listen for store identification from GPS pulse
      document.addEventListener('webnexus:store_identified', (e) => {
        console.log('[homepageHub] store_identified received:', e.detail);
        this.storeNum = e.detail.store_num;
        this.storeName = e.detail.store_name;
        this.city = e.detail.city;
        this.state = e.detail.state;
         this.distanceDisplay = e.detail.distance_display;
         this.vaporManifold = e.detail.vapor_manifold;
         this.veederReadings = e.detail.veeder_readings === true;
      });
    },

    get vaporManifoldLabel() {
      if (this.vaporManifold === true) return "VAPOR MANIFOLD: YES";
      if (this.vaporManifold === false) return "VAPOR MANIFOLD: NO";
      return "VAPOR MANIFOLD: UNKNOWN";
    },

    get vaporManifoldCssClass() {
      if (this.vaporManifold === true) return "vapor-manifold-yes";
      if (this.vaporManifold === false) return "vapor-manifold-no";
      return "vapor-manifold-unknown";
    },

    get veederReadingsLabel() {
      return this.veederReadings ? "VRR FEED: ACTIVE" : "VRR FEED: NONE";
    },

    get veederReadingsCssClass() {
      return this.veederReadings ? "veeder-readings-active" : "veeder-readings-none";
    },

    updateClock() {
      const now = new Date();
      const hours = String(now.getHours()).padStart(2, "0");
      const minutes = String(now.getMinutes()).padStart(2, "0");
      const seconds = String(now.getSeconds()).padStart(2, "0");
      this.clockLabel = `${hours}:${minutes}:${seconds}L`;
    },
  };
}

document.addEventListener("alpine:init", () => {
  Alpine.data("homepageHub", homepageHub);
});
