"""Book positions, family numbers, list pages and totals; alias and repair-log tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-23

Schema for the data repair planned in lemko/spec/data-audit (release A). Every new column is
nullable or defaulted, so the running app keeps working; the repair (release B) fills them.

- evicted_persons: where the row is printed (its list, the <tr> index inside that list's table
  in the book HTML, the data-row number), its position inside its family, and the row kind: a
  person, or a note the book prints instead of names ('Родина №7 - заклеєно стор. - 4 особи.')
  with the number of people the note stands for.
- families: the family number as printed ('12', '138-1', '183-184', '4?'), the kind of entry
  (numbered | individual | unnumbered_household | unnumbered_group), its order in the list, and
  the printed sub-heading it stands under ('Новиця, присілок Прислоп').
- settlement_lists: the start page of the list as printed in the table of contents, e.g.
  '707 (718)', and the family count of the list's own total row as printed ('96', '170-33', '-').
- family_aliases: family uuids retired by the regrouping, so old links keep resolving.
- data_repairs: log of applied data repairs, so a repair is never applied twice.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('evicted_persons', sa.Column('list_id', sa.Integer,
                                               sa.ForeignKey('settlement_lists.id', name='fk_evicted_persons_list')))
    op.add_column('evicted_persons', sa.Column('book_tr', sa.Integer))  # <tr> index in the list's table
    op.add_column('evicted_persons', sa.Column('book_row_no', sa.Integer))  # data-row number, from 0
    op.add_column('evicted_persons', sa.Column('family_position', sa.SmallInteger))  # 1 = first printed row
    op.add_column('evicted_persons', sa.Column('row_kind', sa.Text, nullable=False, server_default='person'))
    op.add_column('evicted_persons', sa.Column('persons_represented', sa.SmallInteger))  # note rows only
    op.create_unique_constraint('uq_evicted_persons_book_tr', 'evicted_persons', ['list_id', 'book_tr'])
    op.create_check_constraint('ck_evicted_persons_row_kind', 'evicted_persons',
                               "row_kind IN ('person', 'note')")

    op.add_column('families', sa.Column('printed_no', sa.Text))
    op.add_column('families', sa.Column('kind', sa.Text))
    op.add_column('families', sa.Column('book_seq', sa.Integer))  # order of the entry in its list, from 1
    op.add_column('families', sa.Column('section', sa.Text))
    op.create_unique_constraint('uq_families_list_seq', 'families', ['list_id', 'book_seq'])
    op.create_check_constraint(
        'ck_families_kind', 'families',
        "kind IS NULL OR kind IN ('numbered', 'individual', 'unnumbered_household', 'unnumbered_group')")

    op.add_column('settlement_lists', sa.Column('book_page', sa.Text))
    op.add_column('settlement_lists', sa.Column('book_page_start', sa.SmallInteger))
    op.add_column('settlement_lists', sa.Column('list_total_families', sa.Text))

    op.create_table(
        'family_aliases',
        sa.Column('old_uuid', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('family_uuid', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('families.family_uuid'), nullable=False),
        sa.Column('reason', sa.Text),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_family_aliases_family_uuid', 'family_aliases', ['family_uuid'])

    op.create_table(
        'data_repairs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.Text, nullable=False, unique=True),
        sa.Column('applied_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('summary', postgresql.JSONB),
    )


def downgrade():
    op.drop_table('data_repairs')
    op.drop_index('ix_family_aliases_family_uuid', table_name='family_aliases')
    op.drop_table('family_aliases')
    for column in ('list_total_families', 'book_page_start', 'book_page'):
        op.drop_column('settlement_lists', column)
    op.drop_constraint('ck_families_kind', 'families', type_='check')
    op.drop_constraint('uq_families_list_seq', 'families', type_='unique')
    for column in ('section', 'book_seq', 'kind', 'printed_no'):
        op.drop_column('families', column)
    op.drop_constraint('ck_evicted_persons_row_kind', 'evicted_persons', type_='check')
    op.drop_constraint('uq_evicted_persons_book_tr', 'evicted_persons', type_='unique')
    op.drop_constraint('fk_evicted_persons_list', 'evicted_persons', type_='foreignkey')
    for column in ('persons_represented', 'row_kind', 'family_position', 'book_row_no', 'book_tr', 'list_id'):
        op.drop_column('evicted_persons', column)
