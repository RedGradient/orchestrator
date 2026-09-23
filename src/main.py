from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from src.schemas import CheckHistoryItem, CheckRequest, CheckResponse
from src.services import list_checks, make_checks
from src.session import get_session

app = FastAPI()



@app.post("/api/check")
async def check(
    request: CheckRequest,
    session: Annotated[Session, Depends(get_session)],
) -> CheckResponse:
    return await make_checks(request, session)


@app.get("/api/checks")
def checks(session: Annotated[Session, Depends(get_session)]) -> list[CheckHistoryItem]:
    return list_checks(session)


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True),
    name="frontend",
)