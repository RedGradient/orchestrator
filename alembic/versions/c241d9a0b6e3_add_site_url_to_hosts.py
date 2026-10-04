"""add site url to hosts

Revision ID: c241d9a0b6e3
Revises: 8d4a2f91c7e3
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c241d9a0b6e3"
down_revision: str | Sequence[str] | None = "8d4a2f91c7e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hosts", sa.Column("site_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("hosts", "site_url")
