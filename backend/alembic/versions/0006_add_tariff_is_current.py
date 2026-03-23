"""Add missing is_current column to tariff_history table.

Migration 0001 created tariff_history without the is_current column,
but the TariffHistory ORM model requires it (Mapped[bool], nullable=False).

Revision ID: 0006_add_tariff_is_current
Revises: 0005_fix_simulations_columns
Create Date: 2026-03-23 11:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "0006_add_tariff_is_current"
down_revision: str = "0005_fix_simulations_columns"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tariff_history
        ADD COLUMN IF NOT EXISTS is_current BOOLEAN NOT NULL DEFAULT false;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE tariff_history DROP COLUMN IF EXISTS is_current;
    """)
