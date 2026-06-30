import { ProposalManager } from "./proposal_manager.js";

document.addEventListener("DOMContentLoaded", () => {
  ProposalManager.init();

  const formsetContainer = document.getElementById("tank-formset-container");
  const addBtn = document.getElementById("add-tank-btn");
  const totalForms = document.getElementById("id_tank_updates-TOTAL_FORMS");
  const emptyFormHtml = document.getElementById("empty-tank-form").innerHTML;

  const latInput = document.getElementById("id_lat");
  const lonInput = document.getElementById("id_lon");

  let map;
  let marker;

  const initMap = (lat, lon) => {
    const defaultLat = lat || 35.7596;
    const defaultLon = lon || -79.0193;
    const zoom = lat ? 18 : 7;

    if (!map) {
      map = L.map("map").setView([defaultLat, defaultLon], zoom);

      if (window.getTacticalTileLayer) {
        window.getTacticalTileLayer(L).addTo(map);
      } else {
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 19,
        }).addTo(map);
      }

      marker = L.marker([defaultLat, defaultLon], { draggable: true }).addTo(map);

      marker.on("dragend", () => {
        const position = marker.getLatLng();
        updateLocation(position.lat, position.lng, map.getZoom());
      });

      map.on("click", (e) => {
        updateLocation(e.latlng.lat, e.latlng.lng, map.getZoom());
      });

      setTimeout(() => map.invalidateSize(), 200);
    } else {
      updateLocation(defaultLat, defaultLon, zoom);
    }
  };

  const checkProximity = async (lat, lon) => {
    if (!lat || !lon) return;
    const excludeNum = document.getElementById("id_store_num").value;
    const container = document.getElementById("proximity-warning");
    const matchesDiv = document.getElementById("proximity-matches");

    try {
      const response = await fetch(
        `/siteintel/api/proximity-check/?lat=${lat}&lon=${lon}&exclude_store_num=${excludeNum}`,
      );
      if (!response.ok) return;
      const data = await response.json();
      if (data.matches && data.matches.length > 0) {
        matchesDiv.innerHTML = "";
        data.matches.forEach((match) => {
          const item = document.createElement("div");
          item.className = "text-white mono mb-1";
          item.innerHTML = `<span class="text-primary fw-bold">#${match.store_num}</span> ${match.store_name} (${match.distance_ft} FT AWAY)`;
          matchesDiv.appendChild(item);
        });
        container.classList.remove("d-none");
      } else {
        container.classList.add("d-none");
      }
    } catch (error) {
      console.warn("PROPOSAL_PROXIMITY_CHECK_FAILED", error);
    }
  };

  const updateLocation = (lat, lon, zoom) => {
    if (lat === undefined || lon === undefined || lat === null || lon === null) return;

    const latVal = parseFloat(lat).toFixed(6);
    const lonVal = parseFloat(lon).toFixed(6);

    latInput.value = latVal;
    lonInput.value = lonVal;

    const currentZoom = map ? map.getZoom() : 7;
    const targetZoom = zoom || (currentZoom < 15 ? 18 : currentZoom);

    if (marker) marker.setLatLng([lat, lon]);
    if (map) {
      map.setView([lat, lon], targetZoom);
      map.invalidateSize();
    }

    checkProximity(latVal, lonVal);
  };

  if (latInput.value && lonInput.value) {
    initMap(parseFloat(latInput.value), parseFloat(lonInput.value));
  } else {
    initMap();
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          updateLocation(pos.coords.latitude, pos.coords.longitude, 18);
        },
        () => {
          console.warn("PROPOSAL_AUTO_GPS_FAILED");
        },
        { enableHighAccuracy: true, timeout: 5000 },
      );
    }
  }

  const captureGps = async () => {
    const btn = document.getElementById("gps-capture-btn");
    const originalText = btn.innerText;
    btn.innerText = "[ ACQUIRING_SIGNAL... ]";
    btn.disabled = true;

    try {
      if (typeof TacticalGPS !== "undefined") {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            updateLocation(pos.coords.latitude, pos.coords.longitude, 18);
            btn.innerText = "[ SIGNAL_LOCKED ]";
            btn.classList.replace("btn-outline-primary", "btn-outline-success");
          },
          () => {
            btn.innerText = "[ SIGNAL_FAILED ]";
            btn.classList.replace("btn-outline-primary", "btn-outline-danger");
          },
          { enableHighAccuracy: true, timeout: 10000 },
        );
      }
    } catch (error) {
      console.error("PROPOSAL_GPS_CAPTURE_FAILED", error);
      btn.innerText = "[ SIGNAL_FAILED ]";
      btn.classList.replace("btn-outline-primary", "btn-outline-danger");
    } finally {
      setTimeout(() => {
        btn.innerText = originalText;
        btn.disabled = false;
        btn.classList.remove("btn-outline-success", "btn-outline-danger");
        btn.classList.add("btn-outline-primary");
      }, 3000);
    }
  };

  document.getElementById("gps-capture-btn").addEventListener("click", captureGps);

  const decodeCoordinates = async () => {
    const lat = latInput.value;
    const lon = lonInput.value;
    if (!lat || !lon) {
      alert("COORDINATE_ERROR: TARGET LAT/LON REQUIRED FOR DECODING");
      return;
    }

    const btn = document.getElementById("geocode-btn");
    const originalText = btn.innerText;
    btn.innerText = "[ DECODING... ]";
    btn.disabled = true;

    try {
      const response = await fetch(`/siteintel/api/reverse-geocode/?lat=${lat}&lon=${lon}`);
      if (response.ok) {
        const data = await response.json();
        if (data.address) document.getElementById("id_address").value = data.address;
        if (data.city) document.getElementById("id_city").value = data.city;
        if (data.state) document.getElementById("id_state").value = data.state;
        if (data.zip_code) document.getElementById("id_zip_code").value = data.zip_code;

        btn.innerText = "[ DECODE_SUCCESS ]";
        btn.classList.replace("btn-outline-info", "btn-outline-success");
      } else {
        btn.innerText = "[ DECODE_FAILED ]";
        btn.classList.replace("btn-outline-info", "btn-outline-danger");
      }
    } catch (error) {
      console.error("PROPOSAL_GEOCODE_FAILED", error);
      btn.innerText = "[ DECODE_ERROR ]";
      btn.classList.replace("btn-outline-info", "btn-outline-danger");
    } finally {
      setTimeout(() => {
        btn.innerText = originalText;
        btn.disabled = false;
        btn.classList.remove("btn-outline-success", "btn-outline-danger");
        btn.classList.add("btn-outline-info");
      }, 3000);
    }
  };

  document.getElementById("geocode-btn").addEventListener("click", decodeCoordinates);

  const typeSelector = document.getElementById("store-type-selector");
  const customTypeInput = document.getElementById("custom-store-type");
  const hiddenTypeInput = document.getElementById("id_store_type");

  typeSelector.addEventListener("change", (e) => {
    if (e.target.value === "CUSTOM") {
      customTypeInput.classList.remove("d-none");
      customTypeInput.focus();
      hiddenTypeInput.value = customTypeInput.value;
    } else {
      customTypeInput.classList.add("d-none");
      hiddenTypeInput.value = e.target.value;
    }
  });

  customTypeInput.addEventListener("input", (e) => {
    hiddenTypeInput.value = e.target.value;
  });

  const initRemoveBtn = (entry) => {
    const btn = entry.querySelector(".remove-tank");
    if (!btn) return;
    btn.addEventListener("click", () => {
      const deleteCheckbox = entry.querySelector('input[name$="-DELETE"]');
      if (deleteCheckbox) {
        deleteCheckbox.checked = true;
        entry.classList.add("d-none");
      } else {
        entry.remove();
        totalForms.value = parseInt(totalForms.value, 10) - 1;
      }
    });
  };

  const initTankPicker = (entry) => {
    const searchContainer = entry.querySelector(".tank-search-container");
    const lockedDisplay = entry.querySelector(".locked-tank-display");
    const capacityInput = entry.querySelector('input[name$="-reported_capacity"]');
    const resultsOverlay = entry.querySelector(".search-results-overlay");
    const tankTypeInput = entry.querySelector('input[name$="-tank_type"]');
    const changeBtn = entry.querySelector(".change-tank-btn");
    const infoMain = entry.querySelector(".tank-info-main");
    const infoSub = entry.querySelector(".tank-info-sub");
    const unverifiedCheck = entry.querySelector('input[name$="-is_unverified"]');

    entry.setLockedState = (name, capacity, depth) => {
      infoMain.innerText = name;
      infoSub.innerText = `${capacity} GAL // ${depth}" DEPTH`;
      searchContainer.classList.add("d-none");
      lockedDisplay.classList.remove("d-none");
    };

    entry.setSearchState = () => {
      searchContainer.classList.remove("d-none");
      lockedDisplay.classList.add("d-none");
    };

    capacityInput.addEventListener("input", async (e) => {
      const cap = e.target.value;
      if (!cap || cap.length < 2) {
        resultsOverlay.classList.add("d-none");
        return;
      }

      try {
        const response = await fetch(`/siteintel/api/tank-search/?capacity=${cap}`);
        if (!response.ok) return;
        const data = await response.json();
        if (data.results.length > 0) {
          resultsOverlay.innerHTML = "";
          data.results.forEach((match) => {
            const item = document.createElement("div");
            item.className = "search-item";
            item.innerHTML = `<span class="text-primary">${match.name}</span> (${match.capacity} GAL / ${match.max_depth}")`;
            item.addEventListener("click", () => {
              tankTypeInput.value = match.id;
              entry.setLockedState(match.name, match.capacity, match.max_depth);
              resultsOverlay.classList.add("d-none");
              unverifiedCheck.checked = false;
            });
            resultsOverlay.appendChild(item);
          });
          resultsOverlay.classList.remove("d-none");
        } else {
          resultsOverlay.innerHTML =
            '<div class="p-2 text-muted" style="font-size: 0.7rem;">NO MATCHES FOUND</div>';
          resultsOverlay.classList.remove("d-none");
        }
      } catch (error) {
        console.error("PROPOSAL_TANK_SEARCH_FAILED", error);
      }
    });

    changeBtn.addEventListener("click", () => {
      tankTypeInput.value = "";
      entry.setSearchState();
      capacityInput.focus();
    });

    document.addEventListener("click", (e) => {
      if (!entry.contains(e.target)) {
        resultsOverlay.classList.add("d-none");
      }
    });
  };

  const fetchStoreData = async (storeNum, isInitialLoad = false) => {
    if (!storeNum) return;
    try {
      const response = await fetch(`/siteintel/api/store-lookup/?q=${storeNum}`);
      if (!response.ok) return;

      const data = await response.json();
      document.getElementById("id_riso_num").value = data.riso_num || "";
      document.getElementById("id_store_name").value = data.store_name || "";

      if (data.store_type) {
        const optionExists = Array.from(typeSelector.options).some(
          (opt) => opt.value === data.store_type,
        );
        if (optionExists) {
          typeSelector.value = data.store_type;
          customTypeInput.classList.add("d-none");
        } else {
          typeSelector.value = "CUSTOM";
          customTypeInput.classList.remove("d-none");
          customTypeInput.value = data.store_type;
        }
        hiddenTypeInput.value = data.store_type;
      }

      document.getElementById("id_address").value = data.address || "";
      document.getElementById("id_city").value = data.city || "";
      document.getElementById("id_state").value = data.state || "";
      document.getElementById("id_zip_code").value = data.zip_code || "";

      if (data.lat && data.lon) {
        updateLocation(data.lat, data.lon);
      }

      if (data.tanks && data.tanks.length > 0) {
        if (!isInitialLoad) {
          formsetContainer.innerHTML = "";
          totalForms.value = "0";
        }

        const existingEntries = formsetContainer.querySelectorAll(".tank-entry");
        data.tanks.forEach((tank, idx) => {
          let entry;
          if (!isInitialLoad) {
            addBtn.click();
            entry = formsetContainer.lastElementChild;
          } else {
            entry = existingEntries[idx];
          }

          if (!entry) return;
          entry.querySelector('input[name$="-tank_index"]').value = tank.tank_index;

          const fuelField = entry.querySelector('[name$="-fuel_type"]');
          if (fuelField) {
            fuelField.value = (tank.fuel_type || "").toLowerCase();
          }

          entry.querySelector('input[name$="-reported_capacity"]').value = tank.capacity;

          if (tank.tank_type_id) {
            entry.querySelector('input[name$="-tank_type"]').value = tank.tank_type_id;
            if (entry.setLockedState) {
              entry.setLockedState(tank.tank_type_name, tank.capacity, tank.max_depth);
            }
          }
        });
      }

      const input = document.getElementById("id_store_num");
      input.classList.add("is-valid");
      setTimeout(() => input.classList.remove("is-valid"), 2000);
    } catch (error) {
      console.warn("PROPOSAL_STORE_LOOKUP_FAILED", error);
    }
  };

  const storeNumInput = document.getElementById("id_store_num");
  storeNumInput.addEventListener("change", (e) => fetchStoreData(e.target.value));

  const urlParams = new URLSearchParams(window.location.search);
  const urlStoreNum = urlParams.get("store_num");
  if (urlStoreNum) {
    fetchStoreData(urlStoreNum, true);
  }

  addBtn.addEventListener("click", () => {
    const formIdx = parseInt(totalForms.value, 10);
    const newForm = emptyFormHtml.replace(/__prefix__/g, formIdx);

    const wrapper = document.createElement("div");
    wrapper.innerHTML = newForm;
    const node = wrapper.firstElementChild;
    node.setAttribute("data-index", formIdx);

    formsetContainer.appendChild(node);
    totalForms.value = formIdx + 1;

    initTankPicker(node);
    initRemoveBtn(node);
  });

  document.querySelectorAll(".tank-entry").forEach((entry) => {
    initTankPicker(entry);
    initRemoveBtn(entry);
  });

  const customAttrBtn = document.getElementById("add-custom-attr-btn");
  const customAttrContainer = document.getElementById("custom-attributes-container");
  const customMetadataInput = document.getElementById("id_custom_metadata_json");

  const updateCustomMetadataJson = () => {
    const data = {};
    customAttrContainer.querySelectorAll(".custom-attr-row").forEach((row) => {
      const key = row.querySelector(".attr-key").value.trim();
      const val = row.querySelector(".attr-val").value.trim();
      if (key) data[key] = val;
    });
    customMetadataInput.value = JSON.stringify(data);
  };

  const createCustomAttrRow = (key = "", val = "") => {
    const row = document.createElement("div");
    row.className = "col-12 custom-attr-row";
    row.innerHTML = `
      <div class="input-group input-group-sm">
        <input type="text" class="form-control mono attr-key" placeholder="KEY (e.g. GATE_CODE)" value="${key}" style="width: 30%;">
        <input type="text" class="form-control mono attr-val" placeholder="VALUE" value="${val}">
        <button type="button" class="btn btn-outline-danger remove-attr-btn">[ X ]</button>
      </div>
    `;

    row.querySelector(".remove-attr-btn").addEventListener("click", () => {
      row.remove();
      updateCustomMetadataJson();
    });

    row.querySelectorAll("input").forEach((input) => {
      input.addEventListener("input", updateCustomMetadataJson);
    });

    customAttrContainer.appendChild(row);
  };

  if (customMetadataInput.value) {
    try {
      const existingData = JSON.parse(customMetadataInput.value);
      Object.entries(existingData).forEach(([key, val]) => {
        createCustomAttrRow(key, val);
      });
    } catch (error) {
      console.warn("PROPOSAL_CUSTOM_METADATA_PARSE_FAILED", error);
    }
  }

  customAttrBtn.addEventListener("click", () => createCustomAttrRow());
});
