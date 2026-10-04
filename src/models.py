from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class OperationStatus(StrEnum):
    """Состояние пользовательского запуска."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL_FAILURE = "partial_failure"
    CANCELLED = "cancelled"


class OperationTaskStatus(StrEnum):
    """Состояние одного действия на одном удалённом хосте."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLED = "cancelled"


class Host(Base):
    """Удалённый хост для SSH-подключения."""

    __tablename__ = "hosts"
    __table_args__ = (
        Index(
            "ix_hosts_ip",
            "ip",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    label: Mapped[str | None] = mapped_column(String(255))
    site_url: Mapped[str | None] = mapped_column(String(2048))
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    operation_tasks: Mapped[list[OperationTask]] = relationship(back_populates="host")


class Operation(Base):
    """Один пользовательский запуск, объединяющий несколько действий на VPS."""

    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[OperationStatus] = mapped_column(
        Enum(
            OperationStatus,
            name="operation_status",
            native_enum=False,
            length=32,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tasks: Mapped[list[OperationTask]] = relationship(
        back_populates="operation",
        cascade="all, delete-orphan",
        order_by="OperationTask.created_at",
    )


class OperationTask(Base):
    """Выполнение одного логического действия на одном удалённом хосте."""

    __tablename__ = "operation_tasks"
    __table_args__ = (
        Index("ix_operation_tasks_operation_id_status", "operation_id", "status"),
        Index("ix_operation_tasks_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    operation_id: Mapped[int] = mapped_column(ForeignKey("operations.id"), nullable=False)
    host_id: Mapped[int] = mapped_column(ForeignKey("hosts.id"), nullable=False)
    command: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[OperationTaskStatus] = mapped_column(
        Enum(
            OperationTaskStatus,
            name="operation_task_status",
            native_enum=False,
            length=32,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    operation: Mapped[Operation] = relationship(back_populates="tasks")
    host: Mapped[Host] = relationship(back_populates="operation_tasks")
