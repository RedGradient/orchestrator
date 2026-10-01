import asyncio
import json
from pathlib import Path
from typing import Any

import asyncssh
from pydantic import BaseModel

from src.models import Host, OperationTask
from src.schemas import Command
from src.services.backup import postgres_dump
from src.services.docker import docker_cleanup
from src.services.logs import logs_cleanup
from src.services.ports import check_ports
from src.services.swap import try_create_swap
from src.settings import settings


async def execute_operation_task_action(task: OperationTask) -> dict[str, Any]:
    """Открывает SSH-соединение и выполняет одно логическое действие задачи."""

    async with asyncio.timeout(settings.ssh_action_timeout_seconds):
        async with asyncssh.connect(
            str(task.host.ip),
            username=task.host.username,
            password=task.host.password,
            known_hosts=None,
            connect_timeout=settings.ssh_connection_timeout_seconds,
        ) as conn:
            result = await dispatch_action(
                conn,
                command=task.command,
                host=task.host,
                parameters=task.parameters,
            )
    return serialize_action_result(result)


async def dispatch_action(
    conn: asyncssh.SSHClientConnection,
    *,
    command: str,
    host: Host,
) -> BaseModel | dict[str, Any]:
    """Выбирает существующее async-действие без привязки к FastAPI или Celery."""

    match Command(command):
        case Command.DOCKER_CLEANUP:
            return await docker_cleanup(conn)
        case Command.POSTGRES_BACKUP:
            return await postgres_dump(conn, str(host.ip), str(Path.cwd() / "backup"))
        case Command.CREATE_SWAP:
            return await try_create_swap(conn)
        case Command.LOGS_CLEANUP:
            return await logs_cleanup(conn)
        case Command.PORTS:
            return await check_ports(conn)


def serialize_action_result(result: BaseModel | dict[str, Any]) -> dict[str, Any]:
    """Преобразует типизированный результат действия в JSONB-совместимый словарь."""

    payload = result.model_dump(mode="json") if isinstance(result, BaseModel) else result
    try:
        return json.loads(json.dumps(payload))
    except (TypeError, ValueError) as exc:
        raise ValueError("Action result is not JSON serializable") from exc
