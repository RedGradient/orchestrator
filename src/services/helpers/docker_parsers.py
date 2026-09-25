from asyncssh import SSHClientConnection

from src.services.helpers.ssh import run_command


def parse_deleted_containers(stdout: str) -> list[str]:
    """Разбирает вывод docker ps -aq / docker rm."""

    return [
        line.strip()
        for line in stdout.splitlines()
        if line.strip()
    ]


def parse_pruned_volumes(stdout: str) -> list[str]:
    """Разбирает вывод docker volume prune."""

    volumes: list[str] = []

    for line in stdout.splitlines():
        line = line.strip()

        if not line:
            continue
        if line.startswith("Deleted Volumes:"):
            continue
        if line.startswith("Total reclaimed space:"):
            continue

        volumes.append(line)

    return volumes


def parse_pruned_networks(stdout: str) -> list[str]:
    """Разбирает вывод docker network prune."""

    networks: list[str] = []

    for line in stdout.splitlines():
        line = line.strip()

        if not line:
            continue
        if line.startswith("Deleted Networks:"):
            continue
        if line.startswith("Total reclaimed space:"):
            continue

        networks.append(line)

    return networks


def parse_pruned_images(
    stdout: str,
) -> tuple[list[str], list[str], str]:
    """Разбирает вывод docker image prune."""

    untagged_images: list[str] = []
    deleted_images: list[str] = []
    reclaimed_space = "0B"

    for line in stdout.splitlines():
        line = line.strip()

        if not line:
            continue

        if line.startswith("untagged: "):
            untagged_images.append(
                line.removeprefix("untagged: ").strip()
            )
        elif line.startswith("deleted: "):
            deleted_images.append(
                line.removeprefix("deleted: ").strip()
            )
        elif line.startswith("Total reclaimed space:"):
            reclaimed_space = (
                line.removeprefix("Total reclaimed space:").strip()
            )

    return untagged_images, deleted_images, reclaimed_space


def parse_build_cache(stdout: str) -> tuple[list[str], str]:
    """Разбирает вывод docker builder prune."""

    deleted_objects: list[str] = []
    reclaimed_space = "0B"

    for line in stdout.splitlines():
        line = line.strip()

        if not line:
            continue
        if line.startswith("ID") and "RECLAIMABLE" in line:
            continue
        if line.startswith("Total:"):
            continue
        if line.startswith("Reclaimed Space:"):
            reclaimed_space = (
                line.removeprefix("Reclaimed Space:").strip()
            )
            continue

        cache_id = line.split()[0].rstrip("*")
        deleted_objects.append(cache_id)

    return deleted_objects, reclaimed_space


def format_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    size = float(value)

    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f}{unit}"
        size /= 1024

    return f"{size:.2f}PB"


async def get_free_disk_space(conn: SSHClientConnection) -> int:
    """Возвращает количество свободного места на / в байтах."""

    output = await run_command(
        conn,
        "df -B1 / | awk 'NR==2 {print $4}'",
        error="Failed to get disk space",
    )
    try:
        return int(output)
    except ValueError as exc:
        raise RuntimeError(f"Failed to parse disk space: {output!r}") from exc
