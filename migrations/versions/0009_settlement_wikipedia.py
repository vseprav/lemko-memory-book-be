"""Wikipedia links for the settlements of the register

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-24

New nullable columns on settlements: the Wikidata item, the article titles on Ukrainian, Polish and
English Wikipedia, and the current Polish name (the Wikidata label). The family page shows a card
with the article's summary, fetched by the browser from Wikipedia.

Wikipedia is not book data: it lives in its own columns and never changes a book value. A link is
stored only where it is unambiguous. migrations/data/settlements_wikipedia.csv is built by
lemko/spec/settlements/tools/make_wiki_seed.py, which takes a probe match only when no other register
entry got the same article, no other entry has the same name and the article title is the printed
name; the rest waits for a hand review (spec/settlements/data/settlements_wikipedia_to_review.csv).

Settlements not in the file keep nulls. A later hand review regenerates the file, and a new migration
loads it (same update, keyed by settlement id). Nothing else changes.
"""
import csv
import logging
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

DATA = Path(__file__).resolve().parent.parent / 'data'
log = logging.getLogger('alembic.runtime.migration')
COLUMNS = ('wikidata_id', 'wikipedia_uk', 'wikipedia_pl', 'wikipedia_en', 'name_pl')


def upgrade():
    for column in COLUMNS:
        op.add_column('settlements', sa.Column(column, sa.Text))

    with open(DATA / 'settlements_wikipedia.csv', encoding='utf-8', newline='') as fh:
        rows = list(csv.DictReader(fh))
    conn = op.get_bind()
    update = sa.text(f"UPDATE settlements SET {', '.join(f'{c} = :{c}' for c in COLUMNS)} WHERE id = :id")
    linked = 0
    for r in rows:
        params = {'id': int(r['settlement_id'])}
        params.update({c: (r[c] or None) for c in COLUMNS})
        linked += conn.execute(update, params).rowcount
    total = conn.execute(sa.text("SELECT count(*) FROM settlements")).scalar()
    log.info("settlements: %s of %s linked to Wikipedia", linked, total)
    if linked != len(rows):
        log.warning("%s rows of settlements_wikipedia.csv name a settlement that is not in the database",
                    len(rows) - linked)


def downgrade():
    for column in reversed(COLUMNS):
        op.drop_column('settlements', column)
