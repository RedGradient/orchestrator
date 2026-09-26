from asyncssh import SSHClientConnection

from src.schemas import SwapInfo, CreateSwapResult
from src.services.helpers.ssh import run_command
from src.services.helpers.swap import (
    calculate_swap_size,
    check_disk_size,
    check_swap,
    free_disk_space,
    get_swap_list,
    try_remove_swap_file,
)

SWAP_PATH = "/swapfile"


async def try_create_swap(
    conn: SSHClientConnection,
) -> CreateSwapResult:
    """Создаёт SWAP и сохраняет его после перезагрузки.

    Возвращает CreateSwapResult с флагом создания и информацией о SWAP.
    """

    size_mb = calculate_swap_size(
        free_space_bytes=await free_disk_space(conn),
        disk_size_bytes=await check_disk_size(conn),
    )

    if size_mb is None:
        return CreateSwapResult(created=False)

    await swap_cleanup(conn)
    await create_swap(conn, size_mb)

    return CreateSwapResult(
        created=True,
        swap_info=await get_swap_info(conn),
    )


async def create_swap(conn: SSHClientConnection, size_mb: int) -> None:
    """Создаёт файл SWAP заданного размера, активирует его и прописывает в fstab"""

    # Создаём файл SWAP указанного размера
    await run_command(
        conn,
        f"fallocate -l {size_mb}M {SWAP_PATH}",
        error="Failed to create SWAP file",
    )

    # Ограничиваем доступ к файлу только для root
    await run_command(
        conn,
        f"chmod 600 {SWAP_PATH}",
        error="Failed to set SWAP file permissions",
    )

    # Инициализируем файл как SWAP
    await run_command(
        conn,
        f"mkswap {SWAP_PATH}",
        error="Failed to initialize SWAP",
    )

    # Активируем SWAP
    await run_command(
        conn,
        f"swapon {SWAP_PATH}",
        error="Failed to enable SWAP",
    )

    # Добавляем SWAP в fstab для автоматической активации после перезагрузки
    await run_command(
        conn,
        f"echo '{SWAP_PATH} none swap sw 0 0' >> /etc/fstab",
        error="Failed to add SWAP to /etc/fstab",
    )


async def swap_cleanup(conn: SSHClientConnection) -> None:
    """Отключает и удаляет все активные SWAP на хосте"""

    swap_list = await get_swap_list(conn)

    for swap in swap_list:
        await try_remove_swap_file(conn, swap.path)


async def get_swap_info(conn: SSHClientConnection) -> SwapInfo:
    """Собирает сведения об активном SWAP и свободном месте на диске.

    Возвращает SwapInfo с флагом активности, общим размером SWAP,
    списком устройств и свободным местом в байтах.
    """

    is_active, size_bytes, swap_list = await check_swap(conn)
    free_space_bytes = await free_disk_space(conn)

    return SwapInfo(
        is_active=is_active,
        total_swap_size_bytes=size_bytes,
        free_disk_space_bytes=free_space_bytes,
        swaps=swap_list,
    )
