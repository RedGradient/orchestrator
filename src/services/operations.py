from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import HostsNotFoundError, OperationNotFoundError
from src.models import Host, Operation, OperationStatus, OperationTask, OperationTaskStatus
from src.schemas import (
    CreateOperationRequest,
    HostItem,
    OperationItem,
    OperationProgress,
    OperationTaskItem,
)


async def create_operation(
    session: AsyncSession,
    request: CreateOperationRequest,
) -> Operation:
    """Создаёт Operation и её pending-задачи в одной БД-транзакции."""

    hosts = (await session.scalars(select(Host).where(Host.id.in_(request.host_ids)))).all()
    hosts_by_id = {host.id: host for host in hosts}
    missing_host_ids = [host_id for host_id in request.host_ids if host_id not in hosts_by_id]
    if missing_host_ids:
        raise HostsNotFoundError(missing_host_ids)

    operation = Operation(status=OperationStatus.PENDING)
    session.add(operation)

    tasks = [
        OperationTask(
            operation=operation,
            host=hosts_by_id[host_id],
            host_id=host_id,
            command=action.command.value,
            parameters=dict(action.parameters),
            status=OperationTaskStatus.PENDING,
        )
        for host_id in request.host_ids
        for action in request.actions
    ]
    session.add_all(tasks)
    await session.commit()
    return operation


async def get_operation(session: AsyncSession, operation_id: int) -> Operation:
    """Возвращает Operation с задачами и хостами, нужными для API snapshot."""

    statement = (
        select(Operation)
        .where(Operation.id == operation_id)
        .options(selectinload(Operation.tasks).selectinload(OperationTask.host))
    )
    operation = await session.scalar(statement)
    if operation is None:
        raise OperationNotFoundError(operation_id)
    return operation


def operation_to_item(operation: Operation) -> OperationItem:
    """Преобразует загруженную Operation в REST source-of-truth snapshot."""

    tasks = [
        OperationTaskItem(
            id=task.id,
            host=HostItem.model_validate(task.host),
            command=task.command,
            parameters=task.parameters,
            status=task.status,
            result=task.result,
            error=task.error,
            created_at=task.created_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
        )
        for task in operation.tasks
    ]
    return OperationItem(
        id=operation.id,
        status=operation.status,
        progress=operation_progress(operation.tasks),
        created_at=operation.created_at,
        started_at=operation.started_at,
        finished_at=operation.finished_at,
        tasks=tasks,
    )


def operation_progress(tasks: list[OperationTask]) -> OperationProgress:
    """Считает прогресс из Task-статусов, не создавая второй источник истины."""

    counts = Counter(task.status.value for task in tasks)
    return OperationProgress(
        total=len(tasks),
        pending=counts[OperationTaskStatus.PENDING.value],
        queued=counts[OperationTaskStatus.QUEUED.value],
        running=counts[OperationTaskStatus.RUNNING.value],
        succeeded=counts[OperationTaskStatus.SUCCEEDED.value],
        failed=counts[OperationTaskStatus.FAILED.value],
        timeout=counts[OperationTaskStatus.TIMEOUT.value],
        cancellation_requested=counts[OperationTaskStatus.CANCELLATION_REQUESTED.value],
        cancelled=counts[OperationTaskStatus.CANCELLED.value],
    )
