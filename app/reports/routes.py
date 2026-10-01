import io
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, send_file
from flask_login import login_required
from openpyxl import Workbook

from app.models import Warehouse, Sensor
from app import influx_client

reports_bp = Blueprint("reports", __name__)


def _parse_filters():
    warehouse_id = request.args.get("warehouse_id", type=int)
    sensor_id = request.args.get("sensor_id", type=int)
    start_date = request.args.get("start_date") or (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = request.args.get("end_date") or datetime.utcnow().strftime("%Y-%m-%d")
    return warehouse_id, sensor_id, start_date, end_date


def _query_readings(sensor, start_date, end_date):
    start_iso = f"{start_date}T00:00:00Z"
    stop_iso = f"{end_date}T23:59:59Z"
    return influx_client.get_readings_range(sensor.sensor_code, start_iso, stop_iso)


@reports_bp.route("/")
@login_required
def index():
    warehouses = Warehouse.query.order_by(Warehouse.name).all()
    warehouse_id, sensor_id, start_date, end_date = _parse_filters()

    sensors = []
    if warehouse_id:
        sensors = Sensor.query.filter_by(warehouse_id=warehouse_id).order_by(Sensor.name).all()

    readings = []
    selected_sensor = None
    if sensor_id:
        selected_sensor = Sensor.query.get(sensor_id)
        if selected_sensor:
            readings = _query_readings(selected_sensor, start_date, end_date)

    chart_data = [
        {"t": r["time"].isoformat(), "v": r["value"]}
        for r in readings
        if r["time"] is not None
    ]

    return render_template(
        "reports/index.html",
        warehouses=warehouses,
        sensors=sensors,
        readings=readings,
        chart_data=chart_data,
        selected_sensor=selected_sensor,
        warehouse_id=warehouse_id,
        sensor_id=sensor_id,
        start_date=start_date,
        end_date=end_date,
        influx_configured=influx_client.is_configured(),
    )


@reports_bp.route("/export")
@login_required
def export():
    warehouse_id, sensor_id, start_date, end_date = _parse_filters()
    sensor = Sensor.query.get(sensor_id) if sensor_id else None

    wb = Workbook()
    ws = wb.active
    ws.title = "Lịch sử nhiệt độ"
    ws.append(["Cảm biến", "Mã cảm biến", "Thời gian", "Nhiệt độ (°C)"])

    if sensor:
        readings = _query_readings(sensor, start_date, end_date)
        for r in readings:
            time_str = r["time"].strftime("%Y-%m-%d %H:%M:%S") if r["time"] else ""
            ws.append([sensor.name, sensor.sensor_code, time_str, r["value"]])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"lich_su_nhiet_do_{start_date}_{end_date}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
