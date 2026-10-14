# Application factory and project-level Flask configuration.
from pathlib import Path

from flask import Flask

from .database import initialize_database
from .routes import api


BASE_DIR = Path(__file__).resolve().parent.parent


def create_app():
    # Serve the frontend directly from the repository while rendering templates
    # from the dedicated templates directory.
    app = Flask(
        __name__,
        static_folder=str(BASE_DIR),
        static_url_path="",
        template_folder=str(BASE_DIR / "templates"),
    )
    app.register_blueprint(api)
    initialize_database()
    return app
