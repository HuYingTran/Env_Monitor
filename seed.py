"""Tạo dữ liệu khởi tạo: roles + tài khoản admin mặc định.

Chạy: python seed.py
"""

from app import create_app
from app.extensions import db, bcrypt
from app.models import Role, User

DEFAULT_ROLES = ["admin", "manager", "viewer"]
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def seed():
    app = create_app()
    with app.app_context():
        db.create_all()

        roles = {}
        for name in DEFAULT_ROLES:
            role = Role.query.filter_by(name=name).first()
            if role is None:
                role = Role(name=name)
                db.session.add(role)
            roles[name] = role
        db.session.flush()

        admin = User.query.filter_by(username=DEFAULT_ADMIN_USERNAME).first()
        if admin is None:
            admin = User(
                username=DEFAULT_ADMIN_USERNAME,
                email="admin@example.com",
                password_hash=bcrypt.generate_password_hash(DEFAULT_ADMIN_PASSWORD).decode("utf-8"),
                role=roles["admin"],
            )
            db.session.add(admin)
            print(f"Đã tạo tài khoản admin: {DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}")
        else:
            print("Tài khoản admin đã tồn tại, bỏ qua.")

        db.session.commit()
        print("Seed hoàn tất.")


if __name__ == "__main__":
    seed()
