from datetime import datetime

from flask_login import UserMixin

from app.extensions import db, login_manager


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)  # admin / manager / viewer

    users = db.relationship("User", back_populates="role")

    def __repr__(self):
        return f"<Role {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    is_active_flag = db.Column("is_active", db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    role = db.relationship("Role", back_populates="users")

    @property
    def is_active(self):
        return self.is_active_flag

    def has_role(self, *role_names):
        return self.role is not None and self.role.name in role_names

    def __repr__(self):
        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Warehouse(db.Model):
    __tablename__ = "warehouses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(40), unique=True, nullable=False)
    map_image_path = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    zones = db.relationship("Zone", back_populates="warehouse", cascade="all, delete-orphan")
    sensors = db.relationship("Sensor", back_populates="warehouse", cascade="all, delete-orphan")
    devices = db.relationship("Device", back_populates="warehouse", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Warehouse {self.code}>"


class Zone(db.Model):
    __tablename__ = "zones"

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    x = db.Column(db.Float, nullable=False)  # % from left
    y = db.Column(db.Float, nullable=False)  # % from top
    width = db.Column(db.Float, nullable=False)  # % of image width
    height = db.Column(db.Float, nullable=False)  # % of image height
    color = db.Column(db.String(20), default="#3b82f6")

    warehouse = db.relationship("Warehouse", back_populates="zones")
    sensors = db.relationship("Sensor", back_populates="zone")

    def __repr__(self):
        return f"<Zone {self.name}>"


class Sensor(db.Model):
    __tablename__ = "sensors"

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    zone_id = db.Column(db.Integer, db.ForeignKey("zones.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    sensor_code = db.Column(db.String(80), unique=True, nullable=False)  # matches InfluxDB tag
    x = db.Column(db.Float, nullable=True)  # % from left on warehouse map
    y = db.Column(db.Float, nullable=True)  # % from top on warehouse map
    warning_threshold = db.Column(db.Float, nullable=True)
    critical_threshold = db.Column(db.Float, nullable=True)

    warehouse = db.relationship("Warehouse", back_populates="sensors")
    zone = db.relationship("Zone", back_populates="sensors")

    def __repr__(self):
        return f"<Sensor {self.sensor_code}>"


class Device(db.Model):
    __tablename__ = "devices"

    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    device_code = db.Column(db.String(80), unique=True, nullable=False)
    type = db.Column(db.String(60), nullable=True)
    status = db.Column(db.String(20), default="active")  # active / inactive / maintenance
    config_json = db.Column(db.Text, nullable=True)
    last_seen = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    warehouse = db.relationship("Warehouse", back_populates="devices")

    def __repr__(self):
        return f"<Device {self.device_code}>"


class SiteSetting(db.Model):
    __tablename__ = "site_settings"

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<SiteSetting {self.key}={self.value}>"


DEFAULT_SETTINGS = {
    "site_name": "Env Monitor",
    "warning_threshold": "30",
    "critical_threshold": "35",
    "timezone": "Asia/Ho_Chi_Minh",
}


def get_setting(key, default=None):
    setting = SiteSetting.query.get(key)
    if setting is None:
        return DEFAULT_SETTINGS.get(key, default)
    return setting.value


def set_setting(key, value):
    setting = SiteSetting.query.get(key)
    if setting is None:
        setting = SiteSetting(key=key, value=value)
        db.session.add(setting)
    else:
        setting.value = value
