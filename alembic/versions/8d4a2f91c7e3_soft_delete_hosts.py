"""soft delete hosts

Revision ID: 8d4a2f91c7e3
Revises: b3f87d42c6a1
Create Date: 2026-10-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "8d4a2f91c7e3"
down_revision: str | Sequence[str] | None = "b3f87d42c6a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("hosts", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_index("ix_hosts_ip", table_name="hosts")
    op.create_index(
        "ix_hosts_ip",
        "hosts",
        ["ip"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM hosts WHERE deleted_at IS NOT NULL"))
    op.drop_index("ix_hosts_ip", table_name="hosts")
    op.create_index("ix_hosts_ip", "hosts", ["ip"], unique=True)
    op.drop_column("hosts", "deleted_at")
