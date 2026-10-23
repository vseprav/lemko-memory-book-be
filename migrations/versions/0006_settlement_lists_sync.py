"""Bring settlement_lists in line with the regenerated seed file

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-23

The data audit (lemko/spec/data-audit, findings BC-11, EI-07, EI-08, content-01) found that the
seed loaded by migration 0002 carried a block's 1944-46 context too far in the summary table
(110 lists, among them the 101 supplement lists at the end of volume 3 shown as 'повіт Березів'),
took 21 headings from parser file names instead of the printed heading, and missed the total row
of 5 lists. migrations/data/settlement_lists.csv is regenerated from the book with those
corrections (lemko/spec/settlements/tools/make_seed_files.py) and now also carries the start page
of each list from the table of contents and the family count of the list's own total row.

The same regeneration drops the code that volume 1 prints in front of its voivodeship header
('2. Ряшівське/Жешувське воєводство') from the division labels of lists and settlements, so one
voivodeship has one name.

This migration updates every list row from settlement_lists.csv, keyed by (volume, table_no), and
the division labels of every settlement from settlements.csv, keyed by id. Running it twice changes
nothing. Nothing is deleted.
"""
import csv
import logging
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

DATA = Path(__file__).resolve().parent.parent / 'data'
log = logging.getLogger('alembic.runtime.migration')

TEXT = ('kind', 'title', 'heading', 'territorial_code', 'voivodeship', 'powiat', 'gmina', 'section',
        'list_total_families', 'book_page', 'archive_ref', 'archive_pages')
INT = ('families_count', 'persons_count', 'list_total_persons', 'book_page_start')
COLUMNS = TEXT + INT

UPDATE = sa.text(f"""
    UPDATE settlement_lists
    SET {', '.join(f'{c} = :{c}' for c in COLUMNS)}
    WHERE volume = :volume AND table_no = :table_no
      AND ({', '.join(COLUMNS)}) IS DISTINCT FROM ({', '.join(f':{c}' for c in COLUMNS)})
""")
EXISTS = sa.text("SELECT 1 FROM settlement_lists WHERE volume = :volume AND table_no = :table_no")

DIVISION = ('territorial_code', 'voivodeship', 'powiat', 'gmina')
UPDATE_SETTLEMENT = sa.text(f"""
    UPDATE settlements
    SET {', '.join(f'{c} = :{c}' for c in DIVISION)}
    WHERE id = :id
      AND ({', '.join(DIVISION)}) IS DISTINCT FROM ({', '.join(f':{c}' for c in DIVISION)})
""")


def read_csv(name):
    with open(DATA / name, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def upgrade():
    conn = op.get_bind()
    rows = read_csv('settlement_lists.csv')
    changed, missing = 0, []
    for r in rows:
        params = {'volume': int(r['volume']), 'table_no': int(r['table_no'])}
        params.update({c: (r[c] or None) for c in TEXT})
        params.update({c: (int(r[c]) if r[c] else None) for c in INT})
        if conn.execute(EXISTS, params).first() is None:
            missing.append(f"{r['volume']}/{r['table_no']}")
            continue
        changed += conn.execute(UPDATE, params).rowcount
    log.info("settlement_lists: %s of %s rows updated from settlement_lists.csv", changed, len(rows))
    if missing:
        log.warning("%s lists of settlement_lists.csv are not in the database: %s", len(missing), missing[:10])

    rows = read_csv('settlements.csv')
    changed = 0
    for r in rows:
        params = {'id': int(r['id'])}
        params.update({c: (r[c] or None) for c in DIVISION})
        changed += conn.execute(UPDATE_SETTLEMENT, params).rowcount
    log.info("settlements: %s of %s rows had their division labels updated from settlements.csv", changed, len(rows))


def downgrade():
    # The old values came from the same table's history; 0002's CSV no longer holds them.
    pass
