"""Points on the community map for the settlements of the register

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-25

New nullable columns on settlements: the placemark name and coordinates of the village on the community
map "Мапа міст і сіл Закерзоння" (Google My Maps, MGO "Молода Лемківщина"). The family page embeds that
map centred on the village.

The map is not book data: it lives in its own columns and never changes a book value. A point is stored
only where the match is unambiguous. migrations/data/settlements_map.csv is built by
lemko/spec/settlements/tools/make_map_seed.py from the map's KML export; the rest waits for a hand review
(spec/settlements/data/settlements_map_to_review.csv).

Settlements not in the file keep nulls. A later hand review regenerates the file, and a new migration
loads it (same update, keyed by settlement id). Nothing else changes.
"""
import csv
import logging
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

DATA = Path(__file__).resolve().parent.parent / 'data'
log = logging.getLogger('alembic.runtime.migration')


def upgrade():
    op.add_column('settlements', sa.Column('map_name', sa.Text))
    op.add_column('settlements', sa.Column('map_lat', sa.Float))
    op.add_column('settlements', sa.Column('map_lng', sa.Float))

    with open(DATA / 'settlements_map.csv', encoding='utf-8', newline='') as fh:
        rows = list(csv.DictReader(fh))
    conn = op.get_bind()
    update = sa.text("UPDATE settlements SET map_name = :map_name, map_lat = :lat, map_lng = :lng WHERE id = :id")
    placed = 0
    for r in rows:
        placed += conn.execute(update, {'id': int(r['settlement_id']), 'map_name': r['map_name'],
                                        'lat': float(r['lat']), 'lng': float(r['lng'])}).rowcount
    total = conn.execute(sa.text("SELECT count(*) FROM settlements")).scalar()
    log.info("settlements: %s of %s placed on the map", placed, total)
    if placed != len(rows):
        log.warning("%s rows of settlements_map.csv name a settlement that is not in the database",
                    len(rows) - placed)


def downgrade():
    for column in ('map_lng', 'map_lat', 'map_name'):
        op.drop_column('settlements', column)
