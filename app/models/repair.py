from sqlalchemy.dialects.postgresql import JSONB
from app.extensions import db


class DataRepair(db.Model):
    """Log of applied data repairs (lemko/spec/data-audit), so that a repair is never applied twice."""
    __tablename__ = 'data_repairs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    applied_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    summary = db.Column(JSONB)
