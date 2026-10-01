import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "env_monitor.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    INFLUX_URL = os.environ.get("INFLUX_URL", "http://localhost:8086")
    INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "")
    INFLUX_ORG = os.environ.get("INFLUX_ORG", "")
    INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "")

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads", "warehouse_maps")
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8MB upload limit
