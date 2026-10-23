import os

from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

from app.routes import search_bp, family_bp, settlements_bp, oblasts_bp
from app.extensions import db, limiter
from app.seeds.first_tom import seed_evicted_persons
from app.commands.repair_book_data import repair_book_data


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    # Azure App Service sits behind a reverse proxy; trust one hop of
    # X-Forwarded-For so rate limiting sees the real client IP.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
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
    limiter.init_app(app)
    migrate = Migrate(app, db)

    # Add the seed_db command to the app
    app.cli.add_command(seed_evicted_persons)
    # One-off data repair from the book (lemko/spec/data-audit); run deliberately, never at startup
    app.cli.add_command(repair_book_data)

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return {'error': 'Too many requests', 'detail': str(e.description)}, 429

    # Health check hello route
    @app.route('/hello')
    @limiter.exempt
    def hello():
        return 'Дай Боже добрыден, сьвітку!'

    # Register the blueprint
    app.register_blueprint(search_bp, url_prefix='/search')
    app.register_blueprint(family_bp, url_prefix='/family')
    app.register_blueprint(settlements_bp, url_prefix='/settlements')
    app.register_blueprint(oblasts_bp, url_prefix='/oblasts')

    return app
