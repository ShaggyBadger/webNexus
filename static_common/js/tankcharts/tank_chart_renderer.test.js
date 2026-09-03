const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");

function loadRenderer() {
  const window = {
    requestAnimationFrame: (callback) => callback(),
    cancelAnimationFrame: () => {},
    ResizeObserver: class {
      observe() {}
      disconnect() {}
    },
  };
  vm.runInNewContext(
    fs.readFileSync(__dirname + "/tank_chart_renderer.js", "utf8"),
    { window },
  );
  return { renderer: window.TankChartRenderer, window };
}

test("buildDatasets filters invalid points and applies canonical styles", () => {
  const { renderer } = loadRenderer();
  const datasets = renderer.buildDatasets(
    {
      tank: { source_policy: "VEEDER_ONLY" },
      series: {
        official_chart: [{ inches: 1, gallons: 2 }],
        generated_curve: [
          { inches: 1, gallons: 2 },
          { inches: 2, gallons: 4 },
          { inches: Infinity, gallons: 5 },
        ],
        scatter_points: [{ inches: 3, gallons: 6 }, { inches: "bad", gallons: 1 }],
      },
    },
    [{ label: "Current Entry", data: [{ x: 4, y: 8 }, { x: NaN, y: 2 }] }],
  );

  assert.deepEqual(Array.from(datasets, (dataset) => dataset.label), [
    "Generated Curve",
    "Veeder-Root Readings",
    "Current Entry",
  ]);
  assert.equal(datasets[0].borderDash, undefined);
  assert.equal(datasets[0].data.length, 2);
  assert.equal(datasets[1].data.length, 1);
  assert.equal(datasets[2].data.length, 1);
});

test("one-point curves are points-only and empty payloads are explicit", () => {
  const { renderer } = loadRenderer();
  const datasets = renderer.buildDatasets({
    series: { generated_curve: [{ inches: 1, gallons: 2 }] },
  });
  assert.equal(datasets.length, 0);
  assert.deepEqual({ ...renderer.stateFor({}, datasets) }, {
    readiness: "UNAVAILABLE",
    hasCurve: false,
    hasPoints: false,
    pointsOnly: false,
    empty: true,
  });
});

test("render creates and destroys a responsive chart controller", () => {
  const { renderer, window } = loadRenderer();
  let created = 0;
  let destroyed = 0;
  window.Chart = class {
    constructor() { created += 1; }
    resize() {}
    destroy() { destroyed += 1; }
  };
  const canvas = { clientWidth: 320, clientHeight: 200, parentElement: {} };
  const controller = renderer.render(canvas, {
    series: { generated_curve: [{ inches: 1, gallons: 2 }, { inches: 2, gallons: 4 }] },
  });
  assert.equal(created, 1);
  controller.destroy();
  assert.equal(destroyed, 1);
});
