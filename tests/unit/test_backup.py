from unittest.mock import AsyncMock, MagicMock

from src.services.backup import get_postgres_containers


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
