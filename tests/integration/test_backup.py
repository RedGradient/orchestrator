import asyncio
import shlex
import time
import uuid
from pathlib import Path

import pytest
from asyncssh import SSHClientConnection

from src.exceptions import CommandError
from src.services.backup import get_postgres_containers, postgres_dump
from src.services.helpers.backup import parse_container_list
from src.services.helpers.ssh import run_command

POSTGRES_IMAGE = "postgres:17-alpine"
REDIS_IMAGE = "redis:7-alpine"
POSTGRES_USER = "backup_user"
POSTGRES_PASSWORD = "backup_password"
POSTGRES_DATABASE = "backup_database"
POSTGRES_TIMEOUT_SECONDS = 30


async def _wait_postgres(
    conn: SSHClientConnection,
    container_name: str,
    *,
    username: str = POSTGRES_USER,
    database: str = POSTGRES_DATABASE,
) -> None:
    """Ожидает, пока PostgreSQL в Docker-контейнере начнёт принимать подключения."""

    command = (
        f"docker exec {shlex.quote(container_name)} "
        f"psql -v ON_ERROR_STOP=1 -U {shlex.quote(username)} "
        f"-d {shlex.quote(database)} -c 'SELECT 1'"
    )
    deadline = time.monotonic() + POSTGRES_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        result = await conn.run(command, check=False)
        if result.exit_status == 0:
            return
        await asyncio.sleep(0.5)

    logs = await run_command(conn, f"docker logs {shlex.quote(container_name)}")
    raise TimeoutError(f"PostgreSQL не поднялся за {POSTGRES_TIMEOUT_SECONDS} секунд:\n{logs}")


def test_parse_container_list_parses_docker_ps_output() -> None:
    """Разбирает строки docker ps и пропускает пустые строки."""

    output = """\
postgres-id\tpostgres:17-alpine\t\"docker-entrypoint\"\tUp 2 minutes\tpostgres-main

redis-id\tredis:7-alpine\t\"docker-entrypoint\"\tUp 1 minute\tcache
"""

    assert parse_container_list(output) == [
        {
            "id": "postgres-id",
            "image": "postgres:17-alpine",
            "command": '"docker-entrypoint"',
            "status": "Up 2 minutes",
            "name": "postgres-main",
        },
        {
            "id": "redis-id",
            "image": "redis:7-alpine",
            "command": '"docker-entrypoint"',
            "status": "Up 1 minute",
            "name": "cache",
        },
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_postgres_containers_filters_running_docker_containers(
    ssh_conn: SSHClientConnection,
) -> None:
    """Возвращает запущенный PostgreSQL-контейнер и исключает Redis."""

    postgres_name = f"postgres-containers-it-{uuid.uuid4().hex[:8]}"
    redis_name = f"redis-containers-it-{uuid.uuid4().hex[:8]}"

    await run_command(ssh_conn, "sudo systemctl start docker")
    await run_command(ssh_conn, f"docker pull {shlex.quote(POSTGRES_IMAGE)}")
    await run_command(ssh_conn, f"docker pull {shlex.quote(REDIS_IMAGE)}")
    await run_command(
        ssh_conn,
        "docker run -d --name "
        f"{shlex.quote(postgres_name)} "
        f"-e POSTGRES_USER={shlex.quote(POSTGRES_USER)} "
        f"-e POSTGRES_PASSWORD={shlex.quote(POSTGRES_PASSWORD)} "
        f"-e POSTGRES_DB={shlex.quote(POSTGRES_DATABASE)} "
        f"{shlex.quote(POSTGRES_IMAGE)}",
    )
    await run_command(
        ssh_conn,
        f"docker run -d --name {shlex.quote(redis_name)} {shlex.quote(REDIS_IMAGE)}",
    )

    try:
        containers = await get_postgres_containers(ssh_conn)
    finally:
        await run_command(ssh_conn, f"docker rm -f {shlex.quote(postgres_name)} || true")
        await run_command(ssh_conn, f"docker rm -f {shlex.quote(redis_name)} || true")

    by_name = {container["name"]: container for container in containers}
    assert postgres_name in by_name
    assert redis_name not in by_name
    assert by_name[postgres_name]["image"] == POSTGRES_IMAGE
    assert by_name[postgres_name]["status"].startswith("Up")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize(
    ("environment", "username", "database", "error"),
    [
        (
            {"POSTGRES_DB": POSTGRES_DATABASE},
            "postgres",
            POSTGRES_DATABASE,
            "POSTGRES_USER is not set",
        ),
        (
            {"POSTGRES_USER": POSTGRES_USER},
            POSTGRES_USER,
            POSTGRES_USER,
            "POSTGRES_DB is not set",
        ),
    ],
    ids=["missing-postgres-user", "missing-postgres-db"],
)
async def test_postgres_dump_fails_when_required_container_environment_is_missing(
    ssh_conn: SSHClientConnection,
    tmp_path: Path,
    environment: dict[str, str],
    username: str,
    database: str,
    error: str,
) -> None:
    """Не считает backup успешным без POSTGRES_USER или POSTGRES_DB."""

    container_name = f"postgres-backup-missing-env-it-{uuid.uuid4().hex[:8]}"
    environment_args = " ".join(
        f"-e {name}={shlex.quote(value)}" for name, value in environment.items()
    )

    await run_command(ssh_conn, "sudo systemctl start docker")
    await run_command(ssh_conn, f"docker pull {shlex.quote(POSTGRES_IMAGE)}")
    await run_command(
        ssh_conn,
        "docker run -d --name "
        f"{shlex.quote(container_name)} "
        f"-e POSTGRES_PASSWORD={shlex.quote(POSTGRES_PASSWORD)} "
        f"{environment_args} {shlex.quote(POSTGRES_IMAGE)}",
    )

    try:
        await _wait_postgres(ssh_conn, container_name, username=username, database=database)

        with pytest.raises(RuntimeError, match=error):
            await postgres_dump(ssh_conn, "test-vps", str(tmp_path))

        assert list((tmp_path / "test-vps").glob("*.dump")) == []
    finally:
        await run_command(ssh_conn, f"docker rm -f {shlex.quote(container_name)} || true")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_dump_fails_without_creating_local_file_when_pg_dump_errors(
    ssh_conn: SSHClientConnection,
    tmp_path: Path,
) -> None:
    """Передаёт ошибку pg_dump вызывающему коду без локального успешного dump."""

    container_name = f"postgres-backup-pg-dump-error-it-{uuid.uuid4().hex[:8]}"

    await run_command(ssh_conn, "sudo systemctl start docker")
    await run_command(ssh_conn, f"docker pull {shlex.quote(POSTGRES_IMAGE)}")
    await run_command(
        ssh_conn,
        "docker run -d --name "
        f"{shlex.quote(container_name)} "
        f"-e POSTGRES_USER={shlex.quote(POSTGRES_USER)} "
        f"-e POSTGRES_PASSWORD={shlex.quote(POSTGRES_PASSWORD)} "
        f"-e POSTGRES_DB={shlex.quote(POSTGRES_DATABASE)} "
        f"{shlex.quote(POSTGRES_IMAGE)}",
    )

    try:
        await _wait_postgres(ssh_conn, container_name)
        await run_command(
            ssh_conn,
            f"docker exec -u root {shlex.quote(container_name)} "
            "sh -c 'mv /usr/local/bin/pg_dump /usr/local/bin/pg_dump.disabled'",
        )

        with pytest.raises(CommandError, match="Can not make dump"):
            await postgres_dump(ssh_conn, "test-vps", str(tmp_path))

        assert list((tmp_path / "test-vps").glob("*.dump")) == []
    finally:
        await run_command(ssh_conn, f"docker rm -f {shlex.quote(container_name)} || true")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_postgres_dump_creates_and_downloads_valid_custom_archive(
    ssh_conn: SSHClientConnection,
    tmp_path: Path,
) -> None:
    """Создаёт PostgreSQL-данные на тестовом VPS и проверяет скачанный custom dump."""

    container_name = f"postgres-backup-it-{uuid.uuid4().hex[:8]}"
    remote_validation_path = "/tmp/postgres-backup-validation.dump"

    await run_command(ssh_conn, "sudo systemctl start docker")
    await run_command(ssh_conn, f"docker pull {shlex.quote(POSTGRES_IMAGE)}")
    await run_command(
        ssh_conn,
        "docker run -d --name "
        f"{shlex.quote(container_name)} "
        f"-e POSTGRES_USER={shlex.quote(POSTGRES_USER)} "
        f"-e POSTGRES_PASSWORD={shlex.quote(POSTGRES_PASSWORD)} "
        f"-e POSTGRES_DB={shlex.quote(POSTGRES_DATABASE)} "
        f"{shlex.quote(POSTGRES_IMAGE)}",
    )

    try:
        await _wait_postgres(ssh_conn, container_name)
        sql = "CREATE TABLE backup_items (id integer PRIMARY KEY, name text); INSERT INTO backup_items VALUES (1, 'saved value');"
        await run_command(
            ssh_conn,
            f"docker exec {shlex.quote(container_name)} "
            f"psql -v ON_ERROR_STOP=1 -U {shlex.quote(POSTGRES_USER)} "
            f"-d {shlex.quote(POSTGRES_DATABASE)} -c {shlex.quote(sql)}",
        )

        result = await postgres_dump(ssh_conn, "test-vps", str(tmp_path))

        assert len(result["containers"]) == 1
        container = result["containers"][0]
        assert container["container"] == container_name
        assert container["db_name"] == POSTGRES_DATABASE
        assert container["size_bytes"] > 0
        assert result["duration_seconds"] >= 0

        dumps = list((tmp_path / "test-vps").glob(f"{container_name}_{POSTGRES_DATABASE}_*.dump"))
        assert len(dumps) == 1
        dump_path = dumps[0]
        assert dump_path.stat().st_size == container["size_bytes"]

        sftp = await ssh_conn.start_sftp_client()
        try:
            await sftp.put(str(dump_path), remote_validation_path)
        finally:
            sftp.exit()

        await run_command(
            ssh_conn,
            f"docker cp {shlex.quote(remote_validation_path)} "
            f"{shlex.quote(container_name)}:/tmp/validation.dump",
        )
        archive_contents = await run_command(
            ssh_conn,
            f"docker exec {shlex.quote(container_name)} pg_restore -l /tmp/validation.dump",
        )
        assert "TABLE public backup_items" in archive_contents

        remote_dumps = await run_command(ssh_conn, "find /tmp -maxdepth 1 -name 'postgres_*.dump'")
        assert remote_dumps == ""
    finally:
        await run_command(ssh_conn, f"rm -f -- {shlex.quote(remote_validation_path)}")
        await run_command(ssh_conn, f"docker rm -f {shlex.quote(container_name)} || true")
