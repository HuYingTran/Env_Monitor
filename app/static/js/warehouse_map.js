(function () {
  const mapEl = document.getElementById("warehouseMap");
  if (!mapEl) return;

  const warehouseId = mapEl.dataset.warehouseId;
  const canEdit = mapEl.dataset.canEdit === "true";

  const toggleBtn = document.getElementById("toggleEditMode");
  const toolbar = document.getElementById("editToolbar");
  const drawZoneBtn = document.getElementById("drawZoneBtn");
  const addSensorBtn = document.getElementById("addSensorBtn");
  const placeSensorBtn = document.getElementById("placeSensorBtn");
  const unplacedSensorSelect = document.getElementById("unplacedSensorSelect");
  const editHint = document.getElementById("editHint");

  const zoneModalEl = document.getElementById("zoneModal");
  const sensorModalEl = document.getElementById("sensorModal");
  const sensorInfoModalEl = document.getElementById("sensorInfoModal");
  const zoneModal = zoneModalEl ? new bootstrap.Modal(zoneModalEl) : null;
  const sensorModal = sensorModalEl ? new bootstrap.Modal(sensorModalEl) : null;
  const sensorInfoModal = sensorInfoModalEl ? new bootstrap.Modal(sensorInfoModalEl) : null;

  let editMode = false;
  let mode = null; // 'zone' | 'sensor' | 'place' | null
  let pendingRect = null; // {x, y, width, height} in %
  let pendingPoint = null; // {x, y} in %
  let drawingDiv = null;
  let dragSensorEl = null;
  let dragMoved = false;
  let activeSensorId = null;

  function pct(value, total) {
    return Math.max(0, Math.min(100, (value / total) * 100));
  }

  function getRelativePoint(clientX, clientY) {
    const rect = mapEl.getBoundingClientRect();
    return {
      x: pct(clientX - rect.left, rect.width),
      y: pct(clientY - rect.top, rect.height),
    };
  }

  function setHint(text) {
    if (editHint) editHint.textContent = text;
  }

  function setEditMode(on) {
    editMode = on;
    toolbar.classList.toggle("d-none", !editMode);
    toggleBtn.textContent = editMode ? "Tắt chế độ chỉnh sửa" : "Bật chế độ chỉnh sửa";
    toggleBtn.classList.toggle("btn-primary", !editMode);
    toggleBtn.classList.toggle("btn-warning", editMode);
    if (!editMode) {
      mode = null;
      setHint("");
    }
  }

  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => setEditMode(!editMode));
  }

  // ---------- Vẽ vùng (zone) ----------
  if (drawZoneBtn) {
    drawZoneBtn.addEventListener("click", () => {
      mode = mode === "zone" ? null : "zone";
      setHint(mode === "zone" ? "Kéo chuột trên bản đồ để vẽ vùng." : "");
    });
  }

  if (addSensorBtn) {
    addSensorBtn.addEventListener("click", () => {
      mode = mode === "sensor" ? null : "sensor";
      setHint(mode === "sensor" ? "Click vào bản đồ để đặt vị trí cảm biến." : "");
    });
  }

  // ---------- Đặt vị trí cho cảm biến đã đăng ký (chưa có tọa độ) ----------
  if (placeSensorBtn) {
    placeSensorBtn.addEventListener("click", () => {
      if (!unplacedSensorSelect.value) {
        alert("Chọn một cảm biến trước.");
        return;
      }
      mode = mode === "place" ? null : "place";
      setHint(mode === "place" ? "Click vào bản đồ để đặt vị trí cho cảm biến đã chọn." : "");
    });
  }

  // Vừa đăng ký cảm biến mới từ trang Thiết bị -> tự bật chế độ chỉnh sửa và
  // vào thẳng chế độ đặt vị trí cho cảm biến đó, khỏi cần bấm thêm.
  const autoPlaceSensorId = mapEl.dataset.autoPlaceSensor;
  if (canEdit && autoPlaceSensorId && unplacedSensorSelect) {
    const option = unplacedSensorSelect.querySelector(`option[value="${autoPlaceSensorId}"]`);
    if (option) {
      setEditMode(true);
      unplacedSensorSelect.value = autoPlaceSensorId;
      mode = "place";
      setHint(`Click vào bản đồ để đặt vị trí cho "${option.dataset.name}".`);
    }
  }

  mapEl.addEventListener("click", async (e) => {
    if (!editMode || mode !== "place") return;
    if (e.target.closest(".map-marker") || e.target.closest(".map-zone")) return;
    const option = unplacedSensorSelect.selectedOptions[0];
    if (!option) return;
    const sensorId = option.value;
    const sensorName = option.dataset.name;
    const point = getRelativePoint(e.clientX, e.clientY);

    const res = await fetch(`/api/sensors/${sensorId}/position`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(point),
    });
    if (res.ok) {
      addMarkerToDom(sensorId, sensorName, point.x, point.y, "unknown", option.dataset);
      option.remove();
      if (!unplacedSensorSelect.options.length) {
        unplacedSensorSelect.closest("div").remove();
      }
      mode = null;
      setHint("");
    } else {
      alert("Không thể lưu vị trí.");
    }
  });

  mapEl.addEventListener("mousedown", (e) => {
    if (!editMode || mode !== "zone") return;
    if (e.target.closest(".map-marker") || e.target.closest(".map-zone")) return;
    const start = getRelativePoint(e.clientX, e.clientY);
    drawingDiv = document.createElement("div");
    drawingDiv.className = "map-zone editable";
    drawingDiv.style.borderColor = "#3b82f6";
    drawingDiv.style.left = start.x + "%";
    drawingDiv.style.top = start.y + "%";
    drawingDiv.style.width = "0%";
    drawingDiv.style.height = "0%";
    mapEl.appendChild(drawingDiv);

    function onMove(ev) {
      const cur = getRelativePoint(ev.clientX, ev.clientY);
      const x = Math.min(start.x, cur.x);
      const y = Math.min(start.y, cur.y);
      const width = Math.abs(cur.x - start.x);
      const height = Math.abs(cur.y - start.y);
      drawingDiv.style.left = x + "%";
      drawingDiv.style.top = y + "%";
      drawingDiv.style.width = width + "%";
      drawingDiv.style.height = height + "%";
      pendingRect = { x, y, width, height };
    }

    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      if (!pendingRect || pendingRect.width < 1 || pendingRect.height < 1) {
        if (drawingDiv) drawingDiv.remove();
        drawingDiv = null;
        pendingRect = null;
        return;
      }
      document.getElementById("zoneName").value = "";
      document.getElementById("zoneColor").value = "#3b82f6";
      zoneModal.show();
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });

  const zoneSaveBtn = document.getElementById("zoneSaveBtn");
  if (zoneSaveBtn) {
    zoneSaveBtn.addEventListener("click", async () => {
      const name = document.getElementById("zoneName").value.trim();
      const color = document.getElementById("zoneColor").value;
      if (!name || !pendingRect) return;
      const res = await fetch(`/api/warehouse/${warehouseId}/zones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...pendingRect, name, color }),
      });
      if (res.ok) {
        const zone = await res.json();
        drawingDiv.dataset.zoneId = zone.id;
        drawingDiv.style.borderColor = zone.color;
        const label = document.createElement("span");
        label.className = "map-zone-label";
        label.style.color = zone.color;
        label.textContent = zone.name;
        drawingDiv.appendChild(label);
        if (canEdit) {
          const del = document.createElement("a");
          del.href = "#";
          del.className = "zone-delete";
          del.dataset.zoneId = zone.id;
          del.title = "Xóa vùng";
          del.innerHTML =
            '<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor">' +
            '<path d="M5.5 5.5a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>' +
            '<path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>' +
            "</svg>";
          drawingDiv.appendChild(del);
        }
        attachZoneEvents(drawingDiv);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.error || "Không thể lưu vùng.");
        drawingDiv.remove();
      }
      drawingDiv = null;
      pendingRect = null;
      zoneModal.hide();
    });
  }

  // ---------- Kéo thả vùng (zone) ----------
  function attachZoneEvents(zone) {
    zone.addEventListener("mousedown", (e) => {
      if (!editMode || mode) return;
      if (e.target.closest(".zone-delete")) return;
      e.preventDefault();
      e.stopPropagation();

      const width = parseFloat(zone.style.width);
      const height = parseFloat(zone.style.height);
      const startPoint = getRelativePoint(e.clientX, e.clientY);
      const startX = parseFloat(zone.style.left);
      const startY = parseFloat(zone.style.top);
      let moved = false;

      function onMove(ev) {
        moved = true;
        const cur = getRelativePoint(ev.clientX, ev.clientY);
        const newX = Math.max(0, Math.min(100 - width, startX + (cur.x - startPoint.x)));
        const newY = Math.max(0, Math.min(100 - height, startY + (cur.y - startPoint.y)));
        zone.style.left = newX + "%";
        zone.style.top = newY + "%";
      }

      function onUp() {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        if (moved) {
          fetch(`/api/zones/${zone.dataset.zoneId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ x: parseFloat(zone.style.left), y: parseFloat(zone.style.top) }),
          });
        }
      }

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }

  document.querySelectorAll(".map-zone").forEach(attachZoneEvents);

  mapEl.addEventListener("click", (e) => {
    const delBtn = e.target.closest(".zone-delete");
    if (delBtn) {
      e.preventDefault();
      const zoneId = delBtn.dataset.zoneId;
      if (!confirm("Xóa vùng này?")) return;
      fetch(`/api/zones/${zoneId}`, { method: "DELETE" }).then((res) => {
        if (res.ok) delBtn.closest(".map-zone").remove();
      });
    }
  });

  // ---------- Thêm cảm biến ----------
  mapEl.addEventListener("click", (e) => {
    if (!editMode || mode !== "sensor") return;
    if (e.target.closest(".map-marker") || e.target.closest(".map-zone")) return;
    pendingPoint = getRelativePoint(e.clientX, e.clientY);
    document.getElementById("sensorName").value = "";
    document.getElementById("sensorCode").value = "";
    document.getElementById("sensorWarning").value = "";
    document.getElementById("sensorCritical").value = "";
    sensorModal.show();
  });

  const sensorSaveBtn = document.getElementById("sensorSaveBtn");
  if (sensorSaveBtn) {
    sensorSaveBtn.addEventListener("click", async () => {
      if (!pendingPoint) return;
      const payload = {
        ...pendingPoint,
        name: document.getElementById("sensorName").value.trim(),
        sensor_code: document.getElementById("sensorCode").value.trim(),
        warning_threshold: document.getElementById("sensorWarning").value || null,
        critical_threshold: document.getElementById("sensorCritical").value || null,
      };
      if (!payload.name || !payload.sensor_code) {
        alert("Vui lòng nhập tên và mã cảm biến.");
        return;
      }
      const res = await fetch(`/api/warehouse/${warehouseId}/sensors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const sensor = await res.json();
        addMarkerToDom(sensor.id, sensor.name, sensor.x, sensor.y, "unknown", {
          warningThreshold: payload.warning_threshold || "",
          criticalThreshold: payload.critical_threshold || "",
        });
        sensorModal.hide();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.error || "Không thể lưu cảm biến.");
      }
      pendingPoint = null;
    });
  }

  function addMarkerToDom(id, name, x, y, status, extra) {
    extra = extra || {};
    const marker = document.createElement("div");
    marker.className = `map-marker status-${status} editable`;
    marker.dataset.sensorId = id;
    marker.dataset.sensorName = name;
    marker.dataset.zoneId = extra.zoneId || "";
    marker.dataset.warningThreshold = extra.warningThreshold || "";
    marker.dataset.criticalThreshold = extra.criticalThreshold || "";
    marker.style.left = x + "%";
    marker.style.top = y + "%";
    marker.title = name;
    mapEl.appendChild(marker);
    attachMarkerEvents(marker);
  }

  // ---------- Kéo thả / click marker ----------
  function attachMarkerEvents(marker) {
    marker.addEventListener("mousedown", (e) => {
      if (!editMode) return;
      e.preventDefault();
      dragSensorEl = marker;
      dragMoved = false;

      function onMove(ev) {
        dragMoved = true;
        const point = getRelativePoint(ev.clientX, ev.clientY);
        marker.style.left = point.x + "%";
        marker.style.top = point.y + "%";
      }

      function onUp(ev) {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        if (dragMoved) {
          const point = getRelativePoint(ev.clientX, ev.clientY);
          fetch(`/api/sensors/${marker.dataset.sensorId}/position`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(point),
          });
        }
        dragSensorEl = null;
      }

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });

    marker.addEventListener("click", () => {
      if (dragMoved) {
        dragMoved = false;
        return;
      }
      showSensorModal(marker.dataset);
    });
  }

  document.querySelectorAll(".map-marker").forEach(attachMarkerEvents);

  // ---------- Xem / sửa thông tin cảm biến (marker hoặc nút "Sửa" trong bảng) ----------
  async function showSensorModal(ds) {
    activeSensorId = ds.sensorId;
    document.getElementById("sensorInfoName").textContent = ds.sensorName;
    document.getElementById("sensorInfoValue").textContent = "Đang tải...";
    document.getElementById("sensorInfoTime").textContent = "";

    const editName = document.getElementById("sensorEditName");
    if (editName) {
      editName.value = ds.sensorName || "";
      document.getElementById("sensorEditWarehouse").value = warehouseId;
      document.getElementById("sensorEditZone").value = ds.zoneId || "";
      document.getElementById("sensorEditWarning").value = ds.warningThreshold || "";
      document.getElementById("sensorEditCritical").value = ds.criticalThreshold || "";
    }

    sensorInfoModal.show();

    const res = await fetch(`/api/sensors/${activeSensorId}/reading`);
    const data = await res.json();
    document.getElementById("sensorInfoValue").textContent =
      data.value !== null ? `${data.value.toFixed(1)} °C` : "Không có dữ liệu";
    document.getElementById("sensorInfoTime").textContent = data.time || "";
  }

  document.querySelectorAll(".sensor-edit-btn").forEach((btn) => {
    btn.addEventListener("click", () => showSensorModal(btn.dataset));
  });

  const sensorInfoSaveBtn = document.getElementById("sensorInfoSaveBtn");
  if (sensorInfoSaveBtn) {
    sensorInfoSaveBtn.addEventListener("click", async () => {
      if (!activeSensorId) return;
      const name = document.getElementById("sensorEditName").value.trim();
      if (!name) {
        alert("Vui lòng nhập tên cảm biến.");
        return;
      }
      const payload = {
        name,
        warehouse_id: document.getElementById("sensorEditWarehouse").value,
        zone_id: document.getElementById("sensorEditZone").value || null,
        warning_threshold: document.getElementById("sensorEditWarning").value || null,
        critical_threshold: document.getElementById("sensorEditCritical").value || null,
      };
      const res = await fetch(`/api/sensors/${activeSensorId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        location.reload();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.error || "Không thể lưu thay đổi.");
      }
    });
  }

  const sensorInfoDeleteBtn = document.getElementById("sensorInfoDeleteBtn");
  if (sensorInfoDeleteBtn) {
    sensorInfoDeleteBtn.addEventListener("click", async () => {
      if (!activeSensorId || !confirm("Xóa cảm biến này?")) return;
      const res = await fetch(`/api/sensors/${activeSensorId}`, { method: "DELETE" });
      if (res.ok) {
        document.querySelector(`.map-marker[data-sensor-id="${activeSensorId}"]`)?.remove();
        sensorInfoModal.hide();
      }
    });
  }
})();
