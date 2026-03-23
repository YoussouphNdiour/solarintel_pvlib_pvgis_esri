"""Add missing created_at column to monitoring table.

Migration 0001 created the monitoring table without a created_at column,
but the Monitoring ORM model inherits created_at from Base. This migration
adds the column with a backfilled default of now().

Revision ID: 0003_add_monitoring_created_at
Revises: 0002_fix_enum_names
Create Date: 2026-03-23 08:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_monitoring_created_at"
down_revision: str = "0002_fix_enum_names"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE monitoring
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE monitoring DROP COLUMN IF EXISTS created_at;
    """)
