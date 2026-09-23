from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.schemas import CheckRequest, CheckResponse
from src.services import make_checks

app = FastAPI()






@app.post("/api/check")
async def check(request: CheckRequest) -> CheckResponse:
    return await make_checks(request)


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True),
    name="frontend",
)