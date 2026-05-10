"""app_settings table

Revision ID: 0002_app_settings
Revises: 0001_initial
Create Date: 2026-05-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_app_settings"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "key", name="uniq_app_settings_user_key"),
    )
    op.create_index("ix_app_settings_user_id", "app_settings", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_app_settings_user_id", table_name="app_settings")
    op.drop_table("app_settings")
