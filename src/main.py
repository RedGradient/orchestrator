import os
from pathlib import Path
from typing import Annotated, Any

import asyncssh
from fastapi import Depends, FastAPI, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from src.exc_handlers import register_exception_handlers
from src.models import Host
from src.schemas import (
    RegisterHostRequest,
    RegisterHostResponse,
    HostItem,
    Command,
    CommandRequest,
    CommandResponse,
    CommandStatus,
    CheckHistoryItem,
    CheckRequest,
    CheckResponse
)
from src.services.backup import postgres_dump
from src.services.checker import make_checks, list_checks
from src.services.docker import docker_cleanup
from src.services.host import create_host, list_hosts
from src.services.swap import try_create_swap
from src.session import get_session

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


@app.post("/api/command", status_code=status.HTTP_201_CREATED)
async def run_command(
    request: CommandRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Any:
    if (host := await session.get(Host, request.host_id)) is None:
        raise Exception(f"Нет зарегистрированного хоста с id {request.host_id}")

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

        else:
            raise Exception("Неизвестная команда")

        return CommandResponse(
            host=str(host.ip),
            status=CommandStatus.SUCCESS,
            result=result
        )


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


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True),
    name="frontend",
)
