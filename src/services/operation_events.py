import json
from collections.abc import AsyncIterator

from fastapi import Request
from redis import asyncio as redis_async

from src.models import Operation, OperationStatus, OperationTask
from src.schemas import OperationEvent
from src.settings import settings


def operation_channel(operation_id: int) -> str:
    """Возвращает Redis Pub/Sub channel для одной Operation."""

    return f"operations:{operation_id}"


async def publish_operation_event(event: OperationEvent) -> None:
    """Публикует уже сохранённое в PostgreSQL изменение состояния Operation."""

    redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.publish(operation_channel(event.operation_id), event.model_dump_json())
    finally:
        await redis.aclose()


async def publish_task_updated(task: OperationTask, operation: Operation) -> None:
    """Публикует изменение одной Task после её сохранения в PostgreSQL."""

    await publish_operation_event(
        OperationEvent(
            event="task.updated",
            operation_id=operation.id,
            operation_status=operation.status,
            task_id=task.id,
            task_status=task.status,
        )
    )


async def publish_operation_updated(operation: Operation) -> None:
    """Публикует aggregate state Operation, включая её terminal-состояние."""

    event_name = (
        "operation.completed"
        if operation.status
        in {
            OperationStatus.SUCCEEDED,
            OperationStatus.FAILED,
            OperationStatus.PARTIAL_FAILURE,
            OperationStatus.CANCELLED,
        }
        else "operation.updated"
    )
    await publish_operation_event(
        OperationEvent(
            event=event_name,
            operation_id=operation.id,
            operation_status=operation.status,
        )
    )


async def stream_operation_events(
    request: Request,
    operation_id: int,
) -> AsyncIterator[str]:
    """Подписывает один SSE-клиент на Redis-события указанной Operation."""

    redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(operation_channel(operation_id))
    try:
        yield "retry: 3000\n\n"
        while not await request.is_disconnected():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                yield ": keepalive\n\n"
                continue

            event = OperationEvent.model_validate(json.loads(message["data"]))
            yield f"event: {event.event}\ndata: {event.model_dump_json()}\n\n"
    finally:
        await pubsub.unsubscribe(operation_channel(operation_id))
        await pubsub.aclose()
        await redis.aclose()
