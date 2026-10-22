"""Families: link every person's family to its book list and settlement

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22

Settlement is a family attribute (no family spans two lists), so the link lives on a new
families table: one row per distinct evicted_persons.family_uuid, with the name list the
family was read from and, where the book names exactly one village, the settlement.
migrations/data/family_lists.csv maps family_uuid -> list (traced through the parser CSVs,
see lemko/spec/settlements). Families not in the mapping get a row with null links, so the
migration cannot fail on data that differs from the export.

Finally evicted_persons.family_uuid gets a foreign key to families, so a future import must
create the family first.
"""
import csv
import logging
import uuid
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

DATA = Path(__file__).resolve().parent.parent / 'data'
log = logging.getLogger('alembic.runtime.migration')


def upgrade():
    op.create_table(
        'families',
        sa.Column('family_uuid', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('list_id', sa.Integer, sa.ForeignKey('settlement_lists.id')),
        sa.Column('settlement_id', sa.Integer, sa.ForeignKey('settlements.id')),
    )
    op.create_index('ix_families_list_id', 'families', ['list_id'])
    op.create_index('ix_families_settlement_id', 'families', ['settlement_id'])

    op.execute("INSERT INTO families (family_uuid) SELECT DISTINCT family_uuid FROM evicted_persons")

    # Load the mapping through a temp table so the update is a single join.
    op.execute("CREATE TEMP TABLE family_lists_import "
               "(family_uuid uuid PRIMARY KEY, list_id integer, settlement_id integer)")
    import_table = sa.table(
        'family_lists_import',
        sa.column('family_uuid', postgresql.UUID(as_uuid=True)),
        sa.column('list_id', sa.Integer),
        sa.column('settlement_id', sa.Integer),
    )
    with open(DATA / 'family_lists.csv', encoding='utf-8', newline='') as f:
        op.bulk_insert(import_table, [
            dict(
                family_uuid=uuid.UUID(r['family_uuid']),
                list_id=int(r['list_id']) if r['list_id'] else None,
                settlement_id=int(r['settlement_id']) if r['settlement_id'] else None,
            )
            for r in csv.DictReader(f)
        ])
    op.execute("""
        UPDATE families f
        SET list_id = i.list_id, settlement_id = i.settlement_id
        FROM family_lists_import i
        WHERE i.family_uuid = f.family_uuid
    """)
    op.execute("DROP TABLE family_lists_import")

    op.create_foreign_key('fk_evicted_persons_family', 'evicted_persons', 'families',
                          ['family_uuid'], ['family_uuid'])

    conn = op.get_bind()
    total = conn.execute(sa.text("SELECT count(*) FROM families")).scalar()
    unmapped = conn.execute(sa.text("SELECT count(*) FROM families WHERE list_id IS NULL")).scalar()
    log.info("families: %s rows, %s without a book list", total, unmapped)
    if unmapped:
        log.warning("%s families are not in family_lists.csv; their settlement info will be empty", unmapped)


def downgrade():
    op.drop_constraint('fk_evicted_persons_family', 'evicted_persons', type_='foreignkey')
    op.drop_table('families')
