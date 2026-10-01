import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename


def sensor_status(sensor, reading):
    if reading is None:
        return "unknown"
    value = reading["value"]
    if sensor.critical_threshold is not None and value >= sensor.critical_threshold:
        return "critical"
    if sensor.warning_threshold is not None and value >= sensor.warning_threshold:
        return "warning"
    return "ok"


def allowed_image(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def save_uploaded_image(file_storage):
    """Lưu ảnh upload vào UPLOAD_FOLDER, trả về tên file đã lưu (hoặc None)."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_image(file_storage.filename):
        raise ValueError("Định dạng ảnh không hợp lệ. Chỉ chấp nhận: png, jpg, jpeg, gif.")

    ext = secure_filename(file_storage.filename).rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file_storage.save(path)
    return filename
