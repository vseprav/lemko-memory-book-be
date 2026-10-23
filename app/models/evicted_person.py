import uuid
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from sqlalchemy import Column, DateTime
from app.extensions import db
from app.models.settlement import Family  # noqa: F401  (registers the mapper for the relationship)
from app.models.area import Area  # noqa: F401


class EvictedPerson(db.Model):
    __tablename__ = 'evicted_persons'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # No default on purpose: a person must belong to an existing family (see families table)
    family_uuid = db.Column(UUID(as_uuid=True), db.ForeignKey('families.family_uuid'), nullable=False)
    full_name = db.Column(db.Text, nullable=False)
    family_role = db.Column(db.Text, nullable=True)
    birth_year = db.Column(db.Text, nullable=True)
    area_eviction = db.Column(db.Text, nullable=True)  # as printed; areas.printed holds the same text
    area_id = db.Column(db.Integer, db.ForeignKey('areas.id'))  # null when the value is empty
    settlement = db.Column(db.Text, nullable=False)

    # Automatically set the current timestamp on creation
    created_at = db.Column(DateTime, default=datetime.utcnow)

    # Automatically update the timestamp on modification
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    family = db.relationship('Family')
    area = db.relationship('Area')

    def settlement_id(self):
        """The register entry behind the person's place, when the book points at exactly one:
        the village named for the family, or the only settlement of their list. Else None."""
        family = self.family
        if family is None:
            return None
        if family.settlement_id is not None:
            return family.settlement_id
        if family.book_list is not None and len(family.book_list.settlements) == 1:
            return family.book_list.settlements[0].id
        return None

    def to_dict(self):
        family = self.family
        return {
            'id': str(self.id),
            'family_uuid': str(self.family_uuid),
            'full_name': self.full_name,
            'family_role': self.family_role,
            'birth_year': self.birth_year,
            'area_eviction': self.area_eviction,
            # The heading printed above the book's list; the old free-text column only when the family has no list
            'settlement': (family.settlement_label() if family else None) or self.settlement,
            # For linking to the settlement filter; null when the list covers several villages
            'settlement_id': self.settlement_id(),
        }
