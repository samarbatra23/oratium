"""add secrets_encrypted column to tenants

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28

Adds a nullable Fernet ciphertext column for per-tenant secrets. The
plaintext shape is :class:`oratium.tenant.TenantSecrets`; the store
encrypts on write and decrypts on read. SQLite users on a fresh dev DB
get this automatically via ``Base.metadata.create_all``; Postgres users
run ``alembic upgrade head``.

Existing dev SQLite files from Phase 2 won't have this column. It's
dev — delete the file and let ``initialize()`` recreate it. Phase 4+
production schemas should always run through Alembic.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("secrets_encrypted", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "secrets_encrypted")
