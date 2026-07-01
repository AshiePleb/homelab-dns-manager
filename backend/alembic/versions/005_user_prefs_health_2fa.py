"""user preferences, 2FA, health history

Revision ID: 005
Revises: 004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("preferences", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("totp_secret", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("totp_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))

    op.create_table(
        "health_check_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hostname", sa.String(255), nullable=False, index=True),
        sa.Column("overall", sa.String(32), nullable=False),
        sa.Column("dns_ok", sa.Boolean(), nullable=False),
        sa.Column("port_ok", sa.Boolean(), nullable=False),
        sa.Column("https_ok", sa.Boolean(), nullable=False),
        sa.Column("ssl_days_remaining", sa.Integer(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("health_check_history")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("totp_enabled")
        batch_op.drop_column("totp_secret")
        batch_op.drop_column("preferences")
