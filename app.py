# app.py - application factory
# Used Copilot to help me get the factory pattern right (the blueprint
# registration part kept breaking until I restructured it)

import os
from flask import Flask
from flask_login import LoginManager
from flask_socketio import SocketIO

socketio = SocketIO()  # created here so chat.py can import it
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "gigcampus-dev-secret-key-change-in-prod")
    app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

    basedir = os.path.abspath(os.path.dirname(__file__))

    # Check for Render persistent disk
    data_dir = "/var/data"
    if os.path.exists(data_dir):
        app.config["DATABASE"] = os.path.join(data_dir, "gigcampus.db")
    else:
        app.config["DATABASE"] = os.path.join(basedir, "gigcampus.db")

    # make sure upload dirs exist
    for sub in ["ids", "gigs", "deliverables", "avatars"]:
        os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], sub), exist_ok=True)

    login_manager.init_app(app)
    # gevent on Render for WebSocket support, threading locally
    mode = "gevent" if os.environ.get("RENDER") else "threading"
    socketio.init_app(app, async_mode=mode)

    from models import init_db, get_db
    with app.app_context():
        init_db(app)

    @login_manager.user_loader
    def load_user(user_id):
        db = get_db()
        rows = db.execute("SELECT * FROM users WHERE id = ?", user_id)
        if rows:
            from helpers import make_user_obj
            return make_user_obj(rows[0])
        return None

    # blueprints
    from routes.auth import auth_bp
    from routes.gigs import gigs_bp
    from routes.orders import orders_bp
    from routes.chat import chat_bp
    from routes.reviews import reviews_bp
    from routes.dashboard import dashboard_bp
    from routes.admin import admin_bp
    from routes.profile import profile_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(gigs_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)

    from helpers import format_bdt
    app.template_filter("bdt")(format_bdt)

    # inject admin badge count + unread messages into every template
    @app.context_processor
    def inject_admin_counts():
        try:
            from flask_login import current_user
            result = {"admin_pending_count": 0, "unread_message_count": 0}
            if current_user.is_authenticated:
                _db = get_db()
                if current_user.is_admin:
                    rows = _db.execute("SELECT COUNT(*) AS cnt FROM users WHERE is_verified = 0")
                    result["admin_pending_count"] = rows[0]["cnt"] if rows else 0
                unread = _db.execute(
                    "SELECT COUNT(*) AS cnt FROM messages m "
                    "JOIN conversations c ON m.conversation_id = c.id "
                    "WHERE (c.buyer_id = ? OR c.seller_id = ?) "
                    "  AND m.sender_id != ? AND m.is_read = 0",
                    current_user.id, current_user.id, current_user.id
                )
                result["unread_message_count"] = unread[0]["cnt"] if unread else 0
            return result
        except Exception:
            pass
        return {"admin_pending_count": 0, "unread_message_count": 0}

    @app.route("/")
    def index():
        from flask import render_template
        db = get_db()
        # 6 most recent active gigs for the homepage
        featured = db.execute(
            "SELECT g.*, u.username AS seller_name, u.avatar AS seller_avatar, "
            "COALESCE((SELECT AVG(r.rating) FROM reviews r WHERE r.reviewee_id = g.seller_id), 0) AS avg_rating "
            "FROM gigs g JOIN users u ON g.seller_id = u.id "
            "WHERE g.status = 'active' ORDER BY g.created_at DESC LIMIT 6"
        )
        return render_template("index.html", featured=featured)

    # only start the ghost checker in the main process (werkzeug runs 2 in debug)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        from ghost_check import start_ghost_checker
        start_ghost_checker(app)

    return app
