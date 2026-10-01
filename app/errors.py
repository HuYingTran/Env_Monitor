from flask import render_template


def register_error_handlers(app):
    @app.errorhandler(401)
    def unauthorized(error):
        return render_template("errors/401.html"), 401

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404
