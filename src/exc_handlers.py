from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.exceptions import (
    CommandError,
    CommandOutputError,
    HostIpAlreadyExistsError,
    HostNotFoundError,
    HostsNotFoundError,
    HostsWithoutSiteUrlError,
    OperationNotFoundError,
    UnsupportedOperationParametersError,
)
from src.schemas import CommandResponse, CommandStatus


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

    @app.exception_handler(HostNotFoundError)
    async def host_not_found_handler(
        _request: Request,
        exc: HostNotFoundError,
    ):
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )

    @app.exception_handler(HostIpAlreadyExistsError)
    async def host_ip_already_exists_handler(
        _request: Request,
        exc: HostIpAlreadyExistsError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc), "ip": exc.ip},
        )

    @app.exception_handler(HostsNotFoundError)
    async def hosts_not_found_handler(
        _request: Request,
        exc: HostsNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc), "host_ids": exc.host_ids},
        )

    @app.exception_handler(OperationNotFoundError)
    async def operation_not_found_handler(
        _request: Request,
        exc: OperationNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )

    @app.exception_handler(HostsWithoutSiteUrlError)
    async def hosts_without_site_url_handler(
        _request: Request,
        exc: HostsWithoutSiteUrlError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "host_ids": exc.host_ids},
        )

    @app.exception_handler(UnsupportedOperationParametersError)
    async def unsupported_operation_parameters_handler(
        _request: Request,
        exc: UnsupportedOperationParametersError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "command": exc.command},
        )
