from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.decorators import roles_required
from app.models import Warehouse, Zone, Sensor
from app.utils import save_uploaded_image, sensor_status as _sensor_status
from app import influx_client

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
@login_required
def home():
    warehouses = Warehouse.query.order_by(Warehouse.display_order, Warehouse.name).all()
    summary = {}
    status_totals = {"ok": 0, "warning": 0, "critical": 0, "unknown": 0}
    total_sensors = 0
    for wh in warehouses:
        wh_readings = {}
        for sensor in wh.sensors:
            reading = influx_client.get_latest_reading(sensor.sensor_code)
            status = _sensor_status(sensor, reading)
            wh_readings[sensor.id] = {"reading": reading, "status": status}
            status_totals[status] += 1
            total_sensors += 1
        summary[wh.id] = wh_readings

    return render_template(
        "main/home.html",
        warehouses=warehouses,
        summary=summary,
        total_warehouses=len(warehouses),
        total_sensors=total_sensors,
        status_totals=status_totals,
        influx_configured=influx_client.is_configured(),
    )


@main_bp.route("/api/sensors/realtime")
@login_required
def api_realtime_readings():
    minutes = request.args.get("minutes", default=15, type=int)
    sensors = Sensor.query.order_by(Sensor.name).limit(8).all()
    sensor_by_code = {s.sensor_code: s for s in sensors}
    codes = list(sensor_by_code.keys())

    # giới hạn ~150 điểm/cảm biến bất kể xem khoảng thời gian dài hay ngắn
    every_seconds = max(5, (minutes * 60) // 150)
    every = f"{every_seconds}s"

    result = {"temperature": [], "humidity": [], "pressure": []}
    for measurement in result:
        by_code = influx_client.get_readings_range_multi(codes, f"-{minutes}m", "now()", measurement=measurement, every=every)
        for code, readings in by_code.items():
            if not readings:
                continue
            s = sensor_by_code[code]
            result[measurement].append({
                "id": s.id,
                "name": s.name,
                "warehouse": s.warehouse.name if s.warehouse else None,
                "data": [
                    {"t": r["time"].isoformat() if r["time"] else None, "v": r["value"]}
                    for r in readings
                    if r["time"] is not None
                ],
            })
        result[measurement].sort(key=lambda x: x["name"])
    return jsonify(result)


@main_bp.route("/api/sensors/<int:sensor_id>/history")
@login_required
def api_sensor_history(sensor_id):
    sensor = Sensor.query.get_or_404(sensor_id)
    hours = request.args.get("hours", default=24, type=int)
    every_seconds = max(5, (hours * 3600) // 150)
    by_code = influx_client.get_readings_range_multi(
        [sensor.sensor_code], f"-{hours}h", "now()", measurement="temperature", every=f"{every_seconds}s"
    )
    readings = by_code.get(sensor.sensor_code, [])
    data = [
        {"t": r["time"].isoformat(), "v": r["value"]}
        for r in readings
        if r["time"] is not None
    ]
    return jsonify(data=data)


@main_bp.route("/warehouse/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "manager")
def warehouse_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        description = request.form.get("description", "").strip()
        if not name or not code:
            flash("Vui lòng nhập đầy đủ tên và mã kho.", "danger")
            return render_template("main/warehouse_form.html", warehouse=None)

        if Warehouse.query.filter_by(code=code).first():
            flash("Mã kho đã tồn tại.", "danger")
            return render_template("main/warehouse_form.html", warehouse=None)

        image_filename = None
        try:
            image_filename = save_uploaded_image(request.files.get("map_image"))
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("main/warehouse_form.html", warehouse=None)

        max_order = db.session.query(db.func.max(Warehouse.display_order)).scalar() or 0
        wh = Warehouse(name=name, code=code, description=description, map_image_path=image_filename, display_order=max_order + 1)
        db.session.add(wh)
        db.session.commit()
        flash("Đã tạo kho mới.", "success")
        return redirect(url_for("main.warehouse_detail", warehouse_id=wh.id))

    return render_template("main/warehouse_form.html", warehouse=None)


@main_bp.route("/warehouse/<int:warehouse_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin", "manager")
def warehouse_edit(warehouse_id):
    wh = Warehouse.query.get_or_404(warehouse_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        description = request.form.get("description", "").strip()
        if not name or not code:
            flash("Vui lòng nhập đầy đủ tên và mã kho.", "danger")
            return render_template("main/warehouse_form.html", warehouse=wh)

        existing = Warehouse.query.filter(Warehouse.code == code, Warehouse.id != wh.id).first()
        if existing:
            flash("Mã kho đã tồn tại.", "danger")
            return render_template("main/warehouse_form.html", warehouse=wh)

        if request.files.get("map_image") and request.files["map_image"].filename:
            try:
                wh.map_image_path = save_uploaded_image(request.files.get("map_image"))
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("main/warehouse_form.html", warehouse=wh)

        wh.name = name
        wh.code = code
        wh.description = description
        db.session.commit()
        flash("Đã cập nhật thông tin kho.", "success")
        return redirect(url_for("main.warehouse_detail", warehouse_id=wh.id))

    return render_template("main/warehouse_form.html", warehouse=wh)


@main_bp.route("/warehouse/<int:warehouse_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def warehouse_delete(warehouse_id):
    wh = Warehouse.query.get_or_404(warehouse_id)
    db.session.delete(wh)
    db.session.commit()
    flash("Đã xóa kho.", "info")
    return redirect(url_for("main.home"))


@main_bp.route("/warehouse/<int:warehouse_id>")
@login_required
def warehouse_detail(warehouse_id):
    wh = Warehouse.query.get_or_404(warehouse_id)
    readings = {}
    for sensor in wh.sensors:
        reading = influx_client.get_latest_reading(sensor.sensor_code)
        readings[sensor.id] = {"reading": reading, "status": _sensor_status(sensor, reading)}
    unplaced_sensors = [s for s in wh.sensors if s.x is None or s.y is None]
    warehouses = Warehouse.query.order_by(Warehouse.name).all()
    can_edit = current_user.has_role("admin", "manager")
    auto_place_sensor_id = request.args.get("place_sensor", type=int)
    return render_template(
        "main/warehouse_detail.html",
        warehouse=wh,
        readings=readings,
        warehouses=warehouses,
        unplaced_sensors=unplaced_sensors,
        can_edit=can_edit,
        auto_place_sensor_id=auto_place_sensor_id,
        influx_configured=influx_client.is_configured(),
    )


@main_bp.route("/api/warehouses/reorder", methods=["POST"])
@login_required
@roles_required("admin", "manager")
def api_reorder_warehouses():
    data = request.get_json(force=True)
    ordered_ids = data.get("order") or []
    warehouses = {wh.id: wh for wh in Warehouse.query.filter(Warehouse.id.in_(ordered_ids)).all()}
    for index, wh_id in enumerate(ordered_ids):
        wh = warehouses.get(int(wh_id))
        if wh:
            wh.display_order = index
    db.session.commit()
    return jsonify(success=True)


# ---------- JSON API cho bản đồ kho (zone / sensor marker) ----------

def _require_edit():
    if not current_user.has_role("admin", "manager"):
        return jsonify(error="Bạn không có quyền thực hiện thao tác này."), 403
    return None


@main_bp.route("/api/warehouse/<int:warehouse_id>/zones", methods=["POST"])
@login_required
def api_create_zone(warehouse_id):
    denied = _require_edit()
    if denied:
        return denied
    wh = Warehouse.query.get_or_404(warehouse_id)
    data = request.get_json(force=True)
    try:
        zone = Zone(
            warehouse_id=wh.id,
            name=data["name"],
            x=float(data["x"]),
            y=float(data["y"]),
            width=float(data["width"]),
            height=float(data["height"]),
            color=data.get("color", "#3b82f6"),
        )
    except (KeyError, ValueError, TypeError):
        return jsonify(error="Dữ liệu vùng không hợp lệ."), 400
    db.session.add(zone)
    db.session.commit()
    return jsonify(id=zone.id, name=zone.name, x=zone.x, y=zone.y, width=zone.width, height=zone.height, color=zone.color), 201


@main_bp.route("/api/zones/<int:zone_id>", methods=["PATCH", "DELETE"])
@login_required
def api_zone_detail(zone_id):
    denied = _require_edit()
    if denied:
        return denied
    zone = Zone.query.get_or_404(zone_id)
    if request.method == "DELETE":
        db.session.delete(zone)
        db.session.commit()
        return jsonify(success=True)

    data = request.get_json(force=True)
    for field in ("name", "x", "y", "width", "height", "color"):
        if field in data:
            setattr(zone, field, data[field])
    db.session.commit()
    return jsonify(success=True)


@main_bp.route("/api/warehouse/<int:warehouse_id>/sensors", methods=["POST"])
@login_required
def api_create_sensor(warehouse_id):
    denied = _require_edit()
    if denied:
        return denied
    wh = Warehouse.query.get_or_404(warehouse_id)
    data = request.get_json(force=True)
    sensor_code = (data.get("sensor_code") or "").strip()
    name = (data.get("name") or "").strip()
    if not sensor_code or not name:
        return jsonify(error="Vui lòng nhập tên và mã cảm biến."), 400
    if Sensor.query.filter_by(sensor_code=sensor_code).first():
        return jsonify(error="Mã cảm biến đã tồn tại."), 400

    try:
        sensor = Sensor(
            warehouse_id=wh.id,
            name=name,
            sensor_code=sensor_code,
            x=float(data["x"]),
            y=float(data["y"]),
            zone_id=data.get("zone_id") or None,
            warning_threshold=data.get("warning_threshold") or None,
            critical_threshold=data.get("critical_threshold") or None,
        )
    except (KeyError, ValueError, TypeError):
        return jsonify(error="Dữ liệu cảm biến không hợp lệ."), 400
    db.session.add(sensor)
    db.session.commit()
    return jsonify(id=sensor.id, name=sensor.name, sensor_code=sensor.sensor_code, x=sensor.x, y=sensor.y), 201


@main_bp.route("/api/sensors/<int:sensor_id>/position", methods=["PATCH"])
@login_required
def api_sensor_position(sensor_id):
    denied = _require_edit()
    if denied:
        return denied
    sensor = Sensor.query.get_or_404(sensor_id)
    data = request.get_json(force=True)
    try:
        sensor.x = float(data["x"])
        sensor.y = float(data["y"])
    except (KeyError, ValueError, TypeError):
        return jsonify(error="Tọa độ không hợp lệ."), 400
    db.session.commit()
    return jsonify(success=True)


@main_bp.route("/api/sensors/<int:sensor_id>", methods=["PATCH", "DELETE"])
@login_required
def api_sensor_detail(sensor_id):
    denied = _require_edit()
    if denied:
        return denied
    sensor = Sensor.query.get_or_404(sensor_id)
    if request.method == "DELETE":
        db.session.delete(sensor)
        db.session.commit()
        return jsonify(success=True)

    data = request.get_json(force=True)
    new_warehouse_id = data.get("warehouse_id")
    warehouse_changed = new_warehouse_id and int(new_warehouse_id) != sensor.warehouse_id

    for field in ("name", "zone_id", "warning_threshold", "critical_threshold"):
        if field in data:
            setattr(sensor, field, data[field])

    if warehouse_changed:
        if not Warehouse.query.get(int(new_warehouse_id)):
            return jsonify(error="Kho không hợp lệ."), 400
        sensor.warehouse_id = int(new_warehouse_id)
        sensor.zone_id = None
        sensor.x = None
        sensor.y = None

    db.session.commit()
    return jsonify(success=True)


@main_bp.route("/api/sensors/<int:sensor_id>/reading")
@login_required
def api_sensor_reading(sensor_id):
    sensor = Sensor.query.get_or_404(sensor_id)
    reading = influx_client.get_latest_reading(sensor.sensor_code)
    if reading is None:
        return jsonify(value=None, time=None, status="unknown")
    return jsonify(
        value=reading["value"],
        time=reading["time"].isoformat() if reading["time"] else None,
        status=_sensor_status(sensor, reading),
    )
