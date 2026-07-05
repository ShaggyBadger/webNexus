(() => {
  function destroyCharts(host) {
    Object.values(host.preflightCharts || {}).forEach((chart) => {
      if (chart && typeof chart.destroy === "function") {
        chart.destroy();
      }
    });
    host.preflightCharts = {};
  }

  async function renderChartForRow(host, row) {
    const canvas = document.getElementById(`preflight-chart-${row.preflight_token}`);
    if (!canvas || typeof Chart !== "function") {
      return;
    }

    let officialSeries = [];
    let generatedSeries = [];
    let scatterSeries = [];

    if (row.tank_mapping_id) {
      try {
        const response = await fetch(`/tankgauge/api/tanks/${row.tank_mapping_id}/chart-data/`);
        if (response.ok) {
          const payload = await response.json();
          const chartData = payload?.status === "success" ? payload.data : payload;
          const series = chartData?.series || {};

          officialSeries = (series.official_chart || []).map((point) => ({
            x: Number(point.inches),
            y: Number(point.gallons),
          }));
          generatedSeries = (series.generated_curve || []).map((point) => ({
            x: Number(point.inches),
            y: Number(point.gallons),
          }));
          scatterSeries = (series.scatter_points || []).map((point) => ({
            x: Number(point.inches),
            y: Number(point.gallons),
          }));
        }
      } catch (error) {
        scatterSeries = [];
      }
    }

    if (scatterSeries.length === 0) {
      scatterSeries = (row.graph?.historical_points || []).map((point) => ({
        x: Number(point.inches),
        y: Number(point.gallons),
      }));
    }

    const candidate = row.graph?.candidate_point || {};
    const datasets = [];

    if (officialSeries.length > 0) {
      datasets.push({
        type: "line",
        label: "Official Chart",
        data: officialSeries,
        borderColor: "#ffb86c",
        backgroundColor: "rgba(255, 184, 108, 0.2)",
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.1,
      });
    }

    if (generatedSeries.length > 0) {
      datasets.push({
        type: "line",
        label: "Generated Curve",
        data: generatedSeries,
        borderColor: "#8da35d",
        backgroundColor: "rgba(141, 163, 93, 0.18)",
        borderWidth: 2,
        borderDash: [6, 4],
        pointRadius: 0,
        tension: 0.12,
      });
    }

    if (scatterSeries.length > 0) {
      datasets.push({
        type: "scatter",
        label: "Recent Veeder Points",
        data: scatterSeries,
        backgroundColor: "#e94560",
        pointRadius: 4,
      });
    }

    datasets.push({
      type: "scatter",
      label: "Current Entry",
      data: [{ x: Number(candidate.inches), y: Number(candidate.gallons) }],
      backgroundColor: "#50fa7b",
      pointRadius: 7,
    });

    host.preflightCharts[row.preflight_token] = new Chart(canvas, {
      type: "scatter",
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: "#f8f9fa" },
          },
        },
        scales: {
          x: {
            title: {
              display: true,
              text: "Height (in)",
              color: "#a0aec0",
            },
            ticks: { color: "#a0aec0" },
            grid: { color: "#2a2e33" },
          },
          y: {
            title: {
              display: true,
              text: "Volume (gal)",
              color: "#a0aec0",
            },
            ticks: { color: "#a0aec0" },
            grid: { color: "#2a2e33" },
          },
        },
      },
    });
  }

  function renderCharts(host) {
    destroyCharts(host);
    if (typeof Chart !== "function") {
      return;
    }

    (host.preflightRows || []).forEach((row) => {
      renderChartForRow(host, row);
    });
  }

  window.VeederGraphSection = {
    destroyCharts,
    renderCharts,
  };
})();
