"""Fix equipment column names to match ORM model.

Migration 0001 created equipment table with panel_wp and battery_ah,
but the ORM model uses panel_power_wc (Integer) and battery_kwh (Float).

Revision ID: 0004_fix_equipment_columns
Revises: 0003_add_monitoring_created_at
Create Date: 2026-03-23 09:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "0004_fix_equipment_columns"
down_revision: str = "0003_add_monitoring_created_at"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'equipment' AND column_name = 'panel_wp'
            ) THEN
                ALTER TABLE equipment RENAME COLUMN panel_wp TO panel_power_wc;
                ALTER TABLE equipment ALTER COLUMN panel_power_wc TYPE INTEGER
                    USING panel_power_wc::INTEGER;
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'equipment' AND column_name = 'battery_ah'
            ) THEN
                ALTER TABLE equipment RENAME COLUMN battery_ah TO battery_kwh;
            END IF;
        END$$;
    """)
    # Add created_at if missing (same pattern as monitoring)
    op.execute("""
        ALTER TABLE equipment
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'equipment' AND column_name = 'panel_power_wc'
            ) THEN
                ALTER TABLE equipment ALTER COLUMN panel_power_wc TYPE FLOAT
                    USING panel_power_wc::FLOAT;
                ALTER TABLE equipment RENAME COLUMN panel_power_wc TO panel_wp;
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'equipment' AND column_name = 'battery_kwh'
            ) THEN
                ALTER TABLE equipment RENAME COLUMN battery_kwh TO battery_ah;
            END IF;
        END$$;
    """)
