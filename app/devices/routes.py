from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.decorators import roles_required
from app.models import Device, Warehouse, Sensor
from app.utils import sensor_status
from app import influx_client

devices_bp = Blueprint("devices", __name__)

STATUS_CHOICES = ["active", "inactive", "maintenance"]


def _available_device_codes(current_code=None):
    """Mã thiết bị được chọn từ các sensor_code đang gửi dữ liệu vào InfluxDB,
    trừ những mã đã gán cho thiết bị khác (giữ lại mã hiện tại khi đang sửa)."""
    known_codes = {d.device_code for d in Device.query.all()}
    recent_codes = influx_client.get_recent_sensor_codes()
    available = recent_codes - known_codes
    if current_code:
        available.add(current_code)
    return sorted(available)


DEVICE_STATUS_BADGE = {"active": "success", "inactive": "secondary", "maintenance": "warning"}
SENSOR_STATUS_BADGE = {"critical": "danger", "warning": "warning", "ok": "success", "unknown": "secondary"}


@devices_bp.route("/")
@login_required
def index():
    devices = Device.query.order_by(Device.name).all()
    sensors = Sensor.query.order_by(Sensor.name).all()
    can_edit = current_user.has_role("admin", "manager")

    new_sensor_codes = []
    if can_edit:
        known_codes = {s.sensor_code for s in sensors}
        recent_codes = influx_client.get_recent_sensor_codes()
        new_sensor_codes = sorted(recent_codes - known_codes)

    rows = []
    for d in devices:
        rows.append({
            "kind": "Thiết bị",
            "entity": "device",
            "id": d.id,
            "name": d.name,
            "code": d.device_code,
            "type": d.type or "",
            "warehouse": d.warehouse.name if d.warehouse else None,
            "warehouse_id": d.warehouse_id,
            "status": d.status,
            "status_color": DEVICE_STATUS_BADGE.get(d.status, "secondary"),
            "warning_threshold": None,
            "critical_threshold": None,
            "delete_url": url_for("devices.delete", device_id=d.id),
        })
    for s in sensors:
        reading = influx_client.get_latest_reading(s.sensor_code)
        status = sensor_status(s, reading)
        rows.append({
            "kind": "Cảm biến",
            "entity": "sensor",
            "id": s.id,
            "name": s.name,
            "code": s.sensor_code,
            "type": "",
            "warehouse": s.warehouse.name if s.warehouse else None,
            "warehouse_id": s.warehouse_id,
            "warning_threshold": s.warning_threshold,
            "critical_threshold": s.critical_threshold,
            "status": status,
            "status_color": SENSOR_STATUS_BADGE.get(status, "secondary"),
            "delete_url": None,
        })
    # sắp theo kho (chưa gán kho thì xếp cuối), trong cùng kho sắp theo tên
    rows.sort(key=lambda r: (r["warehouse"] is None, (r["warehouse"] or "").lower(), r["name"].lower()))
    warehouses = Warehouse.query.order_by(Warehouse.name).all()

    return render_template(
        "devices/index.html",
        rows=rows,
        warehouses=warehouses,
        statuses=STATUS_CHOICES,
        can_edit=can_edit,
        new_sensor_codes=new_sensor_codes,
        influx_configured=influx_client.is_configured(),
    )


@devices_bp.route("/api/<int:device_id>", methods=["PATCH"])
@login_required
@roles_required("admin", "manager")
def api_update_device(device_id):
    device = Device.query.get_or_404(device_id)
    data = request.get_json(force=True)

    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(error="Vui lòng nhập tên thiết bị."), 400

    device.name = name
    device.type = (data.get("type") or "").strip() or None
    device.status = data.get("status") or device.status
    device.warehouse_id = data.get("warehouse_id") or None
    db.session.commit()
    return jsonify(success=True)


@devices_bp.route("/register-sensor", methods=["GET", "POST"])
@login_required
@roles_required("admin", "manager")
def register_sensor():
    warehouses = Warehouse.query.order_by(Warehouse.name).all()
    sensor_code = request.values.get("sensor_code", "").strip()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        warehouse_id = request.form.get("warehouse_id") or None
        if not sensor_code or not name or not warehouse_id:
            flash("Vui lòng nhập đầy đủ mã cảm biến, tên và chọn kho.", "danger")
            return render_template("devices/register_sensor.html", sensor_code=sensor_code, warehouses=warehouses)
        if Sensor.query.filter_by(sensor_code=sensor_code).first():
            flash("Mã cảm biến này đã được đăng ký.", "danger")
            return redirect(url_for("devices.index"))

        sensor = Sensor(
            name=name,
            sensor_code=sensor_code,
            warehouse_id=warehouse_id,
            warning_threshold=request.form.get("warning_threshold") or None,
            critical_threshold=request.form.get("critical_threshold") or None,
        )
        db.session.add(sensor)
        db.session.commit()
        flash("Đã đăng ký cảm biến. Click vào bản đồ để đặt vị trí.", "success")
        return redirect(url_for("main.warehouse_detail", warehouse_id=warehouse_id, place_sensor=sensor.id))

    return render_template("devices/register_sensor.html", sensor_code=sensor_code, warehouses=warehouses)


@devices_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin", "manager")
def new():
    warehouses = Warehouse.query.order_by(Warehouse.name).all()
    available_codes = _available_device_codes()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        device_code = request.form.get("device_code", "").strip()
        if not name or not device_code or device_code not in available_codes:
            flash("Vui lòng nhập tên và chọn một mã thiết bị hợp lệ từ danh sách.", "danger")
            return render_template("devices/form.html", device=None, warehouses=warehouses, statuses=STATUS_CHOICES, available_codes=available_codes)
        if Device.query.filter_by(device_code=device_code).first():
            flash("Mã thiết bị đã tồn tại.", "danger")
            return render_template("devices/form.html", device=None, warehouses=warehouses, statuses=STATUS_CHOICES, available_codes=available_codes)

        warehouse_id = request.form.get("warehouse_id") or None
        device = Device(
            name=name,
            device_code=device_code,
            type=request.form.get("type", "").strip() or None,
            status=request.form.get("status", "active"),
            warehouse_id=warehouse_id,
        )
        db.session.add(device)
        db.session.commit()
        flash("Đã thêm thiết bị.", "success")
        return redirect(url_for("devices.index"))

    return render_template("devices/form.html", device=None, warehouses=warehouses, statuses=STATUS_CHOICES, available_codes=available_codes)


@devices_bp.route("/<int:device_id>", methods=["GET", "POST"])
@login_required
def detail(device_id):
    device = Device.query.get_or_404(device_id)
    can_edit = current_user.has_role("admin", "manager")
    warehouses = Warehouse.query.order_by(Warehouse.name).all()
    available_codes = _available_device_codes(current_code=device.device_code)

    if request.method == "POST":
        if not can_edit:
            flash("Bạn không có quyền chỉnh sửa thiết bị.", "danger")
            return redirect(url_for("devices.detail", device_id=device.id))

        name = request.form.get("name", "").strip()
        device_code = request.form.get("device_code", "").strip()
        if not name or not device_code or device_code not in available_codes:
            flash("Vui lòng nhập tên và chọn một mã thiết bị hợp lệ từ danh sách.", "danger")
            return render_template("devices/form.html", device=device, warehouses=warehouses, statuses=STATUS_CHOICES, available_codes=available_codes, can_edit=can_edit)

        existing = Device.query.filter(Device.device_code == device_code, Device.id != device.id).first()
        if existing:
            flash("Mã thiết bị đã tồn tại.", "danger")
            return render_template("devices/form.html", device=device, warehouses=warehouses, statuses=STATUS_CHOICES, available_codes=available_codes, can_edit=can_edit)

        device.name = name
        device.device_code = device_code
        device.type = request.form.get("type", "").strip() or None
        device.status = request.form.get("status", "active")
        device.warehouse_id = request.form.get("warehouse_id") or None
        db.session.commit()
        flash("Đã cập nhật thiết bị.", "success")
        return redirect(url_for("devices.detail", device_id=device.id))

    return render_template("devices/form.html", device=device, warehouses=warehouses, statuses=STATUS_CHOICES, can_edit=can_edit, available_codes=available_codes)


@devices_bp.route("/<int:device_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete(device_id):
    device = Device.query.get_or_404(device_id)
    db.session.delete(device)
    db.session.commit()
    flash("Đã xóa thiết bị.", "info")
    return redirect(url_for("devices.index"))
