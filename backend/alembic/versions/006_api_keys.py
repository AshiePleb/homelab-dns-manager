"""api keys for external integrations

Revision ID: 006
Revises: 005
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False, index=True),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("max_dns_records", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("max_services", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    with op.batch_alter_table("dns_records") as batch_op:
        batch_op.add_column(sa.Column("api_key_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_dns_records_api_key_id", "api_keys", ["api_key_id"], ["id"])
        batch_op.create_index("ix_dns_records_api_key_id", ["api_key_id"])

    with op.batch_alter_table("proxy_hosts") as batch_op:
        batch_op.add_column(sa.Column("api_key_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_proxy_hosts_api_key_id", "api_keys", ["api_key_id"], ["id"])
        batch_op.create_index("ix_proxy_hosts_api_key_id", ["api_key_id"])


def downgrade() -> None:
    with op.batch_alter_table("proxy_hosts") as batch_op:
        batch_op.drop_index("ix_proxy_hosts_api_key_id")
        batch_op.drop_constraint("fk_proxy_hosts_api_key_id", type_="foreignkey")
        batch_op.drop_column("api_key_id")

    with op.batch_alter_table("dns_records") as batch_op:
        batch_op.drop_index("ix_dns_records_api_key_id")
        batch_op.drop_constraint("fk_dns_records_api_key_id", type_="foreignkey")
        batch_op.drop_column("api_key_id")

    op.drop_table("api_keys")
