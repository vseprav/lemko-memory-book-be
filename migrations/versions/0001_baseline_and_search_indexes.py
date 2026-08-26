"""Baseline schema and search indexes

Revision ID: 0001
Revises:
Create Date: 2026-08-26

Idempotent baseline: the table was originally created by db.create_all(),
so everything here uses IF NOT EXISTS to work on both existing and fresh DBs.

Indexes:
- GIN trigram index on full_name: makes ILIKE '%word%' searches use an index
  instead of a sequential scan (requires the pg_trgm extension; on Azure
  Flexible Server PG_TRGM must be allow-listed in the azure.extensions
  server parameter first).
- btree on family_uuid: /family/<uuid> lookups.
"""
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS evicted_persons (
            id UUID PRIMARY KEY,
            family_uuid UUID NOT NULL,
            full_name TEXT NOT NULL,
            family_role TEXT,
            birth_year TEXT,
            area_eviction TEXT,
            settlement TEXT NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # CONCURRENTLY cannot run inside a transaction block; no table lock on prod.
    with op.get_context().autocommit_block():
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_evicted_persons_full_name_trgm
            ON evicted_persons USING gin (full_name gin_trgm_ops)
        """)
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_evicted_persons_family_uuid
            ON evicted_persons (family_uuid)
        """)
    op.execute("ANALYZE evicted_persons")


def downgrade():
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_evicted_persons_family_uuid")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_evicted_persons_full_name_trgm")
    # Table and extension are intentionally kept: this is the baseline.
