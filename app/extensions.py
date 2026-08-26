from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# Per-client-IP rate limiting. In-memory storage is per worker process,
# which is fine for a single small App Service instance.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60 per minute", "1000 per hour"],
    storage_uri="memory://",
    headers_enabled=True,
)
