from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.exceptions import CommandError
from src.services.backup import create_postgres_dump, get_postgres_containers


async def test_get_postgres_containers_matches_image_case_insensitively(monkeypatch) -> None:
    """Сопоставляет подстроку postgres в имени образа без учёта регистра."""

    run = AsyncMock(
        return_value='postgres-id\tPOSTGRES:17-alpine\t"entrypoint"\tUp 1 minute\tpostgres-main'
    )
    monkeypatch.setattr("src.services.backup.run_command", run)

    containers = await get_postgres_containers(MagicMock())

    assert containers == [
        {
            "id": "postgres-id",
            "image": "POSTGRES:17-alpine",
            "command": '"entrypoint"',
            "status": "Up 1 minute",
            "name": "postgres-main",
        }
    ]


@pytest.mark.asyncio
async def test_create_postgres_dump_removes_remote_file_when_pg_dump_fails(monkeypatch) -> None:
    """Удаляет временный dump, если pg_dump завершился ошибкой."""

    conn = MagicMock()
    error = CommandError("pg_dump failed", host="test-host")
    create_dump = AsyncMock(side_effect=error)
    remove_file = AsyncMock(return_value="")
    dump_id = MagicMock(hex="test-dump-id")
    monkeypatch.setattr("src.services.backup.run_command", create_dump)
    monkeypatch.setattr("src.services.backup.uuid.uuid4", lambda: dump_id)
    monkeypatch.setattr("src.services.helpers.backup.run_command", remove_file)

    with pytest.raises(CommandError) as raised:
        await create_postgres_dump(conn, "postgres", "app", "backup_user")

    assert raised.value is error
    assert remove_file.await_args_list == [
        call(
            conn,
            "rm -f -- /tmp/postgres_test-dump-id.dump",
            error="Can not remove remote file: /tmp/postgres_test-dump-id.dump",
        )
    ]
