import os
from flask import Flask, session, render_template, send_from_directory
from config import Config
from utils import db as db_utils
from utils.auth_utils import gen_csrf_token


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(os.path.dirname(app.config["DATABASE"]), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db_utils.init_app(app)

    from blueprints.auth import bp as auth_bp
    from blueprints.student import bp as student_bp
    from blueprints.faculty import bp as faculty_bp
    from blueprints.admin import bp as admin_bp
    from blueprints.warden import bp as warden_bp
    from blueprints.mess import bp as mess_bp
    from blueprints.frontdesk import bp as frontdesk_bp
    from blueprints.api import bp as api_bp
    from blueprints.common import bp as common_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(faculty_bp, url_prefix="/faculty")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(warden_bp, url_prefix="/warden")
    app.register_blueprint(mess_bp, url_prefix="/mess")
    app.register_blueprint(frontdesk_bp, url_prefix="/frontdesk")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(common_bp)

    @app.context_processor
    def inject_globals():
        photo = None
        if session.get("user_id"):
            from utils.db import query_db
            row = query_db("SELECT photo FROM users WHERE id = ?", (session["user_id"],), one=True)
            photo = row["photo"] if row else None
        return {
            "csrf_token": gen_csrf_token,
            "session": session,
            "lite_mode": session.get("lite_mode", False),
            "app_name": "CampusOne",
            "tagline": "Campus Life, Debugged.",
            "current_user_photo": photo,
        }

    @app.after_request
    def prevent_authenticated_page_caching(response):
        if session.get("user_id"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, message="You don't have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("error.html", code=500, message="Something went wrong on our end."), 500

    return app


app = create_app()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
