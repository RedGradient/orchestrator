from unittest.mock import AsyncMock, MagicMock, call

from src.schemas import SwapEntry, SwapInfo
from src.services.swap import (
    SWAP_PATH,
    create_swap,
    get_swap_info,
    swap_cleanup,
    try_create_swap,
)


async def test_create_swap_runs_required_commands_in_order(monkeypatch) -> None:
    """Создаёт, активирует swap-файл и добавляет его в fstab."""

    run = AsyncMock(return_value="")
    monkeypatch.setattr("src.services.swap.run_command", run)
    conn = MagicMock()

    await create_swap(conn, 2048)

    assert run.await_args_list == [
        call(conn, f"fallocate -l 2048M {SWAP_PATH}", error="Failed to create SWAP file"),
        call(conn, f"chmod 600 {SWAP_PATH}", error="Failed to set SWAP file permissions"),
        call(conn, f"mkswap {SWAP_PATH}", error="Failed to initialize SWAP"),
        call(conn, f"swapon {SWAP_PATH}", error="Failed to enable SWAP"),
        call(
            conn,
            f"echo '{SWAP_PATH} none swap sw 0 0' >> /etc/fstab",
            error="Failed to add SWAP to /etc/fstab",
        ),
    ]


async def test_swap_cleanup_removes_every_active_swap(monkeypatch) -> None:
    """Передаёт каждый активный swap в функцию удаления."""

    swaps = [
        SwapEntry(path="/swapfile", size_bytes=1024),
        SwapEntry(path="/dev/vdb", size_bytes=2048),
    ]
    get_list = AsyncMock(return_value=swaps)
    remove = AsyncMock()
    monkeypatch.setattr("src.services.swap.get_swap_list", get_list)
    monkeypatch.setattr("src.services.swap.try_remove_swap_file", remove)
    conn = MagicMock()

    await swap_cleanup(conn)

    get_list.assert_awaited_once_with(conn)
    assert remove.await_args_list == [call(conn, "/swapfile"), call(conn, "/dev/vdb")]


async def test_try_create_swap_returns_not_created_when_disk_is_too_full(monkeypatch) -> None:
    """Завершает сценарий без очистки и создания, если swap не допустим."""

    monkeypatch.setattr("src.services.swap.free_disk_space", AsyncMock(return_value=1))
    monkeypatch.setattr("src.services.swap.check_disk_size", AsyncMock(return_value=100))
    monkeypatch.setattr("src.services.swap.get_ram_size", AsyncMock(return_value=1))
    monkeypatch.setattr("src.services.swap.calculate_swap_size", MagicMock(return_value=None))
    cleanup = AsyncMock()
    create = AsyncMock()
    monkeypatch.setattr("src.services.swap.swap_cleanup", cleanup)
    monkeypatch.setattr("src.services.swap.create_swap", create)

    result = await try_create_swap(MagicMock())

    assert result.created is False
    assert result.swap_info is None
    cleanup.assert_not_awaited()
    create.assert_not_awaited()


async def test_try_create_swap_cleans_creates_and_returns_fresh_info(monkeypatch) -> None:
    """Очищает старый swap, создаёт новый и возвращает его состояние."""

    conn = MagicMock()
    monkeypatch.setattr("src.services.swap.free_disk_space", AsyncMock(return_value=100))
    monkeypatch.setattr("src.services.swap.check_disk_size", AsyncMock(return_value=200))
    monkeypatch.setattr("src.services.swap.get_ram_size", AsyncMock(return_value=300))
    monkeypatch.setattr("src.services.swap.calculate_swap_size", MagicMock(return_value=2048))
    cleanup = AsyncMock()
    create = AsyncMock()
    swap_info = SwapInfo(
        is_active=True,
        total_swap_size_bytes=2048,
        free_disk_space_bytes=100,
        swaps=[SwapEntry(path=SWAP_PATH, size_bytes=2048)],
    )
    get_info = AsyncMock(return_value=swap_info)
    monkeypatch.setattr("src.services.swap.swap_cleanup", cleanup)
    monkeypatch.setattr("src.services.swap.create_swap", create)
    monkeypatch.setattr("src.services.swap.get_swap_info", get_info)

    result = await try_create_swap(conn)

    assert result.created is True
    assert result.swap_info == swap_info
    cleanup.assert_awaited_once_with(conn)
    create.assert_awaited_once_with(conn, 2048)
    get_info.assert_awaited_once_with(conn)


async def test_get_swap_info_combines_swap_and_disk_data(monkeypatch) -> None:
    """Собирает ответ API из статуса swap и свободного места."""

    swaps = [SwapEntry(path=SWAP_PATH, size_bytes=1024)]
    monkeypatch.setattr(
        "src.services.swap.check_swap",
        AsyncMock(return_value=(True, 1024, swaps)),
    )
    monkeypatch.setattr("src.services.swap.free_disk_space", AsyncMock(return_value=4096))

    assert await get_swap_info(MagicMock()) == SwapInfo(
        is_active=True,
        total_swap_size_bytes=1024,
        free_disk_space_bytes=4096,
        swaps=swaps,
    )
