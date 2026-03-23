"""Initial schema — all 7 core tables.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-03-23 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column(
            "role",
            sa.Enum("admin", "commercial", "technicien", "client", name="userrole"),
            nullable=False,
            server_default="client",
        ),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("google_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # ── projects ──────────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("polygon_geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("zone_area_m2", sa.Float(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_created_at", "projects", ["created_at"])

    # ── simulations ───────────────────────────────────────────────────────────
    op.create_table(
        "simulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("panel_count", sa.Integer(), nullable=False),
        sa.Column("peak_kwc", sa.Float(), nullable=False),
        sa.Column("annual_kwh", sa.Float(), nullable=False),
        sa.Column("performance_ratio", sa.Float(), nullable=True),
        sa.Column("monthly_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pvgis_raw", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("senelec_savings_xof", sa.Float(), nullable=True),
        sa.Column("payback_years", sa.Float(), nullable=True),
        sa.Column("roi_percent", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_simulations_project_id", "simulations", ["project_id"])
    op.create_index("ix_simulations_created_at", "simulations", ["created_at"])

    # ── equipment ─────────────────────────────────────────────────────────────
    op.create_table(
        "equipment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inverter_model", sa.String(length=255), nullable=True),
        sa.Column("inverter_kva", sa.Float(), nullable=True),
        sa.Column("battery_model", sa.String(length=255), nullable=True),
        sa.Column("battery_ah", sa.Float(), nullable=True),
        sa.Column("panel_model", sa.String(length=255), nullable=True),
        sa.Column("panel_wp", sa.Float(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_equipment_project"),
    )
    op.create_index("ix_equipment_project_id", "equipment", ["project_id"])

    # ── reports ───────────────────────────────────────────────────────────────
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("simulation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("html_path", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "generating", "ready", "failed", name="reportstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_simulation_id", "reports", ["simulation_id"])
    op.create_index("ix_reports_status", "reports", ["status"])

    # ── monitoring ────────────────────────────────────────────────────────────
    op.create_table(
        "monitoring",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("production_kwh", sa.Float(), nullable=False),
        sa.Column("irradiance_wm2", sa.Float(), nullable=True),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("ac_power_w", sa.Float(), nullable=True),
        sa.Column("dc_power_w", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True, server_default="webhook"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitoring_project_id", "monitoring", ["project_id"])
    op.create_index("ix_monitoring_timestamp", "monitoring", ["timestamp"])
    # Composite index for time-series queries per project
    op.create_index(
        "ix_monitoring_project_timestamp",
        "monitoring",
        ["project_id", "timestamp"],
    )

    # ── tariff_history ────────────────────────────────────────────────────────
    op.create_table(
        "tariff_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tariff_code", sa.String(length=20), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("t1_xof", sa.Float(), nullable=True),
        sa.Column("t2_xof", sa.Float(), nullable=True),
        sa.Column("t3_xof", sa.Float(), nullable=True),
        sa.Column("woyofal_xof", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tariff_history_code_date",
        "tariff_history",
        ["tariff_code", "effective_date"],
        unique=True,
    )

    # ── seed: current SENELEC tariff (DPP 2024) ───────────────────────────────
    op.execute(
        """
        INSERT INTO tariff_history (id, tariff_code, effective_date, t1_xof, t2_xof, t3_xof, woyofal_xof, notes)
        VALUES (
            gen_random_uuid(),
            'DPP',
            '2024-01-01',
            84.0,
            121.0,
            158.0,
            117.0,
            'SENELEC Domestic Power Plan 2024 — T1: 0-150 kWh, T2: 151-400 kWh, T3: >400 kWh'
        )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("tariff_history")
    op.drop_table("monitoring")
    op.drop_table("reports")
    op.drop_table("equipment")
    op.drop_table("simulations")
    op.drop_table("projects")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS reportstatus")
