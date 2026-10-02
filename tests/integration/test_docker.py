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
