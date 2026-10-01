import os

from flask import Flask

from config import Config
from app.extensions import db, migrate, login_manager, bcrypt


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "instance"), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.reports.routes import reports_bp
    from app.devices.routes import devices_bp
    from app.users.routes import users_bp
    from app.settings.routes import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(devices_bp, url_prefix="/devices")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(settings_bp, url_prefix="/settings")

    from app.errors import register_error_handlers

    register_error_handlers(app)

    from app.models import get_setting

    @app.context_processor
    def inject_site_settings():
        return {"site_name": get_setting("site_name", "Env Monitor")}

    return app
