document.addEventListener("DOMContentLoaded", () => {
  const config = document.getElementById("oversight-config");
  if (!config || typeof L === "undefined") {
    return;
  }

  const telemetryUrl = config.dataset.telemetryUrl;
  const heatmapData = JSON.parse(config.dataset.heatmap || "[]");
  const siteMarkers = JSON.parse(config.dataset.siteMarkers || "[]");

  const map = L.map("sector-map", {
    zoomControl: true,
    attributionControl: false,
  }).setView([35.7596, -79.0193], 6.5);

  const lightTiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
  });
  const darkTiles = L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    {
      maxZoom: 20,
    },
  );

  lightTiles.addTo(map);

  const themeToggle = document.getElementById("map-theme-toggle");
  themeToggle.addEventListener("change", function () {
    if (this.checked) {
      map.removeLayer(lightTiles);
      darkTiles.addTo(map);
      return;
    }
    map.removeLayer(darkTiles);
    lightTiles.addTo(map);
  });

  const heat = L.heatLayer(heatmapData, {
    radius: 40,
    blur: 20,
    maxZoom: 10,
    gradient: { 0.4: "blue", 0.65: "lime", 1: "red" },
  }).addTo(map);

  const markerLayer = L.layerGroup().addTo(map);

  const getMarkerColor = (brand) => {
    if (brand.includes("EXXON")) return "#ff5555";
    if (brand.includes("MOBIL")) return "#8be9fd";
    if (brand.includes("7-ELEVEN") || brand.includes("7-11")) return "#ffb86c";
    if (brand.includes("SPEEDWAY")) return "#f1fa8c";
    if (brand.includes("FUEL_RACK")) return "#50fa7b";
    return "#bd93f9";
  };

  siteMarkers.forEach((site) => {
    const color = getMarkerColor(site.brand || "");
    if (site.type === "RACK") {
      const rackIcon = L.divIcon({
        className: "rack-marker",
        html: `<div style="width:12px; height:12px; background:${color}; border:2px solid #fff; transform: rotate(45deg);"></div>`,
        iconSize: [12, 12],
      });
      L.marker([site.lat, site.lon], { icon: rackIcon })
        .bindPopup(`<strong>${site.name}</strong><br>TYPE: FUEL RACK`)
        .addTo(markerLayer);
      return;
    }

    L.circleMarker([site.lat, site.lon], {
      radius: 6,
      fillColor: color,
      color: "#fff",
      weight: 1,
      opacity: 1,
      fillOpacity: 0.8,
    })
      .bindPopup(`<strong>${site.name}</strong><br>BRAND: ${site.brand}`)
      .addTo(markerLayer);
  });

  const terminal = document.getElementById("terminal");
  terminal.scrollTop = terminal.scrollHeight;

  setInterval(async () => {
    try {
      const response = await fetch(telemetryUrl);
      if (!response.ok) {
        return;
      }

      const data = await response.json();
      heat.setLatLngs(data.heatmap);

      document.getElementById("val-agents").innerText = Object.keys(data.agents).length;
      document.getElementById("val-errors").innerText = data.error_count;

      const dbEl = document.getElementById("val-db-status");
      const latEl = document.getElementById("val-latency");
      dbEl.innerText = data.system_health.db_status;
      dbEl.style.color =
        data.system_health.db_status === "DB_READY"
          ? "var(--tactical-green)"
          : "var(--tactical-red)";
      latEl.innerText = `${data.system_health.latency_ms}ms`;

      const appHitsContainer = document.getElementById("app-hits");
      appHitsContainer.innerHTML = "";
      Object.entries(data.app_hits).forEach(([app, count]) => {
        appHitsContainer.innerHTML += `
          <div class="tactical-bar-container">
            <div class="tactical-bar-label">${app.toUpperCase()} // ${count}</div>
            <div class="tactical-bar-fill" style="width: ${Math.min(count, 100)}%"></div>
          </div>
        `;
      });

      const intelFeed = document.getElementById("intel-feed");
      intelFeed.innerHTML = "";
      data.latest_proposals.forEach((prop) => {
        intelFeed.innerHTML += `
          <div class="intel-feed-item">
            <div class="d-flex justify-content-between">
              <span style="color: var(--tactical-amber)">PROPOSAL_${prop.id}</span>
              <span class="text-muted" style="font-size: 0.6rem;">${prop.time_ago}</span>
            </div>
            <div>${prop.store_name}</div>
            <div style="font-size: 0.6rem; color: #6272a4;">BY: ${prop.submitted_by}</div>
          </div>
        `;
      });

      const logContent = document.getElementById("log-content");
      logContent.innerHTML = "";
      data.terminal.forEach((line) => {
        const row = document.createElement("div");
        row.className = "log-line";
        if (line.includes("ERROR") || line.includes("CRITICAL")) row.classList.add("error");
        else if (line.includes("WARNING")) row.classList.add("warning");
        else if (line.includes("INFO")) row.classList.add("info");
        row.innerText = line;
        logContent.appendChild(row);
      });
      terminal.scrollTop = terminal.scrollHeight;
    } catch (error) {
      console.error("TELEMETRY_PULSE_FAILED", error);
    }
  }, 5000);
});
