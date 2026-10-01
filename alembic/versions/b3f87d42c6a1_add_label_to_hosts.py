"""add label to hosts

Revision ID: b3f87d42c6a1
Revises: f52a6c9e7341
Create Date: 2026-10-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b3f87d42c6a1"
down_revision: str | Sequence[str] | None = "f52a6c9e7341"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hosts", sa.Column("label", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("hosts", "label")
