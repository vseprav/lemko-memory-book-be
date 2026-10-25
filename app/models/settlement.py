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
    # Not book data: Wikipedia links where unambiguous (migration 0009); null when there is none
    wikidata_id = db.Column(db.Text)
    wikipedia_uk = db.Column(db.Text)  # article title on uk.wikipedia.org
    wikipedia_pl = db.Column(db.Text)
    wikipedia_en = db.Column(db.Text)
    name_pl = db.Column(db.Text)  # current Polish name (Wikidata label)
    # Not book data: the village's point on the community map (migration 0010); null when there is none
    map_name = db.Column(db.Text)  # placemark name on the map
    map_lat = db.Column(db.Float)
    map_lng = db.Column(db.Float)

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
            # Kept apart from the book's fields; null when the settlement has no linked article
            'wikipedia': {
                'wikidata_id': self.wikidata_id,
                'uk': self.wikipedia_uk,
                'pl': self.wikipedia_pl,
                'en': self.wikipedia_en,
                'name_pl': self.name_pl,
            } if self.wikidata_id else None,
            # Kept apart from the book's fields; null when the settlement is not on the map
            'map': {
                'name': self.map_name,
                'lat': self.map_lat,
                'lng': self.map_lng,
            } if self.map_lat is not None else None,
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
    families_count = db.Column(db.Integer)  # summary-table row (Розділ ІІ)
    persons_count = db.Column(db.Integer)
    list_total_persons = db.Column(db.Integer)  # the list's own "Всього з …" row
    list_total_families = db.Column(db.Text)  # same row, as printed: "96", "170-33", "-"
    book_page = db.Column(db.Text)  # start page as printed in the table of contents: "707 (718)"
    book_page_start = db.Column(db.SmallInteger)
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
            'list_total_families': self.list_total_families,
            'book_page': self.book_page,
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
    # Filled by the data repair (lemko/spec/data-audit); null until then
    printed_no = db.Column(db.Text)  # the family number as printed: "12", "138-1", "183-184", "4?"
    kind = db.Column(db.Text)  # numbered | individual | unnumbered_household | unnumbered_group
    book_seq = db.Column(db.Integer)  # order of the entry in its list, from 1
    section = db.Column(db.Text)  # printed sub-heading the family stands under: "Новиця, присілок Прислоп"

    book_list = db.relationship('SettlementList')
    settlement = db.relationship('Settlement')

    def to_dict(self):
        return {
            'family_uuid': str(self.family_uuid),
            'printed_no': self.printed_no,
            'kind': self.kind,
            'book_seq': self.book_seq,
            'section': self.section,
        }

    def settlement_label(self):
        """What to show as the person's place: the heading printed above the list, or the village
        the book names for this family inside a group list such as 'Села повіту Сянік: …'."""
        if self.book_list is None:
            return None
        if self.book_list.kind == 'group' and self.settlement is not None:
            return self.settlement.name
        return self.book_list.heading


class FamilyAlias(db.Model):
    """A family uuid retired by the data repair's regrouping, kept so that old links resolve."""
    __tablename__ = 'family_aliases'
    old_uuid = db.Column(UUID(as_uuid=True), primary_key=True)
    family_uuid = db.Column(UUID(as_uuid=True), db.ForeignKey('families.family_uuid'), nullable=False)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    family = db.relationship('Family')
