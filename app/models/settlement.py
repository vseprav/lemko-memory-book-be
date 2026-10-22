from sqlalchemy.dialects.postgresql import ARRAY, UUID
from app.extensions import db


# Which settlements each published name list covers (combined lists cover several)
settlement_list_settlements = db.Table(
    'settlement_list_settlements',
    db.Column('list_id', db.Integer, db.ForeignKey('settlement_lists.id'), primary_key=True),
    db.Column('settlement_id', db.Integer, db.ForeignKey('settlements.id'), primary_key=True),
)


class Settlement(db.Model):
    """One entry of the book's register of settlements (Розділ І), stored as printed."""
    __tablename__ = 'settlements'
    id = db.Column(db.Integer, primary_key=True)
    register_no = db.Column(db.SmallInteger, unique=True)
    name = db.Column(db.Text, nullable=False)
    alt_names = db.Column(ARRAY(db.Text), nullable=False, default=list)
    kind = db.Column(db.Text, nullable=False)  # village | town | unknown
    note = db.Column(db.Text)  # disambiguator as printed, e.g. "ґм. Тісна"
    hamlets = db.Column(ARRAY(db.Text), nullable=False, default=list)
    powiat_1939 = db.Column(db.Text)
    borderland = db.Column(db.Boolean, nullable=False, default=False)
    register_marks = db.Column(db.SmallInteger, nullable=False, default=0)
    volumes = db.Column(ARRAY(db.SmallInteger), nullable=False, default=list)
    territorial_code = db.Column(db.Text)
    voivodeship = db.Column(db.Text)
    powiat = db.Column(db.Text)
    gmina = db.Column(db.Text)
    printed = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'register_no': self.register_no,
            'name': self.name,
            'alt_names': list(self.alt_names),
            'kind': self.kind,
            'note': self.note,
            'hamlets': list(self.hamlets),
            'powiat_1939': self.powiat_1939,
            'borderland': self.borderland,
            'register_marks': self.register_marks,
            'volumes': list(self.volumes),
            'territorial_code': self.territorial_code,
            'voivodeship': self.voivodeship,
            'powiat': self.powiat,
            'gmina': self.gmina,
            'printed': self.printed,
        }


class SettlementList(db.Model):
    """One published name list (a person table in a volume) with the book's own numbers."""
    __tablename__ = 'settlement_lists'
    id = db.Column(db.Integer, primary_key=True)
    volume = db.Column(db.SmallInteger, nullable=False)
    table_no = db.Column(db.SmallInteger, nullable=False)
    kind = db.Column(db.Text, nullable=False)  # main | supplement | combined | group
    title = db.Column(db.Text, nullable=False)  # summary-table form: "Дошниця, Тиханя"
    heading = db.Column(db.Text, nullable=False)  # printed above the list: "Дошниця – Тиханя"
    territorial_code = db.Column(db.Text)
    voivodeship = db.Column(db.Text)
    powiat = db.Column(db.Text)
    gmina = db.Column(db.Text)
    section = db.Column(db.Text)
    families_count = db.Column(db.Integer)
    persons_count = db.Column(db.Integer)
    list_total_persons = db.Column(db.Integer)
    archive_ref = db.Column(db.Text)
    archive_pages = db.Column(db.Text)

    settlements = db.relationship('Settlement', secondary=settlement_list_settlements,
                                  order_by='Settlement.register_no')

    def to_dict(self):
        return {
            'id': self.id,
            'volume': self.volume,
            'table_no': self.table_no,
            'kind': self.kind,
            'title': self.title,
            'heading': self.heading,
            'territorial_code': self.territorial_code,
            'voivodeship': self.voivodeship,
            'powiat': self.powiat,
            'gmina': self.gmina,
            'section': self.section,
            'families_count': self.families_count,
            'persons_count': self.persons_count,
            'list_total_persons': self.list_total_persons,
            'archive_ref': self.archive_ref,
            'archive_pages': self.archive_pages,
            'settlement_ids': [s.id for s in self.settlements],
        }


class Family(db.Model):
    """Links a family (evicted_persons.family_uuid) to the list it was read from and its settlement."""
    __tablename__ = 'families'
    family_uuid = db.Column(UUID(as_uuid=True), primary_key=True)
    list_id = db.Column(db.Integer, db.ForeignKey('settlement_lists.id'))
    # Set only where the book names exactly one village; null for combined and unresolved lists
    settlement_id = db.Column(db.Integer, db.ForeignKey('settlements.id'))

    book_list = db.relationship('SettlementList')
    settlement = db.relationship('Settlement')

    def settlement_label(self):
        """What to show as the person's place: the heading printed above the list, or the village
        the book names for this family inside a group list such as 'Села повіту Сянік: …'."""
        if self.book_list is None:
            return None
        if self.book_list.kind == 'group' and self.settlement is not None:
            return self.settlement.name
        return self.book_list.heading
