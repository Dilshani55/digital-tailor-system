import os
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from mongoengine import connect
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # JWT Configuration
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-digital-tailor-secret-key-2026')
    JWTManager(app)

    CORS(app)

    # Ensure upload and output directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

    # Connect MongoEngine to MongoDB
    connect(host=app.config['MONGO_URI'])

    # Register Route Blueprints
    from app.routes.auth import auth_bp
    from app.routes.images import images_bp
    from app.routes.measurements import measurements_bp
    from app.routes.patterns import patterns_bp
    from app.routes.export import export_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(images_bp, url_prefix='/api/images')
    app.register_blueprint(measurements_bp, url_prefix='/api/measurements')
    app.register_blueprint(patterns_bp, url_prefix='/api/patterns')
    app.register_blueprint(export_bp, url_prefix='/api/export')

    @app.route('/')
    def index():
        return {"status": "online", "message": "AI-Assisted Digital Tailor System API"}

    return app
