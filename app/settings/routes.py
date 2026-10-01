from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from app.extensions import db
from app.decorators import roles_required
from app.models import get_setting, set_setting, DEFAULT_SETTINGS, Warehouse, Zone, Sensor, Device
from app import influx_client

settings_bp = Blueprint("settings", __name__)

EDITABLE_KEYS = ["site_name", "warning_threshold", "critical_threshold", "timezone"]


@settings_bp.route("/", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def index():
    if request.method == "POST":
        for key in EDITABLE_KEYS:
            set_setting(key, request.form.get(key, "").strip())
        db.session.commit()
        flash("Đã lưu cài đặt.", "success")
        return redirect(url_for("settings.index"))

    values = {key: get_setting(key, DEFAULT_SETTINGS.get(key, "")) for key in EDITABLE_KEYS}
    return render_template(
        "settings/index.html",
        values=values,
        defaults=DEFAULT_SETTINGS,
        influx_configured=influx_client.is_configured(),
    )


@settings_bp.route("/reset", methods=["POST"])
@login_required
@roles_required("admin")
def reset():
    for key in EDITABLE_KEYS:
        set_setting(key, DEFAULT_SETTINGS.get(key, ""))
    db.session.commit()
    flash("Đã khôi phục cài đặt về mặc định.", "info")
    return redirect(url_for("settings.index"))


@settings_bp.route("/factory-reset", methods=["POST"])
@login_required
@roles_required("admin")
def factory_reset():
    """Xóa toàn bộ dữ liệu vận hành (kho, vùng, cảm biến, thiết bị) trong SQLite.

    Không đụng đến User/Role, cài đặt website, hay dữ liệu trong InfluxDB.
    """
    Sensor.query.delete()
    Zone.query.delete()
    Device.query.delete()
    Warehouse.query.delete()
    db.session.commit()
    flash("Đã xóa toàn bộ kho, vùng, cảm biến và thiết bị. Dữ liệu trong InfluxDB không bị ảnh hưởng.", "info")
    return redirect(url_for("settings.index"))
