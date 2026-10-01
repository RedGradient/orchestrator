"""create operations and operation tasks

Revision ID: d49f181553b2
Revises: ac78f4283d89
Create Date: 2026-10-01 17:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d49f181553b2"
down_revision: Union[str, Sequence[str], None] = "ac78f4283d89"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

operation_status = sa.Enum(
    "pending",
    "queued",
    "running",
    "succeeded",
    "failed",
    "partial_failure",
    "cancelled",
    name="operation_status",
)
operation_task_status = sa.Enum(
    "pending",
    "queued",
    "running",
    "succeeded",
    "failed",
    "timeout",
    "cancellation_requested",
    "cancelled",
    name="operation_task_status",
)


def upgrade() -> None:
    operation_status.create(op.get_bind(), checkfirst=True)
    operation_task_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "operations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", operation_status, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "operation_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("operation_id", sa.Integer(), nullable=False),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("command", sa.String(length=64), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", operation_task_status, nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"]),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operation_tasks_operation_id_status",
        "operation_tasks",
        ["operation_id", "status"],
        unique=False,
    )
    op.create_index("ix_operation_tasks_status", "operation_tasks", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_operation_tasks_status", table_name="operation_tasks")
    op.drop_index("ix_operation_tasks_operation_id_status", table_name="operation_tasks")
    op.drop_table("operation_tasks")
    op.drop_table("operations")
    operation_task_status.drop(op.get_bind(), checkfirst=True)
    operation_status.drop(op.get_bind(), checkfirst=True)
