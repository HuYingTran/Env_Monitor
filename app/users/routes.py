from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db, bcrypt
from app.decorators import roles_required
from app.models import User, Role

users_bp = Blueprint("users", __name__)


@users_bp.route("/")
@login_required
@roles_required("admin")
def index():
    users = User.query.order_by(User.username).all()
    return render_template("users/index.html", users=users)


@users_bp.route("/new", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def new():
    roles = Role.query.order_by(Role.name).all()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role_id = request.form.get("role_id")

        if not username or not password or not role_id:
            flash("Vui lòng nhập đầy đủ tên đăng nhập, mật khẩu và vai trò.", "danger")
            return render_template("users/form.html", user=None, roles=roles)
        if User.query.filter_by(username=username).first():
            flash("Tên đăng nhập đã tồn tại.", "danger")
            return render_template("users/form.html", user=None, roles=roles)

        user = User(
            username=username,
            email=email or None,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            role_id=role_id,
        )
        db.session.add(user)
        db.session.commit()
        flash("Đã tạo người dùng.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/form.html", user=None, roles=roles)


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit(user_id):
    user = User.query.get_or_404(user_id)
    roles = Role.query.order_by(Role.name).all()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role_id = request.form.get("role_id")
        is_active = request.form.get("is_active") == "on"

        if not username or not role_id:
            flash("Vui lòng nhập đầy đủ tên đăng nhập và vai trò.", "danger")
            return render_template("users/form.html", user=user, roles=roles)

        existing = User.query.filter(User.username == username, User.id != user.id).first()
        if existing:
            flash("Tên đăng nhập đã tồn tại.", "danger")
            return render_template("users/form.html", user=user, roles=roles)

        if user.id == current_user.id and not is_active:
            flash("Bạn không thể tự vô hiệu hóa tài khoản của mình.", "danger")
            return render_template("users/form.html", user=user, roles=roles)

        user.username = username
        user.email = email or None
        user.role_id = role_id
        user.is_active_flag = is_active
        if password:
            user.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        db.session.commit()
        flash("Đã cập nhật người dùng.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/form.html", user=user, roles=roles)


@users_bp.route("/<int:user_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Bạn không thể tự xóa tài khoản của mình.", "danger")
        return redirect(url_for("users.index"))
    db.session.delete(user)
    db.session.commit()
    flash("Đã xóa người dùng.", "info")
    return redirect(url_for("users.index"))
