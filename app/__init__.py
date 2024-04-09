import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

from app.routes import search_bp
from app.extensions import db

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URI")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    with app.app_context():
            from app import models  # Import models after db initialization

    # Health check hello route
    @app.route('/hello')
    def hello():
        return 'Hello, World!'

    # Register the blueprint
    app.register_blueprint(search_bp, url_prefix='/search')

    return app


