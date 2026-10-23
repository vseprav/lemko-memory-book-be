import uuid
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from sqlalchemy import Column, DateTime, event
from app.extensions import db
from app.search_names import name_search
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

    # Where the row is printed; filled by the data repair (lemko/spec/data-audit), null until then
    list_id = db.Column(db.Integer, db.ForeignKey('settlement_lists.id'))
    book_tr = db.Column(db.Integer)  # <tr> index inside the list's table in the book HTML; the row's key
    book_row_no = db.Column(db.Integer)  # data-row number inside the list, from 0
    family_position = db.Column(db.SmallInteger)  # position inside the family in book order, from 1
    # 'person', or 'note' for a row the book prints instead of names ("Родина №7 - заклеєно стор. - 4 особи.")
    row_kind = db.Column(db.Text, nullable=False, default='person', server_default='person')
    persons_represented = db.Column(db.SmallInteger)  # for a note row: how many people it stands for
    # Every way to type the printed name (app/search_names.py); kept in step with full_name below
    name_search = db.Column(db.Text)

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
            # Book order inside the family, from 1 (null before the data repair)
            'family_position': self.family_position,
            # 'note' for a row the book prints instead of names; persons_represented says for how many
            'row_kind': self.row_kind,
            'persons_represented': self.persons_represented,
        }


@event.listens_for(EvictedPerson, 'before_insert')
@event.listens_for(EvictedPerson, 'before_update')
def _keep_name_search(mapper, connection, person):
    """Rows written through the ORM (seed_db, future imports) get their search text like migration 0008."""
    person.name_search = name_search(person.full_name)
