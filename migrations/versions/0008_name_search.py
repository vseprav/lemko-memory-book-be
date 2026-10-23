"""Search text for every printed name

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-24

evicted_persons.name_search holds every way a visitor may type a printed name (app/search_names.py):
the name normalized (lower case, no apostrophes, brackets and punctuation as spaces), every reading
a letter-level bracket allows ('Ко(а)чмарчик' -> кочмарчик, качмарчик), split words joined and
glued words split, and for a surname the book prints in both genders the other form ('Криницька'
-> криницький). The printed full_name is not touched. The search matches each normalized query word
as a substring of name_search, through a trigram index.

The data audit (lemko/spec/data-audit, normalize-03, -05, -08) found 1,458 people that today's search
cannot find by one of their own printed readings and 8,222 women not found by the masculine form
of their surname.
"""
import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.search_names import name_search

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

log = logging.getLogger('alembic.runtime.migration')


def upgrade():
    op.add_column('evicted_persons', sa.Column('name_search', sa.Text))
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, full_name FROM evicted_persons")).all()
    op.execute("CREATE TEMP TABLE name_search_import (id uuid PRIMARY KEY, name_search text NOT NULL)")
    import_table = sa.table('name_search_import',
                            sa.column('id', postgresql.UUID(as_uuid=True)),
                            sa.column('name_search', sa.Text))
    op.bulk_insert(import_table, [{'id': r.id, 'name_search': name_search(r.full_name)} for r in rows])
    op.execute("UPDATE evicted_persons p SET name_search = i.name_search "
               "FROM name_search_import i WHERE i.id = p.id")
    op.execute("DROP TABLE name_search_import")
    op.execute("CREATE INDEX ix_evicted_persons_name_search_trgm ON evicted_persons "
               "USING gin (name_search gin_trgm_ops)")
    missing = conn.execute(sa.text("SELECT count(*) FROM evicted_persons WHERE name_search IS NULL")).scalar()
    log.info("name_search: computed for %s rows, %s without", len(rows), missing)


def downgrade():
    op.drop_index('ix_evicted_persons_name_search_trgm', table_name='evicted_persons')
    op.drop_column('evicted_persons', 'name_search')
