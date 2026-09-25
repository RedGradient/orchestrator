from ipaddress import IPv4Address

from asyncssh import SSHClientConnection

from src.schemas import CommandResponse, DockerPruneResult
from src.services.helpers.docker_parsers import (
    format_bytes,
    get_free_disk_space,
    parse_build_cache,
    parse_deleted_containers,
    parse_pruned_images,
    parse_pruned_networks,
    parse_pruned_volumes,
)
from src.services.helpers.ssh import run_command


async def docker_cleanup(
    conn: SSHClientConnection,
    ip: IPv4Address,
) -> CommandResponse:
    """Полностью очищает Docker host от контейнеров и неиспользуемых ресурсов.

    Возвращает CommandResponse с IP хоста и итогом очистки DockerPruneResult.
    """

    result = DockerPruneResult()

    # Замеряем свободное пространство до очистки
    free_before = await get_free_disk_space(conn)

    # Останавливаем все контейнеры
    await run_command(
        conn,
        """
        containers=$(docker ps -q)
        if [ -n "$containers" ]; then
            docker stop $containers
        fi
        """,
        error="Failed to stop containers",
    )

    # Удаляем контейнеры; в stdout — id реально удалённых
    result.deleted_containers = parse_deleted_containers(
        await run_command(
            conn,
            """
            ids=$(docker ps -aq)
            if [ -n "$ids" ]; then
                docker rm -f $ids
            fi
            """,
            error="Failed to remove containers",
        )
    )

    result.deleted_volumes = parse_pruned_volumes(
        await run_command(
            conn,
            "docker volume prune --all --force",
            error="Failed to remove volumes",
        )
    )
    result.deleted_networks = parse_pruned_networks(
        await run_command(
            conn,
            "docker network prune --force",
            error="Failed to remove networks",
        )
    )
    result.untagged_images, result.deleted_images, _ = parse_pruned_images(
        await run_command(
            conn,
            "docker image prune --all --force",
            error="Failed to remove images",
        )
    )
    result.deleted_build_cache_objects, _ = parse_build_cache(
        await run_command(
            conn,
            "docker builder prune --all --force",
            error="Failed to remove build cache",
        )
    )

    # Замеряем свободное пространство после очистки
    free_after = await get_free_disk_space(conn)

    # Получаем освободившееся место на диске после очистки
    result.disk_space_reclaimed = format_bytes(max(0, free_after - free_before))

    return CommandResponse(ip=ip, result=result)
