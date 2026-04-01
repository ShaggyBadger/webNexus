/**
 * Tactical GPS Module: webNexus
 * Handles opt-in location tracking and modular UI updates for the Header.
 */

const TacticalGPS = {
  storageKey: "webnexus_gps_optin",

  init() {
    const optIn = localStorage.getItem(this.storageKey);
    const displayElement = document.getElementById("loc-ref-display");

    if (!displayElement) return;

    if (optIn === "granted") {
      this.pulse();
    } else {
      this.renderOptInButton(displayElement);
    }
  },

  renderOptInButton(container) {
    container.innerHTML = `
            <button id="gps-pulse-btn" class="btn btn-outline-primary btn-sm mono py-0 px-2" style="font-size: 0.65rem;">
                [ INITIALIZE GPS PULSE ]
            </button>
        `;

    document.getElementById("gps-pulse-btn").addEventListener("click", () => {
      this.requestPermission();
    });
  },

  requestPermission() {
    if (!navigator.geolocation) {
      alert("TACTICAL ERROR: Hardware does not support GPS Pulse.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        localStorage.setItem(this.storageKey, "granted");
        this.updateUI(position.coords);
      },
      (error) => {
        console.error("GPS Access Denied:", error);
        alert("ACCESS DENIED: Field coordinates blocked by user.");
      },
    );
  },

  pulse() {
    navigator.geolocation.getCurrentPosition(
      (position) => this.updateUI(position.coords),
      (error) => {
        console.warn("Pulse Failed:", error);
        const display = document.getElementById("loc-ref-display");
        if (display) display.innerText = "LOC_REF: SIGNAL_LOST";
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  },

  async updateUI(coords) {
    // 1. Update Coordinates (Main Line)
    const lat = coords.latitude.toFixed(4);
    const lon = coords.longitude.toFixed(4);
    const refDisplay = document.getElementById("loc-ref-display");
    if (refDisplay) {
      refDisplay.innerHTML = `LOC_REF: <span class="text-primary">${lat}°N, ${lon}°W</span>`;
    }

    // 2. Fetch & Update Intel Overlay (Small Sub-Line)
    const intelDisplay = document.getElementById("loc-intel-display");
    if (!intelDisplay) return;

    try {
      const response = await fetch(
        `/tankgauge/api/closest-store/?lat=${coords.latitude}&lon=${coords.longitude}`,
      );
      if (response.ok) {
        const data = await response.json();
        intelDisplay.style.display = "block";
        intelDisplay.innerHTML = `
                    ZONE: <span class="text-primary">${data.city.toUpperCase()}, ${data.state.toUpperCase()}</span> // 
                    TARGET: <span class="text-primary">#${data.store_num} (${data.distance_feet.toLocaleString()} FT)
                </span>`;
      }
    } catch (error) {
      console.error("Intel Fetch Failed:", error);
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  TacticalGPS.init();
  // Periodic pulse every 10 seconds if already granted
  setInterval(() => {
    if (localStorage.getItem(TacticalGPS.storageKey) === "granted") {
      TacticalGPS.pulse();
    }
  }, 10000);
});
