import asyncio
import logging

from src.celery_app import celery_app
from src.models import Operation, OperationTask, OperationTaskStatus
from src.services.operation_events import publish_operation_updated, publish_task_updated
from src.services.operations import claim_operation_task, complete_operation_task
from src.services.task_executor import execute_operation_task_action
from src.session import SessionLocal, engine

logger = logging.getLogger(__name__)


@celery_app.task(name="orchestrator.execute_vps_task", ignore_result=True)
def execute_vps_task(operation_task_id: int) -> None:
    """Celery entry point: запускает выполнение операции по её task_id."""

    asyncio.run(run_operation_task(operation_task_id))


async def run_operation_task(operation_task_id: int) -> None:
    """Выполняет задачу операции и фиксирует результат её выполнения."""

    try:
        async with SessionLocal() as session:
            task = await claim_operation_task(session, operation_task_id)
            if task is None:
                return
            await publish_task_state(session, task)

            try:
                result = await execute_operation_task_action(task)
            except TimeoutError:
                await complete_operation_task(
                    session,
                    operation_task_id,
                    status=OperationTaskStatus.TIMEOUT,
                    error="SSH action timed out",
                )
            except Exception as exc:
                await complete_operation_task(
                    session,
                    operation_task_id,
                    status=OperationTaskStatus.FAILED,
                    error=str(exc),
                )
            else:
                await complete_operation_task(
                    session,
                    operation_task_id,
                    status=OperationTaskStatus.SUCCEEDED,
                    result=result,
                )
            await publish_task_state(session, task)
    finally:
        await engine.dispose()


async def publish_task_state(session, task: OperationTask) -> None:
    """Публикует task и aggregate Operation state после успешного DB commit."""

    operation = await session.get(Operation, task.operation_id)
    assert operation is not None
    try:
        await publish_task_updated(task, operation)
        await publish_operation_updated(operation)
    except Exception:
        logger.exception("Could not publish state event for operation task %s", task.id)
