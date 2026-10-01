from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.exceptions import (
    HostsNotFoundError,
    OperationNotFoundError,
    UnsupportedOperationParametersError,
)
from src.models import Host, Operation, OperationStatus, OperationTask, OperationTaskStatus
from src.schemas import (
    Command,
    CreateOperationRequest,
    HostItem,
    OperationActionRequest,
    OperationItem,
    OperationProgress,
    OperationTaskItem,
)


async def create_operation(
    session: AsyncSession,
    request: CreateOperationRequest,
) -> Operation:
    """Создаёт Operation и её pending-задачи в одной БД-транзакции."""

    validate_action_parameters(request.actions)
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


async def queue_operation_tasks(session: AsyncSession, operation_id: int) -> list[int]:
    """Переводит pending-задачи Operation в queued и возвращает их ID для Celery."""

    task_ids = (
        await session.scalars(
            update(OperationTask)
            .where(
                OperationTask.operation_id == operation_id,
                OperationTask.status == OperationTaskStatus.PENDING,
            )
            .values(status=OperationTaskStatus.QUEUED)
            .returning(OperationTask.id)
        )
    ).all()
    if not task_ids:
        return []

    await session.execute(
        update(Operation).where(Operation.id == operation_id).values(status=OperationStatus.QUEUED)
    )
    await session.commit()
    return task_ids


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


async def claim_operation_task(
    session: AsyncSession,
    operation_task_id: int,
) -> OperationTask | None:
    """Атомарно переводит queued-задачу в running для одного Celery worker."""

    started_at = datetime.now(UTC)
    claimed_task_id = await session.scalar(
        update(OperationTask)
        .where(
            OperationTask.id == operation_task_id,
            OperationTask.status == OperationTaskStatus.QUEUED,
        )
        .values(status=OperationTaskStatus.RUNNING, started_at=started_at)
        .returning(OperationTask.id)
    )
    if claimed_task_id is None:
        return None

    task = await session.scalar(
        select(OperationTask)
        .where(OperationTask.id == claimed_task_id)
        .options(selectinload(OperationTask.host))
    )
    assert task is not None
    await _refresh_operation_status(session, task.operation_id)
    await session.commit()
    return task


async def complete_operation_task(
    session: AsyncSession,
    operation_task_id: int,
    *,
    status: OperationTaskStatus,
    result: dict[str, object] | None = None,
    error: str | None = None,
) -> bool:
    """Завершает запущенную задачу и обновляет агрегированный статус Operation."""

    if status not in {
        OperationTaskStatus.SUCCEEDED,
        OperationTaskStatus.FAILED,
        OperationTaskStatus.TIMEOUT,
    }:
        raise ValueError(f"{status.value} is not a completion status")

    task = await session.get(OperationTask, operation_task_id)
    if task is None:
        return False

    if task.status not in {
        OperationTaskStatus.RUNNING,
        OperationTaskStatus.CANCELLATION_REQUESTED,
    }:
        return False

    task.status = status
    task.result = result
    task.error = error
    task.finished_at = datetime.now(UTC)
    await _refresh_operation_status(session, task.operation_id)
    await session.commit()
    return True


def operation_to_item(operation: Operation) -> OperationItem:
    """Преобразует загруженную Operation в REST source-of-truth snapshot."""

    tasks = [
        OperationTaskItem(
            id=task.id,
            host=HostItem.model_validate(task.host),
            command=Command(task.command),
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


async def _refresh_operation_status(session: AsyncSession, operation_id: int) -> None:
    operation = await session.scalar(
        select(Operation).where(Operation.id == operation_id).options(selectinload(Operation.tasks))
    )
    assert operation is not None

    status = derive_operation_status([task.status for task in operation.tasks])
    operation.status = status
    now = datetime.now(UTC)
    if status == OperationStatus.RUNNING and operation.started_at is None:
        operation.started_at = now
    if status in {
        OperationStatus.SUCCEEDED,
        OperationStatus.FAILED,
        OperationStatus.PARTIAL_FAILURE,
        OperationStatus.CANCELLED,
    }:
        operation.finished_at = now


def derive_operation_status(task_statuses: list[OperationTaskStatus]) -> OperationStatus:
    """Вычисляет агрегированный статус без отдельного источника истины progress."""

    statuses = set(task_statuses)
    if not statuses or OperationTaskStatus.PENDING in statuses:
        return OperationStatus.PENDING
    if OperationTaskStatus.QUEUED in statuses:
        return OperationStatus.QUEUED
    if {
        OperationTaskStatus.RUNNING,
        OperationTaskStatus.CANCELLATION_REQUESTED,
    } & statuses:
        return OperationStatus.RUNNING
    if statuses == {OperationTaskStatus.SUCCEEDED}:
        return OperationStatus.SUCCEEDED
    if statuses == {OperationTaskStatus.CANCELLED}:
        return OperationStatus.CANCELLED
    if statuses <= {OperationTaskStatus.FAILED, OperationTaskStatus.TIMEOUT}:
        return OperationStatus.FAILED
    return OperationStatus.PARTIAL_FAILURE


def validate_action_parameters(actions: list[OperationActionRequest]) -> None:
    """Не допускает постановку задач с параметрами, не поддержанными actions."""

    for action in actions:
        if action.parameters:
            raise UnsupportedOperationParametersError(action.command.value)
