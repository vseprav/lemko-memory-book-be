import uuid
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from sqlalchemy import Column, DateTime
from app.extensions import db


class EvictedPerson(db.Model):
    __tablename__ = 'evicted_persons'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_uuid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    full_name = db.Column(db.Text, nullable=False)
    family_role = db.Column(db.Text, nullable=True)
    birth_year = db.Column(db.Text, nullable=True)
    area_eviction = db.Column(db.Text, nullable=True)
    settlement = db.Column(db.Text, nullable=False)

    # Automatically set the current timestamp on creation
    created_at = db.Column(DateTime, default=datetime.utcnow)

    # Automatically update the timestamp on modification
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': str(self.id),
            'family_uuid': str(self.family_uuid),
            'full_name': self.full_name,
            'family_role': self.family_role,
            'birth_year': self.birth_year,
            'area_eviction': self.area_eviction,
            'settlement': self.settlement,
            # Include other fields as necessary
        }
