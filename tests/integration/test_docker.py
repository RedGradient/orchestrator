import shlex
import uuid

import pytest
from asyncssh import SSHClientConnection

from src.services.docker import docker_cleanup
from src.services.helpers.ssh import run_command

ALPINE_IMAGE = "alpine:3.21"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_docker_cleanup_stops_running_containers_gracefully(
    ssh_conn: SSHClientConnection,
) -> None:
    """Останавливает контейнер через SIGTERM до его принудительного удаления."""

    container_name = f"docker-cleanup-stop-it-{uuid.uuid4().hex[:8]}"
    marker_path = f"/tmp/docker-cleanup-stop-{uuid.uuid4().hex}"
    container_command = "trap 'printf stopped > /marker; exit 0' TERM; while true; do sleep 1; done"

    await run_command(ssh_conn, "sudo systemctl start docker")
    await run_command(ssh_conn, f"docker pull {shlex.quote(ALPINE_IMAGE)}")
    await run_command(ssh_conn, f"touch {shlex.quote(marker_path)}")
    await run_command(
        ssh_conn,
        "docker run -d --name "
        f"{shlex.quote(container_name)} "
        f"-v {shlex.quote(marker_path)}:/marker "
        f"{shlex.quote(ALPINE_IMAGE)} sh -c {shlex.quote(container_command)}",
    )

    try:
        await docker_cleanup(ssh_conn)

        assert await run_command(ssh_conn, f"cat {shlex.quote(marker_path)}") == "stopped"
    finally:
        await run_command(ssh_conn, f"docker rm -f {shlex.quote(container_name)} || true")
        await run_command(ssh_conn, f"rm -f -- {shlex.quote(marker_path)}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_docker_cleanup_removes_running_and_stopped_containers(
    ssh_conn: SSHClientConnection,
) -> None:
    """Удаляет все контейнеры и возвращает их идентификаторы в результате."""

    running_name = f"docker-cleanup-running-it-{uuid.uuid4().hex[:8]}"
    stopped_name = f"docker-cleanup-stopped-it-{uuid.uuid4().hex[:8]}"

    await run_command(ssh_conn, "sudo systemctl start docker")
    await run_command(ssh_conn, f"docker pull {shlex.quote(ALPINE_IMAGE)}")
    await run_command(
        ssh_conn,
        f"docker run -d --name {shlex.quote(running_name)} {shlex.quote(ALPINE_IMAGE)} sleep infinity",
    )
    await run_command(
        ssh_conn,
        f"docker create --name {shlex.quote(stopped_name)} {shlex.quote(ALPINE_IMAGE)} sleep infinity",
    )
    running_id = await run_command(
        ssh_conn,
        f"docker inspect --format '{{{{.Id}}}}' {shlex.quote(running_name)}",
    )
    stopped_id = await run_command(
        ssh_conn,
        f"docker inspect --format '{{{{.Id}}}}' {shlex.quote(stopped_name)}",
    )

    try:
        result = await docker_cleanup(ssh_conn)

        # Docker rm выводит сокращённые ID, тогда как docker inspect возвращает полные.
        assert any(
            running_id.startswith(container_id) for container_id in result.deleted_containers
        )
        assert any(
            stopped_id.startswith(container_id) for container_id in result.deleted_containers
        )
        for container_name in (running_name, stopped_name):
            inspect_result = await ssh_conn.run(
                f"docker inspect {shlex.quote(container_name)}",
                check=False,
            )
            assert inspect_result.exit_status != 0
    finally:
        await run_command(ssh_conn, f"docker rm -f {shlex.quote(running_name)} || true")
        await run_command(ssh_conn, f"docker rm -f {shlex.quote(stopped_name)} || true")
