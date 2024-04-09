from app.extensions import db
import uuid
from sqlalchemy.dialects.postgresql import UUID

class EvictedPerson(db.Model):
    __tablename__ = 'evicted_persons'
    id = db.Column(db.Column(UUID(as_uuid=True), primary_key=True))
    family_uuid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    full_name = db.Column(db.Text, nullable=False)
    family_role = db.Column(db.Text, nullable=True)
    birth_year = db.Column(db.Text, nullable=True)
    area_eviction = db.Column(db.Text, nullable=True)
    settlement = db.Column(db.Text, nullable=False)
