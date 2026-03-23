"""Fix enum type names to match SQLAlchemy model definitions.

Migration 0001 created enums as 'userrole' and 'reportstatus',
but the SQLAlchemy models use name="user_role" and name="report_status".
This migration renames the types so inserts/queries work correctly.

Revision ID: 0002_fix_enum_names
Revises: 0001_initial_schema
Create Date: 2026-03-23 12:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "0002_fix_enum_names"
down_revision: str = "0001_initial_schema"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    # Rename enums only if the old names exist (safe on fresh DBs)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                ALTER TYPE userrole RENAME TO user_role;
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reportstatus') THEN
                ALTER TYPE reportstatus RENAME TO report_status;
            END IF;
        END$$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
                ALTER TYPE user_role RENAME TO userrole;
            END IF;
        END$$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'report_status') THEN
                ALTER TYPE report_status RENAME TO reportstatus;
            END IF;
        END$$;
    """)
