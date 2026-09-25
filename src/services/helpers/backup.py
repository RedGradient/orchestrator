"""Вспомогательные функции для бэкапа PostgreSQL на удалённом хосте."""

import shlex
from pathlib import Path
from typing import Any

from asyncssh import SSHClientConnection

from src.services.helpers.ssh import run_command


def parse_databases(output: str) -> list[str]:
    """Разбирает вывод psql со списком баз.

    Возвращает список имён баз данных без пустых строк.
    """

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]


def parse_container_list(stdout: str) -> list[dict[str, Any]]:
    """Разбирает табличный вывод `docker ps`.

    Возвращает список словарей с полями id, image, command, status и name.
    """

    containers: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        container_id, image, command, status, name = line.split("\t")
        containers.append({
            "id": container_id,
            "image": image,
            "command": command,
            "status": status,
            "name": name,
        })
    return containers


async def get_postgres_user(
    conn: SSHClientConnection,
    container_name: str,
) -> str:
    """Читает POSTGRES_USER из окружения контейнера.

    Возвращает имя пользователя PostgreSQL.
    """

    command = (
        f"docker inspect "
        f"--format '{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}' "
        f"{shlex.quote(container_name)} "
        f"| grep '^POSTGRES_USER=' "
        f"| cut -d= -f2-"
    )

    stdout = await run_command(
        conn,
        command,
        error=f"Can not get PostgreSQL user from {container_name}",
    )

    username = stdout.strip()
    if not username:
        raise RuntimeError(
            f"POSTGRES_USER is not set in container {container_name}"
        )
    return username


async def get_postgres_database(
    conn: SSHClientConnection,
    container_name: str,
) -> str:
    """Читает POSTGRES_DB из окружения контейнера.

    Возвращает имя основной базы данных.
    """

    command = (
        f"docker inspect "
        f"--format '{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}' "
        f"{shlex.quote(container_name)} "
        f"| grep '^POSTGRES_DB=' "
        f"| cut -d= -f2-"
    )

    stdout = await run_command(
        conn,
        command,
        error=f"Can not get PostgreSQL database from {container_name}",
    )

    database = stdout.strip()
    if not database:
        raise RuntimeError(
            f"POSTGRES_DB is not set in container {container_name}"
        )
    return database


async def download_dump(
    conn: SSHClientConnection,
    remote_path: str,
    local_path: str,
) -> None:
    """Скачивает dump с удалённого хоста по SFTP.

    Ничего не возвращает; файл сохраняется по local_path.
    """

    sftp = await conn.start_sftp_client()
    try:
        await sftp.get(remote_path, local_path)
    finally:
        sftp.exit()


async def remove_remote_file(
    conn: SSHClientConnection,
    remote_path: str,
) -> None:
    """Удаляет файл на удалённом хосте.

    Ничего не возвращает.
    """

    command = f"rm -f -- {shlex.quote(remote_path)}"
    await run_command(
        conn,
        command,
        error=f"Can not remove remote file: {remote_path}",
    )
