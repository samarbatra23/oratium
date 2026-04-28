"""create tenants table

Revision ID: 0001
Revises:
Create Date: 2026-04-28

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("twilio_number", sa.String(length=20), nullable=False),
        sa.Column("agent_config", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_tenants_twilio_number",
        "tenants",
        ["twilio_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_tenants_twilio_number", table_name="tenants")
    op.drop_table("tenants")
