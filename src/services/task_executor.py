import asyncio
import json
from pathlib import Path
from typing import Any

import asyncssh
from pydantic import BaseModel, HttpUrl

from src.models import Host, OperationTask
from src.schemas import Command
from src.services.backup import postgres_dump
from src.services.checker import make_checks
from src.services.docker import docker_cleanup
from src.services.logs import logs_cleanup
from src.services.overlay2 import analyze_overlay2
from src.services.ports import check_ports
from src.services.swap import try_create_swap
from src.settings import settings


async def execute_operation_task_action(task: OperationTask) -> dict[str, Any]:
    """Выполняет действие задачи и подготавливает результат для хранения в JSONB."""

    result = await dispatch_action(
        command=task.command,
        host=task.host,
        parameters=task.parameters,
    )
    return serialize_action_result(result)


async def dispatch_action(
    *,
    command: str,
    host: Host,
    parameters: dict[str, Any] | None = None,
) -> BaseModel | dict[str, Any]:
    """Маршрутизирует действие и открывает SSH только для SSH-действий."""

    async with asyncio.timeout(settings.ssh_action_timeout_seconds):
        match Command(command):
            case Command.SITE_CHECK:
                if not host.site_url:
                    raise ValueError(f"Host {host.id} does not have a site URL")
                return await make_checks(HttpUrl(host.site_url))
            case _:
                async with asyncssh.connect(
                    str(host.ip),
                    username=host.username,
                    password=host.password,
                    known_hosts=None,
                    connect_timeout=settings.ssh_connection_timeout_seconds,
                ) as conn:
                    return await dispatch_ssh_action(
                        conn,
                        command=command,
                        host=host,
                        parameters=parameters,
                    )


async def dispatch_ssh_action(
    conn: asyncssh.SSHClientConnection,
    *,
    command: str,
    host: Host,
    parameters: dict[str, Any] | None = None,
) -> BaseModel | dict[str, Any]:
    """Выполняет действие, которому требуется SSH-соединение с хостом."""

    del parameters  # Зарезервировано для действий с параметрами в будущих версиях API.

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
        case Command.SITE_CHECK:
            raise ValueError("Site check must be executed without an SSH connection")
        case Command.OVERLAY2_ANALYZE:
            return await analyze_overlay2(conn)
        case Command.OVERLAY2_CLEANUP:
            raise NotImplementedError(f"Action {command} is not implemented yet")


def serialize_action_result(result: BaseModel | dict[str, Any]) -> dict[str, Any]:
    """Преобразует типизированный результат действия в JSONB-совместимый словарь."""

    payload = result.model_dump(mode="json") if isinstance(result, BaseModel) else result
    try:
        return json.loads(json.dumps(payload))
    except (TypeError, ValueError) as exc:
        raise ValueError("Action result is not JSON serializable") from exc
