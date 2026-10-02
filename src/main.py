import logging
import os
from pathlib import Path
from typing import Annotated, Any

import asyncssh
from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from src.exc_handlers import register_exception_handlers
from src.models import OperationStatus
from src.schemas import (
    CheckHistoryItem,
    CheckRequest,
    CheckResponse,
    Command,
    CommandRequest,
    CommandResponse,
    CommandStatus,
    CreateOperationRequest,
    HostItem,
    OperationAccepted,
    OperationItem,
    RegisterHostRequest,
    RegisterHostResponse,
    UpdateHostRequest,
)
from src.services.backup import postgres_dump
from src.services.checker import list_checks, make_checks
from src.services.docker import docker_cleanup
from src.services.host import create_host, delete_host, get_active_host, list_hosts, update_host
from src.services.logs import logs_cleanup
from src.services.operation_events import (
    publish_operation_updated,
    publish_task_updated,
    stream_operation_events,
)
from src.services.operations import (
    cancel_operation,
    create_operation,
    ensure_operation_exists,
    get_operation,
    operation_to_item,
    queue_operation_tasks,
)
from src.services.ports import check_ports
from src.services.swap import try_create_swap
from src.session import get_session
from src.worker_tasks import execute_vps_task

logger = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    """Раздаёт index.html для клиентских маршрутов React Router."""

    async def get_response(self, path: str, scope: dict[str, Any]) -> Response:
        response = await super().get_response(path, scope)
        is_client_route = scope["method"] == "GET" and "." not in Path(path).name
        if response.status_code == status.HTTP_404_NOT_FOUND and is_client_route:
            return await super().get_response("index.html", scope)
        return response


app = FastAPI()

register_exception_handlers(app)


@app.post("/api/check")
async def check(
    request: CheckRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CheckResponse:
    return await make_checks(request, session)


@app.get("/api/checks")
async def checks(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CheckHistoryItem]:
    return await list_checks(session)


@app.post("/api/operations", status_code=status.HTTP_202_ACCEPTED)
async def create_vps_operation(
    request: CreateOperationRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OperationAccepted:
    """Создаёт batch Operation и немедленно возвращает её идентификатор."""

    operation = await create_operation(session, request)
    task_ids = await queue_operation_tasks(session, operation.id)
    for operation_task_id in task_ids:
        try:
            execute_vps_task.delay(operation_task_id)
        except Exception:
            logger.exception(
                "Could not publish operation task %s to Celery; it remains queued",
                operation_task_id,
            )

    return OperationAccepted(operation_id=operation.id, status=OperationStatus.QUEUED)


@app.get("/api/operations/{operation_id}")
async def operation(
    operation_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OperationItem:
    """Возвращает REST source-of-truth snapshot Operation и её задач."""

    return operation_to_item(await get_operation(session, operation_id))


@app.get("/api/operations/{operation_id}/events")
async def operation_events(
    operation_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    """Передаёт изменения одной Operation через Server-Sent Events."""

    await ensure_operation_exists(session, operation_id)
    return StreamingResponse(
        stream_operation_events(request, operation_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/operations/{operation_id}/cancel")
async def cancel_vps_operation(
    operation_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OperationItem:
    """Отменяет ещё не начатые задачи и запрашивает отмену running-задач."""

    operation, changed_tasks = await cancel_operation(session, operation_id)
    if changed_tasks:
        try:
            for task in changed_tasks:
                await publish_task_updated(task, operation)
            await publish_operation_updated(operation)
        except Exception:
            logger.exception("Could not publish cancellation events for operation %s", operation_id)
    return operation_to_item(operation)


@app.post("/api/command", status_code=status.HTTP_201_CREATED)
async def run_command(
    request: CommandRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Any:
    host = await get_active_host(session, request.host_id)

    async with asyncssh.connect(
        str(host.ip),
        username=host.username,
        password=host.password,
        known_hosts=None,
    ) as conn:
        if request.command == Command.DOCKER_CLEANUP:
            result = await docker_cleanup(conn)

        elif request.command == Command.POSTGRES_BACKUP:
            local_dir = Path(os.getcwd()) / "backup"
            result = await postgres_dump(conn, str(host.ip), str(local_dir))

        elif request.command == Command.CREATE_SWAP:
            result = await try_create_swap(conn)

        elif request.command == Command.LOGS_CLEANUP:
            result = await logs_cleanup(conn)

        elif request.command == Command.PORTS:
            result = await check_ports(conn)

        else:
            raise Exception("Неизвестная команда")

        return CommandResponse(host=str(host.ip), status=CommandStatus.SUCCESS, result=result)


@app.get("/api/hosts")
async def hosts(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[HostItem]:
    return await list_hosts(session)


@app.post("/api/host", status_code=status.HTTP_201_CREATED)
async def register_host(
    request: RegisterHostRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RegisterHostResponse:
    return await create_host(session, request)


@app.patch("/api/hosts/{host_id}")
async def edit_host(
    host_id: int,
    request: UpdateHostRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HostItem:
    return await update_host(session, host_id, request)


@app.delete("/api/hosts/{host_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_host(
    host_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await delete_host(session, host_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/check.html", include_in_schema=False)
async def legacy_check_page() -> RedirectResponse:
    return RedirectResponse(url="/checks", status_code=status.HTTP_308_PERMANENT_REDIRECT)


@app.get("/action.html", include_in_schema=False)
async def legacy_action_page() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=status.HTTP_308_PERMANENT_REDIRECT)


app.mount(
    "/",
    SPAStaticFiles(
        directory=Path(__file__).resolve().parent.parent / "frontend" / "dist",
        html=True,
        check_dir=False,
    ),
    name="frontend",
)
