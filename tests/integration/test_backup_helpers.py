import shlex
import uuid

import pytest
from asyncssh import SSHClientConnection

from src.services.helpers.backup import remove_remote_file
from src.services.helpers.ssh import run_command


@pytest.mark.asyncio
@pytest.mark.integration
async def test_remove_remote_file_deletes_dump_on_remote_host(
    ssh_conn: SSHClientConnection,
) -> None:
    """Удаляет временный dump на SSH-тестовом хосте."""

    remote_path = f"/tmp/postgres-remove-{uuid.uuid4().hex} with spaces.dump"

    try:
        # Путь с пробелами дополнительно проверяет экранирование аргумента rm.
        await run_command(ssh_conn, f"printf dump > {shlex.quote(remote_path)}")

        await remove_remote_file(ssh_conn, remote_path)

        await run_command(ssh_conn, f"test ! -e {shlex.quote(remote_path)}")
    finally:
        await run_command(ssh_conn, f"rm -f -- {shlex.quote(remote_path)}")
