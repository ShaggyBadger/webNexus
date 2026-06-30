import { IntelMap } from "./intel_map.js";
import { IntelMapDraw } from "./intel_map_draw.js";

document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("map-edit-canvas");
  if (!container) {
    return;
  }

  const mapController = IntelMap.init("map-edit-canvas");
  const map = mapController ? mapController.instance : null;
  if (!map) {
    console.error("SITEINTEL_MAP_EDIT_INIT_FAILED");
    return;
  }

  const hiddenFieldId = "id_geojson_data";
  const initialData = container.dataset.overlay;
  IntelMapDraw.init(map, hiddenFieldId, initialData);
});
