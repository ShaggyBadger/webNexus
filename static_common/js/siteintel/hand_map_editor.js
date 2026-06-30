function getCsrfToken() {
  const metaToken = document.querySelector('meta[name="csrf-token"]')?.content;
  if (metaToken) {
    return metaToken;
  }

  const cookieValue = document.cookie
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith("csrftoken="));
  return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
}

document.addEventListener("DOMContentLoaded", function () {
  const container = document.getElementById("canvas-container");
  const canvasElement = document.getElementById("hand-map-canvas");
  if (!container || !canvasElement || typeof fabric === "undefined") {
    return;
  }

  const saveUrl = container.dataset.saveUrl;
  const returnUrl = container.dataset.returnUrl;
  const existingMapJson = container.dataset.existingMapJson || "";
  const modeToggle = document.getElementById("mode-toggle");
  const controlsPanel = document.querySelector(".map-controls");
  const toggleControlsButton = document.getElementById("btn-toggle-controls");
  const zoomInButton = document.getElementById("btn-zoom-in");
  const zoomOutButton = document.getElementById("btn-zoom-out");

  const canvas = new fabric.Canvas("hand-map-canvas", {
    isDrawingMode: true,
    width: window.innerWidth,
    height: window.innerHeight,
    backgroundColor: "#1a1d21",
  });

  let currentTool = "brush";
  let isPanningMode = false;
  let isDrawingArrow = false;
  let arrowLine;
  let stateStack = [];
  let redoStack = [];
  let isProcessingStack = false;
  let initialDistance = null;
  let controlsCollapsed = false;

  canvas.freeDrawingBrush = new fabric.PencilBrush(canvas);
  canvas.freeDrawingBrush.color = "#ffb86c";
  canvas.freeDrawingBrush.width = 3;

  function saveState() {
    if (isProcessingStack) return;
    const state = JSON.stringify(canvas.toJSON());
    if (stateStack.length > 0 && stateStack[stateStack.length - 1] === state) return;

    stateStack.push(state);
    if (stateStack.length > 30) stateStack.shift();
    redoStack = [];
    updateUndoRedoUI();
  }

  function updateUndoRedoUI() {
    document.getElementById("btn-undo").disabled = stateStack.length <= 1;
    document.getElementById("btn-redo").disabled = redoStack.length === 0;
  }

  canvas.on("object:added", saveState);
  canvas.on("object:modified", saveState);
  canvas.on("object:removed", saveState);

  document.getElementById("btn-undo").addEventListener("click", function () {
    if (stateStack.length <= 1) return;
    isProcessingStack = true;
    redoStack.push(stateStack.pop());
    const previousState = stateStack[stateStack.length - 1];
    canvas.loadFromJSON(previousState, function () {
      canvas.renderAll();
      isProcessingStack = false;
      updateUndoRedoUI();
    });
  });

  document.getElementById("btn-redo").addEventListener("click", function () {
    if (redoStack.length === 0) return;
    isProcessingStack = true;
    const state = redoStack.pop();
    stateStack.push(state);
    canvas.loadFromJSON(state, function () {
      canvas.renderAll();
      isProcessingStack = false;
      updateUndoRedoUI();
    });
  });

  function setActiveTool(tool) {
    currentTool = tool;

    document.querySelectorAll("#btn-brush, #btn-eraser, #btn-arrow").forEach((button) => {
      button.classList.remove("btn-primary");
      button.classList.add("btn-outline-secondary");
    });
    document
      .getElementById(`btn-${tool}`)
      .classList.replace("btn-outline-secondary", "btn-primary");

    updateCanvasMode();

    if (tool === "eraser") {
      if (fabric.EraserBrush) {
        canvas.freeDrawingBrush = new fabric.EraserBrush(canvas);
      } else {
        canvas.freeDrawingBrush.color = "#1a1d21";
      }
    } else if (tool === "brush") {
      canvas.freeDrawingBrush = new fabric.PencilBrush(canvas);
      canvas.freeDrawingBrush.color =
        document.querySelector(".color-btn.active").getAttribute("data-color");
    }

    canvas.freeDrawingBrush.width =
      parseInt(document.getElementById("stroke-width").value, 10) || 3;
  }

  function updateCanvasMode() {
    const isAdvanced = modeToggle.checked;
    if (isPanningMode) {
      canvas.isDrawingMode = false;
      canvas.selection = false;
    } else if (isAdvanced) {
      canvas.isDrawingMode = false;
      canvas.selection = true;
    } else {
      canvas.isDrawingMode = currentTool === "brush" || currentTool === "eraser";
      canvas.selection = false;
    }
  }

  document.getElementById("btn-brush").addEventListener("click", () => setActiveTool("brush"));
  document.getElementById("btn-eraser").addEventListener("click", () => setActiveTool("eraser"));
  document.getElementById("btn-arrow").addEventListener("click", () => setActiveTool("arrow"));

  function updateZoomDisplay() {
    const zoom = Math.round(canvas.getZoom() * 100);
    document.getElementById("zoom-level").innerText = `ZOOM: ${zoom}%`;
  }

  function applyZoom(multiplier) {
    const center = new fabric.Point(canvas.getWidth() / 2, canvas.getHeight() / 2);
    let zoom = canvas.getZoom() * multiplier;
    if (zoom > 20) zoom = 20;
    if (zoom < 0.05) zoom = 0.05;
    canvas.zoomToPoint(center, zoom);
    canvas.requestRenderAll();
    updateZoomDisplay();
  }

  function getEventCoordinates(evt) {
    if (evt.touches && evt.touches.length > 0) {
      return { x: evt.touches[0].clientX, y: evt.touches[0].clientY };
    }
    if (evt.clientX !== undefined) {
      return { x: evt.clientX, y: evt.clientY };
    }
    return { x: null, y: null };
  }

  canvas.on("mouse:wheel", function (opt) {
    const delta = opt.e.deltaY;
    let zoom = canvas.getZoom() * 0.999 ** delta;
    if (zoom > 20) zoom = 20;
    if (zoom < 0.05) zoom = 0.05;
    canvas.zoomToPoint({ x: opt.e.offsetX, y: opt.e.offsetY }, zoom);
    opt.e.preventDefault();
    opt.e.stopPropagation();
    updateZoomDisplay();
  });

  canvas.on("touch:gesture", function (opt) {
    if (opt.e.touches && opt.e.touches.length === 2) {
      const touch1 = opt.e.touches[0];
      const touch2 = opt.e.touches[1];
      const distance = Math.hypot(
        touch1.clientX - touch2.clientX,
        touch1.clientY - touch2.clientY,
      );
      if (initialDistance === null) {
        initialDistance = distance;
      } else {
        let zoom = canvas.getZoom() * (distance / initialDistance);
        if (zoom > 20) zoom = 20;
        if (zoom < 0.05) zoom = 0.05;
        canvas.zoomToPoint(
          { x: (touch1.clientX + touch2.clientX) / 2, y: (touch1.clientY + touch2.clientY) / 2 },
          zoom,
        );
        initialDistance = distance;
        updateZoomDisplay();
      }
    }
  });

  if (zoomInButton) {
    zoomInButton.addEventListener("click", function () {
      applyZoom(1.12);
    });
  }

  if (zoomOutButton) {
    zoomOutButton.addEventListener("click", function () {
      applyZoom(0.88);
    });
  }

  if (toggleControlsButton && controlsPanel) {
    toggleControlsButton.addEventListener("click", function () {
      controlsCollapsed = !controlsCollapsed;
      controlsPanel.classList.toggle("collapsed", controlsCollapsed);
      toggleControlsButton.innerText = controlsCollapsed
        ? "[ SHOW_TOOLS ]"
        : "[ HIDE_TOOLS ]";
    });
  }

  canvas.on("mouse:down", function (opt) {
    const evt = opt.e;
    const pointer = canvas.getPointer(evt);

    if (evt.altKey === true || isPanningMode) {
      this.isDragging = true;
      this.selection = false;
      const coords = getEventCoordinates(evt);
      this.lastPosX = coords.x;
      this.lastPosY = coords.y;
      return;
    }

    if (currentTool === "arrow" && !modeToggle.checked) {
      isDrawingArrow = true;
      const points = [pointer.x, pointer.y, pointer.x, pointer.y];
      arrowLine = new fabric.Line(points, {
        strokeWidth: canvas.freeDrawingBrush.width,
        stroke: document.querySelector(".color-btn.active").getAttribute("data-color"),
        originX: "center",
        originY: "center",
        selectable: false,
      });
      canvas.add(arrowLine);
    }
  });

  canvas.on("mouse:move", function (opt) {
    if (this.isDragging) {
      const coords = getEventCoordinates(opt.e);
      if (coords.x !== null && this.lastPosX !== undefined) {
        const vpt = this.viewportTransform;
        vpt[4] += coords.x - this.lastPosX;
        vpt[5] += coords.y - this.lastPosY;
        this.requestRenderAll();
        this.lastPosX = coords.x;
        this.lastPosY = coords.y;
      }
      return;
    }

    if (isDrawingArrow) {
      const pointer = canvas.getPointer(opt.e);
      arrowLine.set({ x2: pointer.x, y2: pointer.y });
      canvas.renderAll();
    }
  });

  canvas.on("mouse:up", function (opt) {
    if (this.isDragging) {
      this.setViewportTransform(this.viewportTransform);
      this.isDragging = false;
      this.selection = true;
    }

    if (isDrawingArrow) {
      const pointer = canvas.getPointer(opt.e);
      const x1 = arrowLine.x1;
      const y1 = arrowLine.y1;
      const x2 = pointer.x;
      const y2 = pointer.y;
      const angle = (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI;

      const arrowHead = new fabric.Triangle({
        left: x2,
        top: y2,
        originX: "center",
        originY: "center",
        angle: angle + 90,
        width: 15 + canvas.freeDrawingBrush.width,
        height: 15 + canvas.freeDrawingBrush.width,
        fill: arrowLine.stroke,
        selectable: false,
      });

      const group = new fabric.Group([arrowLine, arrowHead], {
        selectable: modeToggle.checked,
      });

      canvas.remove(arrowLine);
      canvas.add(group);
      isDrawingArrow = false;
      saveState();
    }
    initialDistance = null;
  });

  document.getElementById("btn-toggle-pan").addEventListener("click", function () {
    isPanningMode = !isPanningMode;
    this.innerText = isPanningMode ? "[ PAN_MODE: ON ]" : "[ PAN_MODE: OFF ]";
    this.classList.toggle("btn-warning");
    this.classList.toggle("btn-outline-warning");
    updateCanvasMode();
  });

  document.getElementById("btn-reset-view").addEventListener("click", function () {
    canvas.setZoom(1);
    canvas.viewportTransform = [1, 0, 0, 1, 0, 0];
    canvas.renderAll();
    updateZoomDisplay();
  });

  modeToggle.addEventListener("change", function () {
    const labelBasic = document.getElementById("label-basic");
    const labelAdvanced = document.getElementById("label-advanced");
    const advancedTools = document.querySelector(".advanced-tools");

    if (this.checked) {
      labelBasic.classList.remove("active");
      labelAdvanced.classList.add("active");
      advancedTools.classList.add("show");
      canvas.forEachObject((obj) => {
        obj.selectable = true;
      });
    } else {
      labelBasic.classList.add("active");
      labelAdvanced.classList.remove("active");
      advancedTools.classList.remove("show");
      canvas.forEachObject((obj) => {
        obj.selectable = false;
      });
    }
    updateCanvasMode();
  });

  document.getElementById("btn-add-text").addEventListener("click", function () {
    const vpt = canvas.viewportTransform;
    const centerX = (canvas.width / 2 - vpt[4]) / vpt[0];
    const centerY = (canvas.height / 2 - vpt[5]) / vpt[3];
    canvas.add(
      new fabric.IText("NEW_LABEL", {
        left: centerX,
        top: centerY,
        fontFamily: "JetBrains Mono",
        fontSize: 20 / vpt[0],
        fill: document.querySelector(".color-btn.active").getAttribute("data-color"),
        selectable: true,
      }),
    );
  });

  document.getElementById("btn-add-rect").addEventListener("click", function () {
    const vpt = canvas.viewportTransform;
    const centerX = (canvas.width / 2 - vpt[4]) / vpt[0];
    const centerY = (canvas.height / 2 - vpt[5]) / vpt[3];
    canvas.add(
      new fabric.Rect({
        left: centerX - 50,
        top: centerY - 50,
        width: 100,
        height: 100,
        fill: "transparent",
        stroke: document.querySelector(".color-btn.active").getAttribute("data-color"),
        strokeWidth: canvas.freeDrawingBrush.width,
        selectable: true,
      }),
    );
  });

  document.getElementById("btn-add-callout").addEventListener("click", function () {
    const vpt = canvas.viewportTransform;
    const centerX = (canvas.width / 2 - vpt[4]) / vpt[0];
    const centerY = (canvas.height / 2 - vpt[5]) / vpt[3];
    const color = document.querySelector(".color-btn.active").getAttribute("data-color");
    const text = new fabric.IText("CALLOUT", {
      fontFamily: "JetBrains Mono",
      fontSize: 16 / vpt[0],
      fill: "#000",
      originX: "center",
      originY: "center",
    });
    const rect = new fabric.Rect({
      fill: color,
      width: text.width + 20,
      height: text.height + 10,
      originX: "center",
      originY: "center",
      rx: 5,
      ry: 5,
    });
    canvas.add(new fabric.Group([rect, text], { left: centerX, top: centerY, selectable: true }));
  });

  document.getElementById("btn-delete-selected").addEventListener("click", function () {
    canvas.remove(...canvas.getActiveObjects());
    canvas.discardActiveObject();
  });

  document.getElementById("btn-clear-canvas").addEventListener("click", function () {
    if (confirm("CLEAR_CANVAS?")) {
      canvas.clear();
      canvas.backgroundColor = "#1a1d21";
      canvas.setZoom(1);
      canvas.viewportTransform = [1, 0, 0, 1, 0, 0];
      canvas.renderAll();
      updateZoomDisplay();
    }
  });

  document.querySelectorAll(".color-btn").forEach((button) => {
    button.addEventListener("click", function () {
      const color = this.getAttribute("data-color");
      if (currentTool === "brush") {
        canvas.freeDrawingBrush.color = color;
      }
      const activeObj = canvas.getActiveObject();
      if (activeObj) {
        if (activeObj.type === "i-text") {
          activeObj.set("fill", color);
        } else if (activeObj.type === "group" && activeObj._objects[0].type === "rect") {
          activeObj._objects[0].set("fill", color);
        } else {
          activeObj.set("stroke", color);
        }
        canvas.renderAll();
        saveState();
      }
      document.querySelectorAll(".color-btn").forEach((swatch) => swatch.classList.remove("active"));
      this.classList.add("active");
    });
  });

  document.getElementById("stroke-width").addEventListener("input", function () {
    const width = parseInt(this.value, 10) || 1;
    canvas.freeDrawingBrush.width = width;
    const activeObj = canvas.getActiveObject();
    if (activeObj && activeObj.type !== "i-text") {
      activeObj.set("strokeWidth", width);
      canvas.renderAll();
      saveState();
    }
  });

  if (existingMapJson) {
    try {
      canvas.loadFromJSON(JSON.parse(existingMapJson), () => {
        canvas.renderAll();
        canvas.forEachObject((obj) => {
          obj.selectable = modeToggle.checked;
        });
        updateZoomDisplay();
        stateStack = [JSON.stringify(canvas.toJSON())];
        updateUndoRedoUI();
      });
    } catch (error) {
      console.error("HAND_MAP_LOAD_ERROR", error);
    }
  } else {
    stateStack = [JSON.stringify(canvas.toJSON())];
    updateUndoRedoUI();
  }

  document.getElementById("btn-save-map").addEventListener("click", function () {
    const button = this;
    button.disabled = true;
    button.innerText = "[ COMMITTING... ]";

    const currentZoom = canvas.getZoom();
    const currentViewport = canvas.viewportTransform.slice();
    canvas.setZoom(1);
    canvas.viewportTransform = [1, 0, 0, 1, 0, 0];
    canvas.renderAll();

    const objects = canvas.getObjects();
    let exportData = { left: 0, top: 0, width: canvas.width, height: canvas.height };
    if (objects.length > 0) {
      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;
      objects.forEach((obj) => {
        const bounds = obj.getBoundingRect(true);
        minX = Math.min(minX, bounds.left);
        minY = Math.min(minY, bounds.top);
        maxX = Math.max(maxX, bounds.left + bounds.width);
        maxY = Math.max(maxY, bounds.top + bounds.height);
      });
      const padding = 50;
      exportData = {
        left: minX - padding,
        top: minY - padding,
        width: maxX - minX + padding * 2,
        height: maxY - minY + padding * 2,
      };
    }

    const fabricJson = JSON.stringify(canvas.toJSON());
    const imageData = canvas.toDataURL({ format: "png", ...exportData, quality: 0.9 });

    canvas.setZoom(currentZoom);
    canvas.viewportTransform = currentViewport;
    canvas.renderAll();

    fetch(saveUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ fabric_json: fabricJson, image_data: imageData }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "success") {
          window.location.href = returnUrl;
          return;
        }
        alert(`ERROR: ${data.message}`);
        button.disabled = false;
        button.innerText = "[ COMMIT_INTEL ]";
      })
      .catch((error) => {
        console.error("HAND_MAP_SAVE_ERROR", error);
        alert("CRITICAL_FAILURE");
        button.disabled = false;
        button.innerText = "[ COMMIT_INTEL ]";
      });
  });

  setActiveTool("brush");
  updateZoomDisplay();
  window.addEventListener("resize", () => {
    canvas.setWidth(window.innerWidth);
    canvas.setHeight(window.innerHeight);
    canvas.renderAll();
  });
});
