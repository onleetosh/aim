# Application factory and project-level Flask configuration.
import os
import secrets
from pathlib import Path

from flask import Flask

from .auth import auth
from .database import initialize_database, initialize_tracking_tables
from .analytics import analytics_api
from .insights import insights_api
from .dashboard import dashboard_api
from .downtime import downtime_api
from .focus import focus_api
from .routes import api


BASE_DIR = Path(__file__).resolve().parent.parent


def create_app():
    # Only the frontend directory is public; the database and source stay private.
    app = Flask(
        __name__,
        static_folder=str(BASE_DIR / "frontend"),
        static_url_path="/frontend",
        template_folder=str(BASE_DIR / "templates"),
    )
    # Set SECRET_KEY in production so sessions survive restarts; a random key
    # is fine locally but logs everyone out whenever the server restarts.
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Render sets RENDER=true and serves the app over HTTPS.
        SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),
    )
    app.register_blueprint(auth)
    app.register_blueprint(api)
    app.register_blueprint(downtime_api)
    app.register_blueprint(focus_api)
    app.register_blueprint(dashboard_api)
    app.register_blueprint(analytics_api)
    app.register_blueprint(insights_api)
    initialize_database()
    initialize_tracking_tables()
    return app
