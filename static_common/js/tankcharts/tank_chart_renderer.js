(function (window) {
  "use strict";

  const COLORS = {
    official: "#a0aec0",
    generated: "#8da35d",
    observed: "#e94560",
    overlay: "#50fa7b",
    grid: "#2a2e33",
    labels: "#a0aec0",
    legend: "#d9dce3",
  };
  const MAX_LAYOUT_RETRIES = 8;

  function finitePoint(point) {
    const x = Number(point && (point.x ?? point.inches));
    const y = Number(point && (point.y ?? point.gallons));
    return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
  }

  function points(values) {
    return (Array.isArray(values) ? values : []).map(finitePoint).filter(Boolean);
  }

  function lineDataset(label, data, style) {
    if (data.length < 2) return null;
    return {
      type: "line",
      label,
      data,
      borderColor: style.borderColor,
      backgroundColor: "transparent",
      borderWidth: style.borderWidth,
      borderDash: style.borderDash,
      fill: false,
      showLine: true,
      pointRadius: 0,
      tension: 0.2,
      order: style.order,
    };
  }

  function buildDatasets(payload, overlays) {
    const data = payload || {};
    const series = data.series || {};
    const tank = data.tank || {};
    const datasets = [];
    const official = points(series.official_chart);
    const generated = points(series.generated_curve);
    const observed = points(series.scatter_points);

    if (tank.source_policy !== "VEEDER_ONLY") {
      const officialDataset = lineDataset("Official Tank Chart", official, {
        borderColor: COLORS.official,
        borderWidth: 3,
        order: 3,
      });
      if (officialDataset) datasets.push(officialDataset);
    }

    const generatedDataset = lineDataset("Generated Curve", generated, {
      borderColor: COLORS.generated,
      borderWidth: 2,
      order: 2,
    });
    if (generatedDataset) datasets.push(generatedDataset);

    if (observed.length) {
      datasets.push({
        type: "scatter",
        label: "Veeder-Root Readings",
        data: observed,
        backgroundColor: COLORS.observed,
        borderColor: "#ffffff",
        borderWidth: 1,
        pointRadius: 4,
        pointHoverRadius: 6,
        showLine: false,
        order: 1,
      });
    }

    (Array.isArray(overlays) ? overlays : []).forEach((overlay) => {
      const overlayPoints = points(overlay.data);
      if (!overlayPoints.length) return;
      const isLine = overlay.type === "line" && overlayPoints.length > 1;
      datasets.push({
        type: isLine ? "line" : "scatter",
        label: overlay.label || "Overlay",
        data: overlayPoints,
        backgroundColor: overlay.backgroundColor || COLORS.overlay,
        borderColor: overlay.borderColor || "#ffffff",
        borderWidth: overlay.borderWidth || 1,
        borderDash: isLine ? overlay.borderDash : undefined,
        fill: false,
        showLine: isLine,
        pointRadius: overlay.pointRadius || 6,
        pointHoverRadius: overlay.pointHoverRadius || 8,
        tension: 0.2,
        order: overlay.order ?? 0,
      });
    });

    return datasets;
  }

  function stateFor(payload, datasets) {
    const readiness = payload && payload.tank && payload.tank.readiness;
    const hasCurve = datasets.some((dataset) => dataset.type === "line");
    const hasPoints = datasets.some((dataset) => dataset.data.length > 0);
    return {
      readiness: readiness || "UNAVAILABLE",
      hasCurve,
      hasPoints,
      pointsOnly: hasPoints && !hasCurve,
      empty: !hasPoints,
    };
  }

  function chartOptions() {
    return {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: "linear",
          title: { display: true, text: "Depth (Inches)", color: COLORS.labels },
          grid: { color: COLORS.grid },
          ticks: { color: COLORS.labels },
        },
        y: {
          title: { display: true, text: "Volume (Gallons)", color: COLORS.labels },
          grid: { color: COLORS.grid },
          ticks: { color: COLORS.labels },
        },
      },
      plugins: { legend: { labels: { color: COLORS.legend, boxWidth: 14 } } },
    };
  }

  function render(canvas, payload, options) {
    const config = options || {};
    const datasets = buildDatasets(payload, config.overlays);
    const state = stateFor(payload, datasets);
    let chart = null;
    let observer = null;
    let frame = null;
    let retries = 0;
    let destroyed = false;

    function tryCreate() {
      if (destroyed || chart) return;
      if (typeof window.Chart !== "function") return;
      if (!canvas || canvas.clientWidth <= 0 || canvas.clientHeight <= 0) {
        if (retries++ < MAX_LAYOUT_RETRIES) frame = window.requestAnimationFrame(tryCreate);
        return;
      }
      if (!state.empty) chart = new window.Chart(canvas, {
        type: "scatter",
        data: { datasets },
        options: Object.assign(chartOptions(), config.chartOptions || {}),
      });
      if (typeof window.ResizeObserver === "function") {
        observer = new window.ResizeObserver(() => {
          if (chart) chart.resize();
          else tryCreate();
        });
        observer.observe(canvas.parentElement || canvas);
      }
    }

    tryCreate();
    return {
      state,
      get chart() { return chart; },
      destroy() {
        destroyed = true;
        if (frame !== null) window.cancelAnimationFrame(frame);
        if (observer) observer.disconnect();
        if (chart) chart.destroy();
        chart = null;
      },
    };
  }

  window.TankChartRenderer = { COLORS, buildDatasets, stateFor, render };
})(window);
