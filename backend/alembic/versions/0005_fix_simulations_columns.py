"""Add missing columns to simulations table.

Migration 0001 created the simulations table without specific_yield, status,
and error_message columns, but the Simulation ORM model requires them.

Revision ID: 0005_fix_simulations_columns
Revises: 0004_fix_equipment_columns
Create Date: 2026-03-23 10:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "0005_fix_simulations_columns"
down_revision: str = "0004_fix_equipment_columns"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    # Create simulation_status enum type if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'simulation_status') THEN
                CREATE TYPE simulation_status AS ENUM ('pending', 'running', 'completed', 'failed');
            END IF;
        END$$;
    """)

    # Add specific_yield column
    op.execute("""
        ALTER TABLE simulations
        ADD COLUMN IF NOT EXISTS specific_yield FLOAT;
    """)

    # Add status column with enum type and default 'completed'
    # (existing rows are completed simulations)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'simulations' AND column_name = 'status'
            ) THEN
                ALTER TABLE simulations
                ADD COLUMN status simulation_status NOT NULL DEFAULT 'completed';
            END IF;
        END$$;
    """)

    # Add error_message column
    op.execute("""
        ALTER TABLE simulations
        ADD COLUMN IF NOT EXISTS error_message TEXT;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE simulations DROP COLUMN IF EXISTS specific_yield;")
    op.execute("ALTER TABLE simulations DROP COLUMN IF EXISTS error_message;")
    op.execute("ALTER TABLE simulations DROP COLUMN IF EXISTS status;")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'simulation_status') THEN
                DROP TYPE simulation_status;
            END IF;
        END$$;
    """)
