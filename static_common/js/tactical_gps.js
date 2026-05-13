/**
 * Tactical GPS Module: webNexus
 * Handles opt-in location tracking and modular UI updates for the Header.
 */

const TacticalGPS = {
  storageKey: "webnexus_gps_optin",
  storePersistenceKey: "webnexus_closest_store_id",

  init() {
    const optIn = localStorage.getItem(this.storageKey);
    
    // Always pulse if granted
    if (optIn === "granted") {
      this.pulse().catch(() => {});
    } else {
      const displayElement = document.getElementById("loc-ref-display");
      if (displayElement) {
        this.renderOptInButton(displayElement);
      }
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

  /**
   * Requests GPS permission and returns a promise.
   */
  requestPermission() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        const err = "HARDWARE_UNSUPPORTED";
        alert("TACTICAL ERROR: Hardware does not support GPS Pulse.");
        reject(err);
        return;
      }

      navigator.geolocation.getCurrentPosition(
        async (position) => {
          console.log("GPS Pulse Success:", position.coords.latitude, position.coords.longitude);
          localStorage.setItem(this.storageKey, "granted");
          try {
            const data = await this.updateUI(position.coords);
            resolve(data);
          } catch (e) {
            reject(e);
          }
        },
        (error) => {
          console.error("GPS Access Denied/Failed:", error);
          if (error.code === 3) {
            alert("TIMEOUT ERROR: GPS signal acquisition took too long. Please ensure you have a clear view of the sky.");
          } else {
            alert("ACCESS DENIED: Field coordinates blocked or unavailable.");
          }
          reject(error);
        },
        { enableHighAccuracy: true, timeout: 15000 }
      );
    });
  },

  /**
   * Triggers a fresh GPS pulse.
   * If not granted, it will attempt to request permission.
   */
  async pulse() {
    console.log("TacticalGPS: Triggering fresh pulse...");
    if (localStorage.getItem(this.storageKey) !== "granted") {
      return await this.requestPermission();
    }

    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          console.log("GPS Pulse Success (Pulse):", position.coords.latitude, position.coords.longitude);
          try {
            const data = await this.updateUI(position.coords);
            resolve(data);
          } catch (e) {
            reject(e);
          }
        },
        (error) => {
          console.warn("Pulse Failed:", error);
          const display = document.getElementById("loc-ref-display");
          if (display) display.innerText = "LOC_REF: SIGNAL_LOST";
          reject(error);
        },
        { enableHighAccuracy: true, timeout: 15000 },
      );
    });
  },

  async updateUI(coords) {
    // 1. Update Coordinates (Main Line)
    const lat = coords.latitude.toFixed(4);
    const lon = coords.longitude.toFixed(4);
    
    const refDisplay = document.getElementById("loc-ref-display");
    if (refDisplay) {
      refDisplay.innerHTML = `LOC_REF: <span class="text-primary">${lat}°N, ${lon}°W</span>`;
    }

    // Dispatch global event for other modules (like RackManager)
    document.dispatchEvent(new CustomEvent('webnexus:gps_pulse', { 
        detail: { 
            lat: coords.latitude, 
            lon: coords.longitude,
            accuracy: coords.accuracy
        } 
    }));

    try {
      const response = await fetch(
        `/tankgauge/api/closest-store/?lat=${coords.latitude}&lon=${coords.longitude}`,
      );
      if (response.ok) {
        const data = await response.json();
        
        // PERSISTENCE: Store with timestamp
        const storeIntel = {
            num: data.store_num,
            timestamp: Date.now()
        };
        localStorage.setItem(this.storePersistenceKey, JSON.stringify(storeIntel));
        
        // 2. Update Intel Overlay (if present)
        const intelDisplay = document.getElementById("loc-intel-display");
        if (intelDisplay) {
          const distanceStr = data.distance_display || `${data.distance_feet.toLocaleString()} FT`;
          intelDisplay.style.display = "block";
          intelDisplay.innerHTML = `
                      ZONE: <span class="text-primary">${data.city.toUpperCase()}, ${data.state.toUpperCase()}</span> // 
                      TARGET: <span class="text-primary">#${data.store_num} (${distanceStr})
                  </span>`;
        }

        return data;
      }
    } catch (error) {
      console.error("Intel Fetch Failed:", error);
      throw error;
    }
  },
};

document.addEventListener("DOMContentLoaded", () => {
  TacticalGPS.init();
});
