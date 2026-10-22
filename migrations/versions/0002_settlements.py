"""Settlements from the book: register, name lists and their links

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22

Three reference tables filled from migrations/data/*.csv:
- settlements: one row per entry of the book's register of settlements (Розділ І, volume 3
  edition), plus places that have a name list but no register entry (Відач).
- settlement_lists: one row per published name list (Розділ ІІ summary table row), with the
  book's counts and the archive reference.
- settlement_list_settlements: which settlements each list covers (combined lists cover 2-4).

The book is the source of truth: values are stored as printed, nothing is corrected. The CSVs
were generated from the book HTML by lemko/spec/settlements/tools and travel with the
migration, so the same `flask db upgrade` works locally and on Azure.
"""
import csv
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

DATA = Path(__file__).resolve().parent.parent / 'data'


def read_csv(name):
    with open(DATA / name, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def text_or_none(value):
    return value or None


def int_or_none(value):
    return int(value) if value else None


def split(value):
    return [part for part in value.split('|') if part]


def upgrade():
    settlements = op.create_table(
        'settlements',
        sa.Column('id', sa.Integer, primary_key=True),
        # Position in the volume 3 register; null for places that are not in it
        sa.Column('register_no', sa.SmallInteger, unique=True),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('alt_names', postgresql.ARRAY(sa.Text), nullable=False, server_default='{}'),
        sa.Column('kind', sa.Text, nullable=False),  # village | town | unknown
        sa.Column('note', sa.Text),  # disambiguator as printed, e.g. "ґм. Тісна"
        sa.Column('hamlets', postgresql.ARRAY(sa.Text), nullable=False, server_default='{}'),
        sa.Column('powiat_1939', sa.Text),
        sa.Column('borderland', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('register_marks', sa.SmallInteger, nullable=False, server_default='0'),
        sa.Column('volumes', postgresql.ARRAY(sa.SmallInteger), nullable=False, server_default='{}'),
        # Archive division (1944-46) from the settlement's main list
        sa.Column('territorial_code', sa.Text),
        sa.Column('voivodeship', sa.Text),
        sa.Column('powiat', sa.Text),
        sa.Column('gmina', sa.Text),
        sa.Column('printed', sa.Text, nullable=False),  # the register line as printed
    )
    lists = op.create_table(
        'settlement_lists',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('volume', sa.SmallInteger, nullable=False),
        sa.Column('table_no', sa.SmallInteger, nullable=False),  # table number in the volume
        sa.Column('kind', sa.Text, nullable=False),  # main | supplement | combined | group
        sa.Column('title', sa.Text, nullable=False),  # as printed in the summary table
        sa.Column('heading', sa.Text, nullable=False),  # as printed above the list itself; what people see
        sa.Column('territorial_code', sa.Text),
        sa.Column('voivodeship', sa.Text),
        sa.Column('powiat', sa.Text),
        sa.Column('gmina', sa.Text),
        sa.Column('section', sa.Text),
        sa.Column('families_count', sa.Integer),
        sa.Column('persons_count', sa.Integer),
        sa.Column('list_total_persons', sa.Integer),  # the list's own "Всього з …" row
        sa.Column('archive_ref', sa.Text),
        sa.Column('archive_pages', sa.Text),
        sa.UniqueConstraint('volume', 'table_no', name='uq_settlement_lists_volume_table_no'),
    )
    links = op.create_table(
        'settlement_list_settlements',
        sa.Column('list_id', sa.Integer, sa.ForeignKey('settlement_lists.id', ondelete='CASCADE'),
                  primary_key=True),
        sa.Column('settlement_id', sa.Integer, sa.ForeignKey('settlements.id', ondelete='CASCADE'),
                  primary_key=True),
    )
    op.create_index('ix_settlements_name', 'settlements', ['name'])
    op.create_index('ix_settlement_list_settlements_settlement_id', 'settlement_list_settlements',
                    ['settlement_id'])

    op.bulk_insert(settlements, [
        dict(
            id=int(r['id']),
            register_no=int_or_none(r['register_no']),
            name=r['name'],
            alt_names=split(r['alt_names']),
            kind=r['kind'],
            note=text_or_none(r['note']),
            hamlets=split(r['hamlets']),
            powiat_1939=text_or_none(r['powiat_1939']),
            borderland=r['borderland'] == '1',
            register_marks=int(r['register_marks']),
            volumes=[int(v) for v in split(r['volumes'])],
            territorial_code=text_or_none(r['territorial_code']),
            voivodeship=text_or_none(r['voivodeship']),
            powiat=text_or_none(r['powiat']),
            gmina=text_or_none(r['gmina']),
            printed=r['printed'],
        )
        for r in read_csv('settlements.csv')
    ])
    op.bulk_insert(lists, [
        dict(
            id=int(r['id']),
            volume=int(r['volume']),
            table_no=int(r['table_no']),
            kind=r['kind'],
            title=r['title'],
            heading=r['heading'],
            territorial_code=text_or_none(r['territorial_code']),
            voivodeship=text_or_none(r['voivodeship']),
            powiat=text_or_none(r['powiat']),
            gmina=text_or_none(r['gmina']),
            section=text_or_none(r['section']),
            families_count=int_or_none(r['families_count']),
            persons_count=int_or_none(r['persons_count']),
            list_total_persons=int_or_none(r['list_total_persons']),
            archive_ref=text_or_none(r['archive_ref']),
            archive_pages=text_or_none(r['archive_pages']),
        )
        for r in read_csv('settlement_lists.csv')
    ])
    op.bulk_insert(links, [
        dict(list_id=int(r['list_id']), settlement_id=int(r['settlement_id']))
        for r in read_csv('settlement_list_settlements.csv')
    ])
    # Rows were inserted with explicit ids; move the sequences past them.
    for table in ('settlements', 'settlement_lists'):
        op.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT max(id) FROM {table}))")


def downgrade():
    op.drop_table('settlement_list_settlements')
    op.drop_table('settlement_lists')
    op.drop_table('settlements')
