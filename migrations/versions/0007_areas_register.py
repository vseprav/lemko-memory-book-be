"""Areas register: printed readings instead of the old parser's glued ones

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-23

The data audit (lemko/spec/data-audit, findings fields-02 and G3-11) found that 12 values of the
areas register loaded by migration 0004 are not printed readings but the old parser's glueing of
two-line cells ('Сталінська, ниніДонецька', 'м. Стрий,Дрогобицька обл.'), and that two printed
two-line values are missing ('Тернопільська Тернопільська', 'Тернопільська Станіславська').

migrations/data/areas.csv is regenerated with the printed readings; areas_renamed.csv lists each
old value with its printed reading. This migration:
- renames a glued value in place when its printed reading is not registered yet, which keeps
  every person's area_id valid;
- merges a glued value into the registered printed reading otherwise, re-pointing area_id first;
- adds the missing printed values and refreshes the oblast link of every registered value.
Nothing else is deleted. Until the data repair (release B) rewrites the person rows, the text in
evicted_persons.area_eviction of the affected people still shows the old reading; their area_id
and the oblast filter are right throughout.
"""
import csv
import logging
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

DATA = Path(__file__).resolve().parent.parent / 'data'
log = logging.getLogger('alembic.runtime.migration')


def read_csv(name):
    with open(DATA / name, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def upgrade():
    conn = op.get_bind()

    def area_id(printed):
        return conn.execute(sa.text("SELECT id FROM areas WHERE printed = :p"), {'p': printed}).scalar()

    renamed = merged = 0
    for r in read_csv('areas_renamed.csv'):
        old, new = r['old_printed'], r['printed_reading']
        if not new:  # not a printed reading of any cell; the data repair rewrites those rows
            continue
        old_id = area_id(old)
        if old_id is None:
            continue
        new_id = area_id(new)
        if new_id is None:
            conn.execute(sa.text("UPDATE areas SET printed = :new WHERE id = :id"), {'new': new, 'id': old_id})
            renamed += 1
        else:
            conn.execute(sa.text("UPDATE evicted_persons SET area_id = :new_id WHERE area_id = :old_id"),
                         {'new_id': new_id, 'old_id': old_id})
            conn.execute(sa.text("DELETE FROM areas WHERE id = :id"), {'id': old_id})
            merged += 1

    added = refreshed = 0
    for r in read_csv('areas.csv'):
        params = {'printed': r['printed'], 'oblast_id': int(r['oblast_id']) if r['oblast_id'] else None,
                  'locality': r['locality'] or None, 'uncertain': r['uncertain'] == '1'}
        if area_id(r['printed']) is None:
            conn.execute(sa.text(
                "INSERT INTO areas (printed, oblast_id, locality, uncertain) "
                "VALUES (:printed, :oblast_id, :locality, :uncertain)"), params)
            added += 1
        else:
            refreshed += conn.execute(sa.text(
                "UPDATE areas SET oblast_id = :oblast_id, locality = :locality, uncertain = :uncertain "
                "WHERE printed = :printed "
                "AND (oblast_id, locality, uncertain) IS DISTINCT FROM (:oblast_id, :locality, :uncertain)"),
                params).rowcount
    log.info("areas: %s values renamed to the printed reading, %s merged into it, %s added, %s links refreshed",
             renamed, merged, added, refreshed)


def downgrade():
    # The glued readings are gone for good; migration 0004's history is in git.
    pass
