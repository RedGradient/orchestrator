from datetime import UTC, datetime

import pytest

from src.models import Host, Operation, OperationStatus, OperationTask, OperationTaskStatus
from src.schemas import Command, CreateOperationRequest, OperationActionRequest
from src.services.operations import create_operation, operation_to_item


class ScalarResult:
    """Минимальная замена результату `AsyncSession.scalars()` для unit-теста."""

    def __init__(self, values: list[Host]) -> None:
        self._values = values

    def all(self) -> list[Host]:
        return self._values


class FakeSession:
    """In-memory имитация только нужных сервису операций SQLAlchemy-сессии."""

    def __init__(self, hosts: list[Host]) -> None:
        self.hosts = hosts
        self.added: list[object] = []
        self.committed = False

    async def scalars(self, _statement: object) -> ScalarResult:
        return ScalarResult(self.hosts)

    def add(self, item: object) -> None:
        self.added.append(item)

    def add_all(self, items: list[object]) -> None:
        self.added.extend(items)

    async def commit(self) -> None:
        self.committed = True


def make_host(host_id: int) -> Host:
    """Создаёт хост с данными, достаточными для тестов операций."""

    return Host(
        id=host_id,
        ip=f"192.0.2.{host_id}",
        username="root",
        password="secret",
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_create_operation_creates_task_for_each_host_and_action() -> None:
    """Создание batch Operation порождает одну pending-задачу на пару host × action."""

    session = FakeSession([make_host(1), make_host(2)])
    request = CreateOperationRequest(
        host_ids=[1, 2],
        actions=[
            OperationActionRequest(command=Command.PORTS),
            OperationActionRequest(command=Command.LOGS_CLEANUP),
        ],
    )

    operation = await create_operation(session, request)  # type: ignore[arg-type]

    tasks = [item for item in session.added if isinstance(item, OperationTask)]
    assert operation.status == OperationStatus.PENDING
    assert len(tasks) == 4
    assert {(task.host_id, task.command) for task in tasks} == {
        (1, "ports"),
        (1, "logs_cleanup"),
        (2, "ports"),
        (2, "logs_cleanup"),
    }
    assert all(task.status == OperationTaskStatus.PENDING for task in tasks)
    assert session.committed is True


def test_operation_snapshot_uses_task_statuses_for_progress() -> None:
    """REST snapshot получает счётчики progress из статусов дочерних задач."""

    host = make_host(1)
    now = datetime.now(UTC)
    operation = Operation(
        id=11,
        status=OperationStatus.RUNNING,
        created_at=now,
        tasks=[
            OperationTask(
                id=1,
                host=host,
                command="ports",
                parameters={},
                status=OperationTaskStatus.SUCCEEDED,
                created_at=now,
            ),
            OperationTask(
                id=2,
                host=host,
                command="logs_cleanup",
                parameters={},
                status=OperationTaskStatus.RUNNING,
                created_at=now,
            ),
        ],
    )

    snapshot = operation_to_item(operation)

    assert snapshot.progress.total == 2
    assert snapshot.progress.succeeded == 1
    assert snapshot.progress.running == 1
    assert snapshot.progress.failed == 0
