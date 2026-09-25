from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas import RegisterHostRequest, RegisterHostResponse
from src.services.host import create_host
from src.schemas import CommandRequest, CommandResponse
from src.services.checker import make_checks, list_checks
from src.services.docker import try_run_command
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
async def create_job(
    request: CommandRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CommandResponse:
    return await try_run_command(session, request)


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
