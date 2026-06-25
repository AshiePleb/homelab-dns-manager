"""proxy hosts and app_created flag

Revision ID: 003
Revises: 002
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("dns_records") as batch_op:
        batch_op.add_column(
            sa.Column("app_created", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    op.execute("UPDATE dns_records SET app_created = 0 WHERE managed = 0")

    op.create_table(
        "proxy_hosts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hostname", sa.String(255), unique=True, index=True),
        sa.Column("forward_host", sa.String(255)),
        sa.Column("forward_port", sa.Integer()),
        sa.Column("ssl_mode", sa.String(32), server_default="cloudflare"),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true()),
        sa.Column("port_reachable", sa.Boolean(), nullable=True),
        sa.Column("last_port_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("proxy_hosts")
    with op.batch_alter_table("dns_records") as batch_op:
        batch_op.drop_column("app_created")
