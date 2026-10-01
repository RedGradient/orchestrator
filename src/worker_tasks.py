import asyncio

from src.celery_app import celery_app
from src.models import OperationTaskStatus
from src.services.operations import claim_operation_task, complete_operation_task
from src.services.task_executor import execute_operation_task_action
from src.session import SessionLocal, engine


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
    finally:
        await engine.dispose()
