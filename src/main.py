import os
from ipaddress import IPv4Address
from pathlib import Path
from typing import Annotated

import asyncssh
from fastapi import Depends, FastAPI, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Host
from src.services.backup import postgres_dump
from src.services.docker import docker_cleanup
from src.schemas import RegisterHostRequest, RegisterHostResponse, HostItem, Command
from src.services.host import create_host, list_hosts
from src.schemas import CommandRequest, CommandResponse
from src.services.checker import make_checks, list_checks
from src.schemas import CheckHistoryItem, CheckRequest, CheckResponse
from src.session import get_session

app = FastAPI()


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
) -> CommandResponse:
    if (host := await session.get(Host, request.host_id)) is None:
        raise Exception(f"Нет зарегистрированного хоста с id {request.host_id}")

    async with asyncssh.connect(
            str(host.ip),
            username=host.username,
            password=host.password,
            known_hosts=None,
    ) as conn:
        if request.command == Command.DOCKER_CLEANUP:
            return await docker_cleanup(conn, IPv4Address(host.ip))

        if request.command == Command.POSTGRES_BACKUP:
            local_dir = Path(os.getcwd()) / "backup"
            return await postgres_dump(conn, str(host.ip), str(local_dir))

        raise Exception("Неизвестная команда")


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
