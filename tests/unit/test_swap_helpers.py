from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.schemas import SwapEntry
from src.services.helpers.swap import (
    calculate_swap_size,
    check_disk_size,
    check_swap,
    free_disk_space,
    get_ram_size,
    get_swap_list,
    parse_free_disk_space,
    parse_swap_info,
    parse_swap_list,
    try_remove_swap_file,
)

MEBIBYTE = 1024 * 1024
GIBIBYTE = 1024 * MEBIBYTE


@pytest.mark.parametrize(
    ("free_space_bytes", "disk_size_bytes", "ram_size_bytes", "expected_size_mb"),
    [
        (3 * GIBIBYTE, 10 * GIBIBYTE, GIBIBYTE, 1024),
        (6 * GIBIBYTE, 10 * GIBIBYTE, 4 * GIBIBYTE, 2048),
        (12 * GIBIBYTE, 20 * GIBIBYTE, 16 * GIBIBYTE, 4096),
        (20 * GIBIBYTE, 30 * GIBIBYTE, 16 * GIBIBYTE, 4096),
        (20 * GIBIBYTE, 30 * GIBIBYTE, GIBIBYTE, 2048),
        (3 * GIBIBYTE, 10 * GIBIBYTE, 16 * GIBIBYTE, 1024),
    ],
)
def test_calculate_swap_size_uses_disk_and_ram_limits(
    free_space_bytes: int,
    disk_size_bytes: int,
    ram_size_bytes: int,
    expected_size_mb: int,
) -> None:
    """Выбирает меньший из лимитов, заданных диском и RAM."""

    assert (
        calculate_swap_size(free_space_bytes, disk_size_bytes, ram_size_bytes) == expected_size_mb
    )


def test_calculate_swap_size_rejects_disk_with_85_percent_usage() -> None:
    """Не предлагает создавать swap, когда заполнено 85% диска."""

    assert calculate_swap_size(15 * GIBIBYTE, 100 * GIBIBYTE, GIBIBYTE) is None


def test_parse_swap_list_parses_active_swap_devices() -> None:
    """Разбирает пути и размеры активных swap-устройств."""

    output = "\n/swapfile 2147479552\n/dev/vdb 1073737728\n"

    assert parse_swap_list(output) == [
        SwapEntry(path="/swapfile", size_bytes=2147479552),
        SwapEntry(path="/dev/vdb", size_bytes=1073737728),
    ]


def test_parse_swap_info_returns_total_size_and_devices() -> None:
    """Суммирует размеры всех swap-устройств из вывода swapon."""

    is_active, total_size, swaps = parse_swap_info("/swapfile 1024\n/dev/vdb 2048\n")

    assert is_active is True
    assert total_size == 3072
    assert swaps == [
        SwapEntry(path="/swapfile", size_bytes=1024),
        SwapEntry(path="/dev/vdb", size_bytes=2048),
    ]


def test_parse_swap_info_handles_empty_output() -> None:
    """Считает пустой вывод swapon отсутствием активного swap."""

    assert parse_swap_info("\n") == (False, 0, [])


def test_parse_free_disk_space_accepts_df_output() -> None:
    """Извлекает число байтов из стандартного вывода df."""

    assert parse_free_disk_space("Avail\n 123456 \n") == 123456


@pytest.mark.parametrize("output", ["", "Avail\n", "Avail\n1\n2\n"])
def test_parse_free_disk_space_rejects_unexpected_df_output(output: str) -> None:
    """Не маскирует повреждённый или неполный вывод df."""

    with pytest.raises(ValueError, match="Unexpected df output"):
        parse_free_disk_space(output)


async def test_get_swap_list_runs_swapon_and_parses_result(monkeypatch) -> None:
    """Запрашивает список swap-устройств и разбирает ответ удалённого хоста."""

    run = AsyncMock(return_value="/swapfile 1024\n")
    monkeypatch.setattr("src.services.helpers.swap.run_command", run)
    conn = MagicMock()

    assert await get_swap_list(conn) == [SwapEntry(path="/swapfile", size_bytes=1024)]
    run.assert_awaited_once_with(
        conn,
        "swapon --show=NAME,SIZE --bytes --noheadings --raw",
        error="Failed to get SWAP information",
    )


async def test_get_ram_size_reads_memtotal_from_remote_host(monkeypatch) -> None:
    """Получает размер RAM удалённого хоста в байтах."""

    run = AsyncMock(return_value="1048576")
    monkeypatch.setattr("src.services.helpers.swap.run_command", run)
    conn = MagicMock()

    assert await get_ram_size(conn) == 1048576 * 1024
    run.assert_awaited_once_with(
        conn,
        "awk '/^MemTotal/ {print $2}' /proc/meminfo",
        error="Failed to get RAM size",
    )


@pytest.mark.parametrize("value", ["", "unknown", "1024 KB"])
async def test_get_ram_size_rejects_invalid_memtotal(monkeypatch, value: str) -> None:
    """Не подменяет некорректный вывод MemTotal нулевым размером RAM."""

    monkeypatch.setattr("src.services.helpers.swap.run_command", AsyncMock(return_value=value))

    with pytest.raises(ValueError, match="Invalid MemTotal value"):
        await get_ram_size(MagicMock())


async def test_check_swap_returns_parsed_state(monkeypatch) -> None:
    """Возвращает признак активности и суммарный размер swap."""

    run = AsyncMock(return_value="/swapfile 1024\n")
    monkeypatch.setattr("src.services.helpers.swap.run_command", run)

    assert await check_swap(MagicMock()) == (
        True,
        1024,
        [SwapEntry(path="/swapfile", size_bytes=1024)],
    )


async def test_disk_helpers_request_root_filesystem_sizes(monkeypatch) -> None:
    """Запрашивает свободное и общее место именно корневой файловой системы."""

    run = AsyncMock(side_effect=["Avail\n123\n", "Size\n456\n"])
    monkeypatch.setattr("src.services.helpers.swap.run_command", run)
    conn = MagicMock()

    assert await free_disk_space(conn) == 123
    assert await check_disk_size(conn) == 456
    assert run.await_args_list == [
        call(conn, "df --output=avail -B1 /", error="Can not check free space"),
        call(conn, "df --output=size -B1 /", error="Failed to get disk size"),
    ]


async def test_try_remove_swap_file_disables_cleans_and_removes_file(monkeypatch) -> None:
    """Отключает swap, удаляет запись fstab и файл в заданном порядке."""

    run = AsyncMock(return_value="")
    monkeypatch.setattr("src.services.helpers.swap.run_command", run)
    conn = MagicMock()

    await try_remove_swap_file(conn, "/swapfile")

    assert run.await_args_list == [
        call(conn, "swapoff /swapfile", error="Failed to disable old SWAP"),
        call(
            conn,
            "sed -i '\\|^/swapfile |d' /etc/fstab",
            error="Failed to remove SWAP from /etc/fstab",
        ),
        call(
            conn,
            "test -b /swapfile || rm -f /swapfile",
            error="Failed to remove old SWAP file",
        ),
    ]
