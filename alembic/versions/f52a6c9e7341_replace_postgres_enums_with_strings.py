"""replace postgres enums with strings

Revision ID: f52a6c9e7341
Revises: d49f181553b2
Create Date: 2026-10-01 18:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f52a6c9e7341"
down_revision: str | Sequence[str] | None = "d49f181553b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE checks ALTER COLUMN trigger TYPE VARCHAR(16) USING trigger::text")
    op.execute("ALTER TABLE operations ALTER COLUMN status TYPE VARCHAR(32) USING status::text")
    op.execute(
        "ALTER TABLE operation_tasks ALTER COLUMN status TYPE VARCHAR(32) USING status::text"
    )
    op.execute("DROP TYPE check_trigger")
    op.execute("DROP TYPE operation_status")
    op.execute("DROP TYPE operation_task_status")


def downgrade() -> None:
    check_trigger = sa.Enum("manual", "automatic", name="check_trigger")
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
    bind = op.get_bind()
    check_trigger.create(bind)
    operation_status.create(bind)
    operation_task_status.create(bind)

    op.execute(
        "ALTER TABLE checks ALTER COLUMN trigger TYPE check_trigger "
        + "USING trigger::check_trigger"
    )
    op.execute(
        "ALTER TABLE operations ALTER COLUMN status TYPE operation_status "
        + "USING status::operation_status"
    )
    op.execute(
        "ALTER TABLE operation_tasks ALTER COLUMN status TYPE operation_task_status "
        "USING status::operation_task_status"
    )
