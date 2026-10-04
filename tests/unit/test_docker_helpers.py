from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.helpers.docker_parsers import (
    format_bytes,
    get_free_disk_space,
    parse_build_cache,
    parse_deleted_containers,
    parse_pruned_images,
    parse_pruned_networks,
    parse_pruned_volumes,
)


def test_parse_deleted_containers_strips_blank_lines() -> None:
    """Возвращает только непустые идентификаторы удалённых контейнеров."""

    assert parse_deleted_containers("\n first-id \n\nsecond-id\n") == ["first-id", "second-id"]


@pytest.mark.parametrize(
    ("parser", "header"),
    [
        (parse_pruned_volumes, "Deleted Volumes:"),
        (parse_pruned_networks, "Deleted Networks:"),
    ],
)
def test_parse_pruned_resources_ignores_docker_headers_and_summary(parser, header: str) -> None:
    """Не включает служебные строки Docker в перечень удалённых ресурсов."""

    output = f"\n{header}\nresource-one\nresource-two\n\nTotal reclaimed space: 12.3MB\n"

    assert parser(output) == ["resource-one", "resource-two"]


def test_parse_pruned_images_separates_tags_ids_and_reclaimed_space() -> None:
    """Разделяет снятые теги, удалённые слои и освобождённое место."""

    output = """\
Deleted Images:
untagged: alpine:3.21
untagged: alpine@sha256:manifest
deleted: sha256:layer-one
deleted: sha256:layer-two

Total reclaimed space: 24.5MB
"""

    assert parse_pruned_images(output) == (
        ["alpine:3.21", "alpine@sha256:manifest"],
        ["sha256:layer-one", "sha256:layer-two"],
        "24.5MB",
    )


def test_parse_pruned_images_uses_zero_when_docker_removed_nothing() -> None:
    """Возвращает пустые списки и нулевое значение для пустого вывода."""

    assert parse_pruned_images("") == ([], [], "0B")


def test_parse_build_cache_ignores_table_metadata_and_marks() -> None:
    """Извлекает ID cache-объектов, отбрасывая заголовки, итог и символ *."""

    output = """\
ID		RECLAIMABLE	SIZE	LAST ACCESSED
cache-id-one*	true	12MB	1 minute ago
cache-id-two	true	4MB	1 minute ago
Total: 16MB
Reclaimed Space: 16MB
"""

    assert parse_build_cache(output) == (["cache-id-one", "cache-id-two"], "16MB")


def test_parse_build_cache_uses_zero_when_nothing_was_pruned() -> None:
    """Корректно представляет пустой ответ docker builder prune."""

    assert parse_build_cache("Total: 0B\nReclaimed Space: 0B\n") == ([], "0B")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0.00B"),
        (1023, "1023.00B"),
        (1024, "1.00KB"),
        (5 * 1024 * 1024, "5.00MB"),
        (3 * 1024 * 1024 * 1024, "3.00GB"),
    ],
)
def test_format_bytes_uses_binary_units(value: int, expected: str) -> None:
    """Форматирует байты с двумя знаками после запятой и двоичными единицами."""

    assert format_bytes(value) == expected


async def test_get_free_disk_space_requests_root_filesystem(monkeypatch) -> None:
    """Запрашивает доступное место корневой файловой системы и возвращает байты."""

    run = AsyncMock(return_value=" 123456\n")
    monkeypatch.setattr("src.services.helpers.docker_parsers.run_command", run)
    conn = MagicMock()

    assert await get_free_disk_space(conn) == 123456
    run.assert_awaited_once_with(
        conn,
        "df -B1 / | awk 'NR==2 {print $4}'",
        error="Failed to get disk space",
    )


async def test_get_free_disk_space_raises_clear_error_for_invalid_output(monkeypatch) -> None:
    """Не маскирует некорректный ответ df как нулевое свободное место."""

    monkeypatch.setattr(
        "src.services.helpers.docker_parsers.run_command",
        AsyncMock(return_value="not-a-number"),
    )

    with pytest.raises(RuntimeError, match="Failed to parse disk space: 'not-a-number'"):
        await get_free_disk_space(MagicMock())
