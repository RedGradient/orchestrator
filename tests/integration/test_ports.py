import asyncio
import shlex
import time
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from asyncssh import SSHClientConnection

from src.schemas import ShouldClose
from src.services.helpers.ssh import run_command
from src.services.ports import (
    ALLOWED_SERVICES,
    SENSITIVE_SERVICES,
    ListeningPort,
    check_ports,
    find_docker_process,
    get_open_ports,
)

REDIS_IMAGE = "redis:7-alpine"
REDIS_NAME = "ports-it-redis"
REDIS_HOST_PORT = 16379
PUBLIC_PORT = 18080
LOCAL_PORT = 18081


async def _start_listener(conn: SSHClientConnection, host: str, port: int) -> str:
    """Запускает тестовый TCP-сервис на указанном адресе и порту."""

    unit = f"port-listener-{port}"
    code = (
        "import socket,time;"
        "s=socket.socket();"
        "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
        f"s.bind(({host!r},{port}));"
        "s.listen(1);"
        "time.sleep(3600)"
    )
    await run_command(conn, f"sudo systemctl stop {shlex.quote(unit)} || true")
    await run_command(
        conn,
        "sudo systemd-run --quiet --collect --unit "
        f"{shlex.quote(unit)} /usr/bin/python3 -c {shlex.quote(code)}",
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        output = await run_command(conn, "sudo ss -ltnH")
        if f":{port} " in output or output.rstrip().endswith(f":{port}"):
            return unit
        await asyncio.sleep(0.1)

    await _stop_listener(conn, unit)
    raise TimeoutError(f"тестовый listener не открыл порт {port}")


async def _stop_listener(conn: SSHClientConnection, unit: str) -> None:
    """Останавливает тестовый TCP-сервис."""

    await run_command(conn, f"sudo systemctl stop {shlex.quote(unit)} || true")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def published_redis(ssh_conn: SSHClientConnection) -> AsyncIterator[None]:
    """Запускает Redis-контейнер с опубликованным портом для интеграционных тестов."""

    await run_command(ssh_conn, "sudo systemctl start docker")
    await run_command(ssh_conn, f"sudo docker pull {shlex.quote(REDIS_IMAGE)}")
    await run_command(ssh_conn, f"sudo docker rm -f {shlex.quote(REDIS_NAME)} || true")
    await run_command(
        ssh_conn,
        "sudo docker run -d --name "
        f"{shlex.quote(REDIS_NAME)} -p {REDIS_HOST_PORT}:6379 {shlex.quote(REDIS_IMAGE)}",
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        output = await run_command(ssh_conn, "sudo ss -ltnpH")
        if f":{REDIS_HOST_PORT} " in output or output.rstrip().endswith(f":{REDIS_HOST_PORT}"):
            if "docker-proxy" in output:
                break
        await asyncio.sleep(0.5)
    else:
        logs = await run_command(ssh_conn, f"sudo docker logs {shlex.quote(REDIS_NAME)} || true")
        raise TimeoutError(f"порт {REDIS_HOST_PORT} не опубликовал docker-proxy:\n{logs}")
    try:
        yield
    finally:
        await run_command(ssh_conn, f"sudo docker rm -f {shlex.quote(REDIS_NAME)} || true")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_open_ports_includes_sshd(ssh_conn: SSHClientConnection) -> None:
    """Проверяет обнаружение SSH-порта среди внешне доступных портов."""

    ports = await get_open_ports(ssh_conn)

    ssh_ports = [item for item in ports if item.port == 22]
    assert ssh_ports == [ListeningPort(port=22, service="sshd")]
    assert ports == sorted(ports, key=lambda item: (item.port, item.service))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_open_ports_ignores_localhost(ssh_conn: SSHClientConnection) -> None:
    """Проверяет, что порты, доступные только через localhost, игнорируются."""

    public_unit = await _start_listener(ssh_conn, "0.0.0.0", PUBLIC_PORT)
    local_unit = await _start_listener(ssh_conn, "127.0.0.1", LOCAL_PORT)
    try:
        ports = await get_open_ports(ssh_conn)
    finally:
        await _stop_listener(ssh_conn, public_unit)
        await _stop_listener(ssh_conn, local_unit)

    assert ListeningPort(port=PUBLIC_PORT, service="python3") in ports
    assert all(item.port != LOCAL_PORT for item in ports)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_open_ports_sees_docker_proxy(
    ssh_conn: SSHClientConnection,
    published_redis: None,
) -> None:
    """Проверяет обнаружение опубликованного Docker-порта через docker-proxy."""

    ports = await get_open_ports(ssh_conn)

    assert ListeningPort(port=REDIS_HOST_PORT, service="docker-proxy") in ports


@pytest.mark.asyncio
@pytest.mark.integration
async def test_find_docker_process(
    ssh_conn: SSHClientConnection,
    published_redis: None,
) -> None:
    """Проверяет, находится ли Docker-контейнер и процесс по его порту."""

    found = await find_docker_process(ssh_conn, REDIS_HOST_PORT)

    assert found is not None
    assert found.port == REDIS_HOST_PORT
    assert found.container == REDIS_NAME
    assert found.image == REDIS_IMAGE
    assert found.container_port == 6379
    assert "redis" in found.service


@pytest.mark.asyncio
@pytest.mark.integration
async def test_find_docker_process_unknown_port(
    ssh_conn: SSHClientConnection,
    published_redis: None,
) -> None:
    """Проверяет, что для порта, не опубликованного Docker-контейнером, возвращается None."""

    assert await find_docker_process(ssh_conn, 1) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_check_ports(
    ssh_conn: SSHClientConnection,
    published_redis: None,
) -> None:
    """Проверяет определение сервисов и рекомендаций для открытых портов хоста."""

    public_unit = await _start_listener(ssh_conn, "0.0.0.0", PUBLIC_PORT)
    try:
        result = await check_ports(ssh_conn)
    finally:
        await _stop_listener(ssh_conn, public_unit)

    by_port = {item.port: item for item in result.ports}

    ssh = by_port[22]
    assert ssh.service == "sshd"
    assert ssh.is_docker is False
    assert ssh.should_close == ShouldClose.NO
    assert ssh.reason == ALLOWED_SERVICES["sshd"]

    redis = by_port[REDIS_HOST_PORT]
    assert redis.is_docker is True
    assert "redis" in redis.service
    assert redis.should_close == ShouldClose.YES
    assert redis.reason == SENSITIVE_SERVICES["redis"]

    public = by_port[PUBLIC_PORT]
    assert public.service == "python3"
    assert public.is_docker is False
    assert public.should_close == ShouldClose.UNKNOWN
