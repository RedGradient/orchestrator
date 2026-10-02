from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.helpers.backup import (
    download_dump,
    get_postgres_database,
    get_postgres_user,
    parse_container_list,
    parse_databases,
    remove_remote_file,
)


def test_parse_databases_strips_empty_lines() -> None:
    """Возвращает только непустые имена баз без окружающих пробелов."""

    assert parse_databases("\n postgres \n\napp\n  \n") == ["postgres", "app"]


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
async def test_get_postgres_user_reads_and_strips_container_environment(monkeypatch) -> None:
    """Извлекает POSTGRES_USER из вывода docker inspect."""

    run = AsyncMock(return_value=" backup_user \n")
    monkeypatch.setattr("src.services.helpers.backup.run_command", run)
    conn = MagicMock()

    username = await get_postgres_user(conn, "postgres main")

    assert username == "backup_user"
    command = run.await_args.args[1]
    assert "docker inspect" in command
    assert "'postgres main'" in command
    assert "grep '^POSTGRES_USER='" in command


@pytest.mark.asyncio
async def test_get_postgres_database_reads_and_strips_container_environment(monkeypatch) -> None:
    """Извлекает POSTGRES_DB из вывода docker inspect."""

    run = AsyncMock(return_value=" app_database \n")
    monkeypatch.setattr("src.services.helpers.backup.run_command", run)
    conn = MagicMock()

    database = await get_postgres_database(conn, "postgres-main")

    assert database == "app_database"
    command = run.await_args.args[1]
    assert "grep '^POSTGRES_DB='" in command
    assert run.await_args.kwargs["error"] == "Can not get PostgreSQL database from postgres-main"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("getter", "environment_name"),
    [
        (get_postgres_user, "POSTGRES_USER"),
        (get_postgres_database, "POSTGRES_DB"),
    ],
)
async def test_get_postgres_environment_value_fails_when_value_is_empty(
    monkeypatch,
    getter,
    environment_name: str,
) -> None:
    """Не принимает пустое значение обязательной переменной окружения."""

    monkeypatch.setattr("src.services.helpers.backup.run_command", AsyncMock(return_value=" \n"))

    with pytest.raises(RuntimeError, match=f"{environment_name} is not set"):
        await getter(MagicMock(), "postgres-main")


@pytest.mark.asyncio
async def test_download_dump_downloads_file_and_closes_sftp_client() -> None:
    """Скачивает dump по SFTP и закрывает клиент после успешной передачи."""

    sftp = MagicMock()
    sftp.get = AsyncMock()
    conn = MagicMock()
    conn.start_sftp_client = AsyncMock(return_value=sftp)

    await download_dump(conn, "/tmp/remote.dump", "/tmp/local.dump")

    sftp.get.assert_awaited_once_with("/tmp/remote.dump", "/tmp/local.dump")
    sftp.exit.assert_called_once_with()


@pytest.mark.asyncio
async def test_download_dump_closes_sftp_client_when_download_fails() -> None:
    """Закрывает SFTP-клиент даже если скачивание завершилось ошибкой."""

    sftp = MagicMock()
    sftp.get = AsyncMock(side_effect=OSError("SFTP disconnected"))
    conn = MagicMock()
    conn.start_sftp_client = AsyncMock(return_value=sftp)

    with pytest.raises(OSError, match="SFTP disconnected"):
        await download_dump(conn, "/tmp/remote.dump", "/tmp/local.dump")

    sftp.exit.assert_called_once_with()


@pytest.mark.asyncio
async def test_remove_remote_file_quotes_path_and_runs_rm(monkeypatch) -> None:
    """Удаляет временный файл командой rm с безопасно экранированным путём."""

    run = AsyncMock(return_value="")
    monkeypatch.setattr("src.services.helpers.backup.run_command", run)
    conn = MagicMock()

    await remove_remote_file(conn, "/tmp/dump with spaces.dump")

    assert run.await_args.args == (conn, "rm -f -- '/tmp/dump with spaces.dump'")
    assert (
        run.await_args.kwargs["error"] == "Can not remove remote file: /tmp/dump with spaces.dump"
    )
