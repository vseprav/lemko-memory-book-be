import os

from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv

from app.routes import search_bp, family_bp
from app.extensions import db
from app.seeds.first_tom import seed_evicted_persons


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    CORS(app)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URI")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Keep a small warm pool: opening Postgres connections is CPU-expensive,
    # and Azure drops idle connections, so recycle and ping before use.
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 5,
        'max_overflow': 5,
        'pool_pre_ping': True,
        'pool_recycle': 1800,
    }

    db.init_app(app)
    migrate = Migrate(app, db)

    # Add the seed_db command to the app
    app.cli.add_command(seed_evicted_persons)

    # Health check hello route
    @app.route('/hello')
    def hello():
        return 'Дай Боже добрыден, сьвітку!'

    # Register the blueprint
    app.register_blueprint(search_bp, url_prefix='/search')
    app.register_blueprint(family_bp, url_prefix='/family')

    return app
