(() => {
  function destroyCharts(host) {
    host.chartRenderGeneration = (host.chartRenderGeneration || 0) + 1;
    Object.values(host.preflightCharts || {}).forEach((chart) => {
      if (chart && typeof chart.destroy === "function") {
        chart.destroy();
      }
    });
    host.preflightCharts = {};
  }

  async function renderChartForRow(host, row, generation) {
    let chartData = { series: {}, tank: {} };
    let scatterSeries = [];

    if (row.tank_mapping_id) {
      try {
        const response = await fetch(`/tankgauge/api/tanks/${row.tank_mapping_id}/chart-data/`);
        if (response.ok) {
          const payload = await response.json();
          chartData = (payload?.status === "success" ? payload.data : payload) || chartData;
          scatterSeries = chartData?.series?.scatter_points || [];
        }
      } catch (error) {
        scatterSeries = [];
      }
    }

    if (generation !== host.chartRenderGeneration) return;
    if (scatterSeries.length === 0) {
      scatterSeries = row.graph?.historical_points || [];
    }

    const candidate = row.graph?.candidate_point || {};
    const candidatePoint = Number.isFinite(Number(candidate.inches)) &&
      Number.isFinite(Number(candidate.gallons))
      ? [{ x: Number(candidate.inches), y: Number(candidate.gallons) }]
      : [];
    chartData.series = Object.assign({}, chartData.series, {
      scatter_points: scatterSeries,
    });

    const canvas = document.getElementById(`preflight-chart-${row.preflight_token}`);
    if (
      generation !== host.chartRenderGeneration ||
      !canvas ||
      !window.TankChartRenderer
    ) {
      return;
    }

    const controller = window.TankChartRenderer.render(canvas, chartData, {
      overlays: [
        {
          label: "Current Entry",
          data: candidatePoint,
          backgroundColor: "#50fa7b",
          pointRadius: 7,
          order: 0,
        },
      ],
    });
    if (generation !== host.chartRenderGeneration) {
      controller.destroy();
      return;
    }
    host.preflightCharts[row.preflight_token] = controller;
  }

  function renderCharts(host) {
    destroyCharts(host);
    if (!window.TankChartRenderer) return;
    const generation = host.chartRenderGeneration;
    (host.preflightRows || []).forEach((row) => {
      renderChartForRow(host, row, generation);
    });
  }

  window.VeederGraphSection = {
    destroyCharts,
    renderCharts,
  };
})();
