import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from mongoengine import connect
from pymongo.errors import PyMongoError
from werkzeug.exceptions import HTTPException

from config import Config

log = logging.getLogger(__name__)

_MESSAGES = {
    400: "The request could not be understood.",
    401: "Please sign in to continue.",
    403: "You do not have permission to do that.",
    404: "That page or item does not exist.",
    405: "That action is not allowed here.",
    413: "That file is too large. The limit is 16 MB.",
    415: "That type of content is not supported.",
}


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    if not app.config.get("SECRETS_FROM_ENV"):
        log.warning("SECRET_KEY / JWT_SECRET_KEY are not set in the environment: using random per-process "
                    "secrets (sign-in tokens stop working when the server restarts). Set them in backend/.env.")

    JWTManager(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    # Ensure upload and output directories exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

    # Connect MongoEngine to MongoDB (connection is lazy; failures are reported per request)
    connect(host=app.config["MONGO_URI"], serverSelectionTimeoutMS=app.config["MONGO_TIMEOUT_MS"])

    # Register Route Blueprints
    from app.routes.auth import auth_bp
    from app.routes.images import images_bp
    from app.routes.measurements import measurements_bp
    from app.routes.patterns import patterns_bp
    from app.routes.export import export_bp
    from app.routes.research import research_bp
    from app.routes.fabric import fabric_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(images_bp, url_prefix="/api/images")
    app.register_blueprint(measurements_bp, url_prefix="/api/measurements")
    app.register_blueprint(patterns_bp, url_prefix="/api/patterns")
    app.register_blueprint(export_bp, url_prefix="/api/export")
    app.register_blueprint(research_bp, url_prefix="/api/research")
    app.register_blueprint(fabric_bp, url_prefix="/api/fabric")

    @app.route("/")
    def index():
        return {"status": "online", "message": "AI-Assisted Digital Tailor System API"}

    # ── consistent JSON errors: never HTML pages, never stack traces ───────────
    @app.errorhandler(HTTPException)
    def http_error(err):
        code = err.code or 500
        return jsonify({"error": _MESSAGES.get(code, err.name), "error_code": err.name.upper().replace(" ", "_")}), code

    @app.errorhandler(PyMongoError)
    def database_error(err):
        log.error("database error: %s", err)
        return jsonify({"error": "The database is not available right now. Please try again in a moment.",
                        "error_code": "DATABASE_UNAVAILABLE"}), 503

    @app.errorhandler(Exception)
    def unexpected_error(err):
        log.exception("unhandled error")
        return jsonify({"error": "Something went wrong on the server. Please try again.",
                        "error_code": "INTERNAL_ERROR"}), 500

    return app
