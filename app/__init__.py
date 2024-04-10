import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv

from app.routes import search_bp
from app.extensions import db

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URI")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate = Migrate(app, db)
    with app.app_context():
        db.create_all()

    # Health check hello route
    @app.route('/hello')
    def hello():
        return 'Дай Боже добрыден, сьвітку!'

    # Register the blueprint
    app.register_blueprint(search_bp, url_prefix='/search')

    return app


