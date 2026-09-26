from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.schemas import CommandResponse, CommandStatus
from src.exceptions import CommandError, CommandOutputError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CommandError)
    async def command_error_handler(
        _request: Request,
        exc: CommandError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=CommandResponse(
                host=exc.host,
                status=CommandStatus.ERROR,
                error=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(CommandOutputError)
    async def command_output_error_handler(
        _request: Request,
        exc: CommandOutputError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=CommandResponse(
                host=exc.host,
                status=CommandStatus.ERROR,
                error=str(exc),
            ).model_dump(),
        )