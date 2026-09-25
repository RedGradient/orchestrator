from datetime import datetime
import shlex
import uuid
from ipaddress import IPv4Address
from pathlib import Path

from asyncssh import SSHClientConnection

from src.schemas import CommandResponse
from src.services.helpers.backup import (
    download_dump,
    get_postgres_database,
    get_postgres_user,
    parse_container_list,
    parse_databases,
    remove_remote_file
)
from src.services.helpers.ssh import run_command


async def get_postgres_containers(
    conn: SSHClientConnection,
) -> list[dict]:
    """Ищет запущенные контейнеры PostgreSQL на хосте.

    Возвращает список словарей с полями id, image, command, status и name.
    """

    stdout = await run_command(
        conn,
        """
        docker ps --format '{{.ID}}\t{{.Image}}\t{{.Command}}\t{{.Status}}\t{{.Names}}'
        """,
        error="Failed to list running containers",
    )

    containers = parse_container_list(stdout)
    return [
        container
        for container in containers
        if "postgres" in container["image"].lower()
    ]


async def get_postgres_databases(
    conn: SSHClientConnection,
    container_name: str,
    username: str,
) -> list[str]:
    """Запрашивает имена баз в контейнере PostgreSQL.

    Возвращает список имён пользовательских баз (без шаблонов).
    """

    command = (
        f"docker exec {shlex.quote(container_name)} "
        f"psql -U {username} -d postgres -Atc "
        f'"SELECT datname FROM pg_database '
        f"WHERE datistemplate = false;\""
    )

    stdout = await run_command(
        conn,
        command,
        error=f"Can not get PostgreSQL database names from {container_name}",
    )

    return parse_databases(stdout)


async def create_postgres_dump(
    conn: SSHClientConnection,
    container_name: str,
    database_name: str,
    username: str,
) -> str:
    """Создаёт custom-format dump базы на удалённом хосте.

    Возвращает путь к файлу dump на удалённой машине.
    """

    dump_id = uuid.uuid4().hex
    remote_path = f"/tmp/postgres_{dump_id}.dump"

    command = (
        f"docker exec {shlex.quote(container_name)} "
        f"pg_dump -U {shlex.quote(username)} "
        f"-Fc -d {shlex.quote(database_name)} "
        f"> {shlex.quote(remote_path)}"
    )

    await run_command(
        conn,
        command,
        error=(
            f"Can not make dump of database "
            f"{database_name} from {container_name}"
        ),
    )

    return remote_path


async def postgres_dump(
    conn: SSHClientConnection,
    host: str,
    local_dump_dir: str,
) -> CommandResponse:
    """Делает dump баз из всех запущенных контейнеров PostgreSQL.

    Возвращает CommandResponse с IP хоста и списком сохранённых dump-файлов.
    """

    local_dir = Path(local_dump_dir) / host
    local_dir.mkdir(parents=True, exist_ok=True)

    containers = await get_postgres_containers(conn)
    result = []

    started_at = datetime.now()

    for container in containers:
        container_name = container["name"]

        username = await get_postgres_user(conn, container_name)
        db_name = await get_postgres_database(conn, container_name)

        remote_path = await create_postgres_dump(
            conn,
            container_name,
            db_name,
            username,
        )

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        local_path = local_dir / f"{container_name}_{db_name}_{timestamp}.dump"

        await download_dump(conn, remote_path, str(local_path))

        await remove_remote_file(conn, remote_path)

        result.append({
            "container": container_name,
            "db_name": db_name,
            "size_bytes": local_path.stat().st_size,
        })

    finished_at = datetime.now()

    return CommandResponse(
        ip=IPv4Address(host),
        result={
            "created_at": started_at.strftime("%Y-%m-%d_%H-%M-%S"),
            "finished_at": finished_at.strftime("%Y-%m-%d_%H-%M-%S"),
            "duration_seconds": (finished_at - started_at).total_seconds(),
            "containers": result,
        },
    )
