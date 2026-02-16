"""Initial schema - alle Tabellen

Revision ID: 001_initial
Revises: None
Create Date: 2026-02-15

Erstellt die komplette Datenbankstruktur als Baseline.
Bestehende Datenbanken, die via create_all() angelegt wurden,
werden als "bereits migriert" markiert (alembic stamp head).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ack
    op.create_table(
        "ack",
        sa.Column("case_id", sa.String(), primary_key=True),
        sa.Column("station_id", sa.String(), primary_key=True),
        sa.Column("ack_scope", sa.String(), primary_key=True),
        sa.Column("scope_id", sa.String(), primary_key=True),
        sa.Column("acked_at", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("condition_hash", sa.Text(), nullable=True),
        sa.Column("business_date", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("shift_code", sa.Text(), nullable=True),
    )

    # AckEvent
    op.create_table(
        "ack_event",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("ts", sa.String(), nullable=True),
        sa.Column("case_id", sa.String(), nullable=True),
        sa.Column("station_id", sa.String(), nullable=True),
        sa.Column("ack_scope", sa.String(), nullable=True),
        sa.Column("scope_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
    )

    # DayState
    op.create_table(
        "day_state",
        sa.Column("station_id", sa.String(), primary_key=True),
        sa.Column("business_date", sa.String(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
    )

    # User
    op.create_table(
        "user",
        sa.Column("user_id", sa.String(), primary_key=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(), nullable=True),
    )

    # Role
    op.create_table(
        "role",
        sa.Column("role_id", sa.String(), primary_key=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="1"),
    )

    # Permission
    op.create_table(
        "permission",
        sa.Column("perm_id", sa.String(), primary_key=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="1"),
    )

    # RolePermission
    op.create_table(
        "role_permission",
        sa.Column("role_id", sa.String(), sa.ForeignKey("role.role_id"), primary_key=True),
        sa.Column("perm_id", sa.String(), sa.ForeignKey("permission.perm_id"), primary_key=True),
    )

    # UserRole
    op.create_table(
        "user_role",
        sa.Column("user_id", sa.String(), sa.ForeignKey("user.user_id"), primary_key=True),
        sa.Column("role_id", sa.String(), sa.ForeignKey("role.role_id"), primary_key=True),
        sa.Column("station_id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
    )

    # BreakGlassSession
    op.create_table(
        "break_glass_session",
        sa.Column("session_id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("station_id", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.String(), nullable=True),
        sa.Column("expires_at", sa.String(), nullable=True),
        sa.Column("revoked_at", sa.String(), nullable=True),
        sa.Column("revoked_by", sa.String(), nullable=True),
    )

    # SecurityEvent
    op.create_table(
        "security_event",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("ts", sa.String(), nullable=True),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("actor_station_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=True),
        sa.Column("target_type", sa.String(), nullable=True),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
    )

    # RuleDefinition
    op.create_table(
        "rule_definition",
        sa.Column("rule_id", sa.String(), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("severity", sa.String(), nullable=True),
        sa.Column("metric", sa.String(), nullable=True),
        sa.Column("operator", sa.String(), nullable=True),
        sa.Column("value_json", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
    )

    # Case
    op.create_table(
        "case_data",
        sa.Column("case_id", sa.String(), primary_key=True),
        sa.Column("station_id", sa.String(), nullable=False, index=True),
        sa.Column("patient_id", sa.String(), nullable=True),
        sa.Column("patient_initials", sa.String(), nullable=True),
        sa.Column("clinic", sa.String(), nullable=True),
        sa.Column("center", sa.String(), nullable=True),
        sa.Column("admission_date", sa.String(), nullable=False),
        sa.Column("discharge_date", sa.String(), nullable=True),
        sa.Column("honos_entry_total", sa.Integer(), nullable=True),
        sa.Column("honos_entry_date", sa.String(), nullable=True),
        sa.Column("honos_discharge_total", sa.Integer(), nullable=True),
        sa.Column("honos_discharge_date", sa.String(), nullable=True),
        sa.Column("honos_discharge_suicidality", sa.Integer(), nullable=True),
        sa.Column("bscl_total_entry", sa.Integer(), nullable=True),
        sa.Column("bscl_entry_date", sa.String(), nullable=True),
        sa.Column("bscl_total_discharge", sa.Integer(), nullable=True),
        sa.Column("bscl_discharge_date", sa.String(), nullable=True),
        sa.Column("bscl_discharge_suicidality", sa.Integer(), nullable=True),
        sa.Column("bfs_1", sa.String(), nullable=True),
        sa.Column("bfs_2", sa.String(), nullable=True),
        sa.Column("bfs_3", sa.String(), nullable=True),
        sa.Column("isolations_json", sa.Text(), nullable=True),
        sa.Column("imported_at", sa.String(), nullable=True),
        sa.Column("imported_by", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
    )

    # ShiftReason
    op.create_table(
        "shift_reason",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(), unique=True, nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    # NotificationRule
    op.create_table(
        "notification_rule",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("station_id", sa.String(), nullable=True),
        sa.Column("min_severity", sa.String(), nullable=False, server_default="CRITICAL"),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("delay_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("notification_rule")
    op.drop_table("shift_reason")
    op.drop_table("case_data")
    op.drop_table("rule_definition")
    op.drop_table("security_event")
    op.drop_table("break_glass_session")
    op.drop_table("user_role")
    op.drop_table("role_permission")
    op.drop_table("permission")
    op.drop_table("role")
    op.drop_table("user")
    op.drop_table("day_state")
    op.drop_table("ack_event")
    op.drop_table("ack")
