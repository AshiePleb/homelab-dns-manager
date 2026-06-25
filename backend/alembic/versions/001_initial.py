"""initial

Revision ID: 001
Revises:
Create Date: 2026-06-24

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, index=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255)),
        sa.Column("role", sa.Enum("admin", "operator", "viewer", name="userrole"), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(128), unique=True, index=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("encrypted", sa.Boolean(), default=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "domains",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("zone_id", sa.String(64), unique=True, index=True),
        sa.Column("name", sa.String(255), index=True),
        sa.Column("status", sa.String(32)),
        sa.Column("account_id", sa.String(64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "dns_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("domains.id"), index=True),
        sa.Column("cloudflare_record_id", sa.String(64), nullable=True),
        sa.Column("hostname", sa.String(255), index=True),
        sa.Column("record_type", sa.String(16)),
        sa.Column("content", sa.String(512)),
        sa.Column("proxied", sa.Boolean()),
        sa.Column("managed", sa.Boolean()),
        sa.Column("ttl", sa.Integer()),
        sa.Column("status", sa.String(32)),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "dns_record_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("dns_records.id"), index=True),
        sa.Column("old_content", sa.String(512), nullable=True),
        sa.Column("new_content", sa.String(512)),
        sa.Column("change_reason", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "ip_change_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("old_ip", sa.String(45), nullable=True),
        sa.Column("new_ip", sa.String(45)),
        sa.Column("affected_records", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("level", sa.Enum("info", "warning", "error", "success", name="loglevel"), nullable=False),
        sa.Column("category", sa.String(64), index=True),
        sa.Column("message", sa.Text()),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "npm_proxy_hosts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("npm_id", sa.Integer(), nullable=True),
        sa.Column("domain_names", sa.JSON()),
        sa.Column("forward_host", sa.String(255)),
        sa.Column("forward_port", sa.Integer()),
        sa.Column("ssl_enabled", sa.Boolean()),
        sa.Column("certificate_id", sa.Integer(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("npm_proxy_hosts")
    op.drop_table("activity_logs")
    op.drop_table("ip_change_logs")
    op.drop_table("dns_record_history")
    op.drop_table("dns_records")
    op.drop_table("domains")
    op.drop_table("app_settings")
    op.drop_table("users")
