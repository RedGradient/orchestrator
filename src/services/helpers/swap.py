"""Вспомогательные функции для работы с SWAP на удалённом хосте."""

from asyncssh import SSHClientConnection

from src.schemas import SwapEntry
from src.services.helpers.ssh import run_command


def calculate_swap_size(
    free_space_bytes: int,
    disk_size_bytes: int,
) -> int | None:
    """Выбирает размер SWAP в зависимости от объёма свободного места на диске.

    Политика:

    - менее 4 GB свободного места → 1 GB SWAP;
    - от 4 до менее 8 GB → 2 GB SWAP;
    - от 8 до менее 16 GB → 4 GB SWAP;
    - 16 GB и более → 8 GB SWAP.

    Возвращает размер SWAP в мегабайтах или None, если диск заполнен на 85% и более.
    """

    disk_usage_percent = 100 - (free_space_bytes / disk_size_bytes * 100)

    if disk_usage_percent >= 85:
        return None

    free_space_mb = free_space_bytes // (1024 * 1024)

    if free_space_mb < 4 * 1024:
        size_mb = 1024
    elif free_space_mb < 8 * 1024:
        size_mb = 2048
    elif free_space_mb < 16 * 1024:
        size_mb = 4096
    else:
        size_mb = 8192

    return size_mb


async def get_swap_list(
    conn: SSHClientConnection,
) -> list[SwapEntry]:
    """Возвращает список активных SWAP."""

    output = await run_command(
        conn,
        "swapon --show=NAME,SIZE --bytes --noheadings --raw",
        error="Failed to get SWAP information",
    )

    return parse_swap_list(output)


def parse_swap_list(output: str) -> list[SwapEntry]:
    """Разбирает вывод swapon.

    Возвращает список активных SWAP.
    """

    swaps: list[SwapEntry] = []

    for line in output.splitlines():
        line = line.strip()

        if not line:
            continue

        path, size = line.split(maxsplit=1)

        swaps.append(
            SwapEntry(
                path=path,
                size_bytes=int(size),
            )
        )

    return swaps


async def try_remove_swap_file(
    conn: SSHClientConnection,
    swap_path: str,
) -> None:
    """Отключает SWAP, удаляет запись из /etc/fstab и файл, если это не блочное устройство.

    Ничего не возвращает.
    """

    await run_command(
        conn,
        f"swapoff {swap_path}",
        error="Failed to disable old SWAP",
    )

    await run_command(
        conn,
        f"sed -i '\\|^{swap_path} |d' /etc/fstab",
        error="Failed to remove SWAP from /etc/fstab",
    )

    await run_command(
        conn,
        f"test -b {swap_path} || rm -f {swap_path}",
        error="Failed to remove old SWAP file",
    )


async def free_disk_space(conn: SSHClientConnection) -> int:
    """Возвращает свободное дисковое пространство корневой ФС в байтах."""

    output = await run_command(
        conn,
        "df --output=avail -B1 /",
        error="Can not check free space",
    )

    return parse_free_disk_space(output)


async def check_swap(
    conn: SSHClientConnection,
) -> tuple[bool, int, list[SwapEntry]]:
    """Проверяет активный SWAP.

    Возвращает кортеж (активен ли SWAP, общий размер в байтах, список устройств).
    """

    output = await run_command(
        conn,
        "swapon --show=NAME,SIZE --bytes --noheadings --raw",
        error="Failed to get SWAP information",
    )

    return parse_swap_info(output)


def parse_swap_info(
    output: str,
) -> tuple[bool, int, list[SwapEntry]]:
    """Разбирает вывод swapon.

    Возвращает кортеж (активен ли SWAP, общий размер в байтах, список устройств).
    """

    total_size = 0
    swaps: list[SwapEntry] = []

    for line in output.splitlines():
        line = line.strip()

        if not line:
            continue

        path, size = line.split(maxsplit=1)
        size_bytes = int(size)

        swaps.append(
            SwapEntry(
                path=path,
                size_bytes=size_bytes,
            )
        )

        total_size += size_bytes

    return total_size > 0, total_size, swaps


def parse_free_disk_space(output: str) -> int:
    """Извлекает объём доступного дискового пространства из вывода df.

    Возвращает размер в байтах.
    """

    lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]

    if len(lines) != 2:
        raise ValueError(f"Unexpected df output: {output!r}")

    return int(lines[1])


async def check_disk_size(
    conn: SSHClientConnection,
) -> int:
    """Возвращает общий размер корневой файловой системы в байтах."""

    output = await run_command(
        conn,
        "df --output=size -B1 /",
        error="Failed to get disk size",
    )

    lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]

    return int(lines[1])
