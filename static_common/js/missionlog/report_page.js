document.addEventListener("DOMContentLoaded", async () => {
  const container = document.getElementById("report-content");
  if (!container) {
    return;
  }

  const reportUrl = container.dataset.reportUrl;
  if (!reportUrl) {
    container.innerHTML = '<p class="text-tactical-danger mono">REPORT_URL_MISSING</p>';
    return;
  }

  try {
    const response = await fetch(reportUrl);
    const raw = await response.json();
    const data = raw && raw.status === "success" && raw.data ? raw.data : raw;

    if (!response.ok) {
      const message =
        (data && data.error && data.error.message) || "Unable to load report intelligence.";
      throw new Error(message);
    }

    const gross =
      data && data.metrics && data.metrics.fuel
        ? data.metrics.fuel.total_gross_gallons.value
        : "N/A";
    const mpg =
      data && data.metrics && data.metrics.efficiency
        ? data.metrics.efficiency.mpg.value
        : "N/A";

    container.innerHTML = `
      <div class="tactical-card">
        <h4>Fuel Intelligence</h4>
        <div class="metric-label">Gross Gallons</div>
        <div class="metric-value">${gross}</div>
        <div class="metric-label">MPG</div>
        <div class="metric-value">${mpg}</div>
      </div>
    `;
  } catch (error) {
    console.error("MISSIONLOG_REPORT_RENDER_FAILED", error);
    container.innerHTML = `<p class="text-tactical-danger mono">${error.message}</p>`;
  }
});
