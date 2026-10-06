import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest_asyncio
from pytest import TempPathFactory

from tests.conftest import _docker

SITE_CHECK_IMAGE = "orchestrator-site-check-it"
SITE_CHECK_DIR = Path(__file__).resolve().parents[1] / "site_check"
SITE_CHECK_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class SiteCheckServer:
    """Данные локального HTTPS-сервера для интеграционных тестов Site Check."""

    url: str
    domain: str
    ca_certificate: Path


async def _wait_site_check_server() -> None:
    """Ожидает готовности HTTP-сервера тестового сайта."""

    deadline = time.monotonic() + SITE_CHECK_TIMEOUT_SECONDS
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get("http://127.0.0.1/")
                if response.status_code == 200:
                    return
            except httpx.RequestError as exc:
                last_error = exc
            await asyncio.sleep(0.2)

    raise TimeoutError(
        f"Тестовый сайт не ответил за {SITE_CHECK_TIMEOUT_SECONDS} секунд: {last_error}"
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def site_check_server(tmp_path_factory: TempPathFactory) -> AsyncIterator[SiteCheckServer]:
    """Запускает локальный HTTP/HTTPS-сайт с тестовым CA и удаляет его после тестов."""

    container_name = f"orchestrator-site-check-it-{uuid.uuid4().hex[:8]}"
    certificates_dir = tmp_path_factory.mktemp("site-check-certificates")
    ca_certificate = certificates_dir / "ca.crt"
    started = False

    try:
        await _docker("build", "-t", SITE_CHECK_IMAGE, str(SITE_CHECK_DIR))
        await _docker(
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            "127.0.0.1:80:80",
            "-p",
            "127.0.0.1:443:443",
            SITE_CHECK_IMAGE,
        )
        started = True
        await _wait_site_check_server()
        await _docker(
            "cp",
            f"{container_name}:/etc/nginx/test-certs/ca.crt",
            str(ca_certificate),
        )
        yield SiteCheckServer(
            url="https://127.0.0.1",
            domain="127.0.0.1",
            ca_certificate=ca_certificate,
        )
    finally:
        if started:
            await _docker("rm", "-f", container_name)
