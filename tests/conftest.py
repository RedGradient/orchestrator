import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import asyncssh
import pytest_asyncio
from asyncssh import SSHClientConnection

from src.services.helpers.ssh import run_command

IMAGE = "orchestrator-logs-it"
SSH_USER = "testuser"
SSH_PASSWORD = "test"
TESTS_DIR = Path(__file__).resolve().parent
SSH_TIMEOUT_SECONDS = 90


async def _docker(*args: str) -> str:
    """Выполняет команду Docker и возвращает stdout."""

    process = await asyncio.create_subprocess_exec(
        "docker",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        message = stderr.decode() or stdout.decode()
        command = " ".join(("docker", *args))
        raise RuntimeError(f"{command} failed ({process.returncode}):\n{message}")
    return stdout.decode()


async def _ssh_port(container_name: str) -> int:
    """Возвращает опубликованный на хосте порт SSH тестового контейнера."""

    output = await _docker("port", container_name, "22")
    line = output.strip().splitlines()[0]
    return int(line.rsplit(":", 1)[1])


async def _wait_ssh(port: int) -> SSHClientConnection:
    """Ожидает доступности SSH-сервера по указанному порту на "127.0.0.1"."""

    deadline = time.monotonic() + SSH_TIMEOUT_SECONDS
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return await asyncssh.connect(
                "127.0.0.1",
                port=port,
                username=SSH_USER,
                password=SSH_PASSWORD,
                known_hosts=None,
            )
        except asyncssh.PermissionDenied:
            raise
        except (OSError, asyncssh.Error) as exc:
            last_error = exc
            await asyncio.sleep(0.5)
    raise TimeoutError(f"SSH не поднялся за {SSH_TIMEOUT_SECONDS} с: {last_error}")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def ssh_conn() -> AsyncIterator[SSHClientConnection]:
    """Запускает тестовый контейнер и возвращает SSH-соединение с ним."""

    container_name = f"orchestrator-logs-it-{uuid.uuid4().hex[:8]}"
    started = False
    conn: SSHClientConnection | None = None
    try:
        await _docker("build", "-t", IMAGE, str(TESTS_DIR))
        await _docker(
            "run",
            "-d",
            "--name",
            container_name,
            "--privileged",
            "--cgroupns=private",
            "--tmpfs",
            "/tmp",
            "--tmpfs",
            "/run",
            "--tmpfs",
            "/run/lock",
            "-v",
            "/sys/fs/cgroup:/sys/fs/cgroup",
            "-p",
            "127.0.0.1::22",
            IMAGE,
        )
        started = True
        try:
            conn = await _wait_ssh(await _ssh_port(container_name))
        except Exception as exc:
            logs = await _docker("logs", container_name)
            raise RuntimeError(f"{exc}\n{logs}") from exc
        whoami = await run_command(conn, "whoami")
        if whoami != SSH_USER:
            raise RuntimeError(f"SSH вошёл как {whoami}, ожидался {SSH_USER}")
        yield conn
    finally:
        if conn is not None:
            conn.close()
            await conn.wait_closed()
        if started:
            await _docker("rm", "-f", container_name)
