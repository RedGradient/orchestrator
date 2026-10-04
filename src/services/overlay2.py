"""Безопасный read-only анализ Docker overlay2 на удалённом хосте."""

import json
import re
import shlex
import time

from asyncssh import SSHClientConnection

from src.schemas import (
    Overlay2AnalyzeResult,
    Overlay2Confidence,
    Overlay2Finding,
    Overlay2FindingState,
    Overlay2SourceStatus,
    Overlay2Summary,
)
from src.services.helpers.ssh import run_command

OVERLAY2_ID_PATTERN = re.compile(r"^(?:[a-z0-9]{25}|[a-f0-9]{64})(?:-init)?$")
ANALYZE_GRACE_SECONDS = 24 * 60 * 60
MAX_FINDINGS = 100


async def analyze_overlay2(conn: SSHClientConnection) -> Overlay2AnalyzeResult:
    """Собрать инвентарь overlay2 через SSH, не изменяя удалённый хост.

    Если обязательный источник данных недоступен, отчёт помечается ``unsafe``.
    Такой отчёт пригоден для диагностики, но не должен использоваться для очистки.
    """

    sources: list[Overlay2SourceStatus] = []
    docker_info = await _docker_info(conn, sources)
    if docker_info is None:
        return Overlay2AnalyzeResult(sources=sources, unsafe=True)

    driver = docker_info.get("Driver")
    docker_root = docker_info.get("DockerRootDir")
    if driver != "overlay2" or not isinstance(docker_root, str) or not docker_root:
        sources.append(
            Overlay2SourceStatus(
                name="docker-info",
                ok=False,
                detail=f"Docker storage driver is {driver!r}; overlay2 is required",
            )
        )
        return Overlay2AnalyzeResult(docker_root=docker_root, sources=sources, unsafe=True)

    overlay2_root = f"{docker_root}/overlay2"
    aliases = await _link_aliases(conn, overlay2_root, sources)
    layerdb_ids = await _layerdb_references(conn, docker_root, sources)
    container_ids = await _container_references(conn, sources)
    process_ids = await _process_references(conn, sources)
    findings, inventory = await _physical_findings(
        conn,
        overlay2_root,
        aliases,
        layerdb_ids,
        container_ids,
        process_ids,
        sources,
    )

    summary = _build_summary(findings)
    visible_findings = [
        finding
        for finding in findings
        if finding.state not in {Overlay2FindingState.LIVE, Overlay2FindingState.REFERENCED}
    ]
    return Overlay2AnalyzeResult(
        docker_root=docker_root,
        overlay2_root=overlay2_root,
        disk_usage_bytes=sum(finding.size_bytes for finding in findings),
        inventory=inventory,
        sources=sources,
        unsafe=not all(source.ok for source in sources),
        summary=summary,
        findings=visible_findings[:MAX_FINDINGS],
        omitted_findings_count=max(0, len(visible_findings) - MAX_FINDINGS),
    )


async def _docker_info(
    conn: SSHClientConnection, sources: list[Overlay2SourceStatus]
) -> dict[str, object] | None:
    """Получить и проверить сведения Docker, нужные для поиска его root-каталога."""

    output = await _try_command(conn, "docker info --format '{{json .}}'", "docker-info", sources)
    if output is None:
        return None
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        sources.append(
            Overlay2SourceStatus(name="docker-info", ok=False, detail="invalid JSON response")
        )
        return None
    if not isinstance(value, dict):
        sources.append(
            Overlay2SourceStatus(name="docker-info", ok=False, detail="unexpected response")
        )
        return None
    return value


async def _link_aliases(
    conn: SSHClientConnection, overlay2_root: str, sources: list[Overlay2SourceStatus]
) -> set[str]:
    """Получить идентификаторы слоёв, на которые ссылается индекс ``overlay2/l``."""

    command = (
        f"find {shlex.quote(overlay2_root + '/l')} -mindepth 1 -maxdepth 1 -type l "
        "-exec readlink -f {} \\;"
    )
    output = await _try_root_command(conn, command, "link-index", sources)
    if output is None:
        return set()
    return {path.split("/")[-2] for path in output.splitlines() if "/diff" in path}


async def _layerdb_references(
    conn: SSHClientConnection, docker_root: str, sources: list[Overlay2SourceStatus]
) -> set[str]:
    """Получить идентификаторы из метаданных образов и монтирований Docker."""

    layerdb = f"{docker_root}/image/overlay2/layerdb"
    command = (
        f"find {shlex.quote(layerdb)} -type f "
        "\\( -name cache-id -o -name mount-id -o -name init-id \\) -exec cat {} \\;"
    )
    output = await _try_root_command(conn, command, "layerdb", sources)
    return _overlay_ids(output or "")


async def _container_references(
    conn: SSHClientConnection, sources: list[Overlay2SourceStatus]
) -> set[str]:
    """Получить идентификаторы слоёв из описаний существующих контейнеров."""

    output = await _try_command(
        conn,
        "ids=$(docker ps -aq); if [ -n \"$ids\" ]; then docker inspect $ids; else printf '[]'; fi",
        "container-inspect",
        sources,
    )
    return _overlay_ids(output or "")


async def _process_references(
    conn: SSHClientConnection, sources: list[Overlay2SourceStatus]
) -> set[str]:
    """Найти ссылки процессов на директории overlay2 через ``/proc``."""

    command = """
failed=0
for process in /proc/[0-9]*; do
    [ -r "$process/mountinfo" ] && cat "$process/mountinfo" || failed=1
    [ -r "$process/maps" ] && cat "$process/maps" || failed=1
    for item in "$process/cwd" "$process/root" "$process/fd"/*; do
        [ -e "$item" ] || continue
        readlink "$item" || failed=1
    done
done
exit "$failed"
"""
    output = await _try_root_command(conn, command, "process-references", sources)
    return _overlay_ids(output or "")


async def _physical_findings(
    conn: SSHClientConnection,
    overlay2_root: str,
    aliases: set[str],
    layerdb_ids: set[str],
    container_ids: set[str],
    process_ids: set[str],
    sources: list[Overlay2SourceStatus],
) -> tuple[list[Overlay2Finding], dict[str, int]]:
    """Обойти физические директории overlay2, измерить их и классифицировать."""

    root = shlex.quote(overlay2_root)
    command = f"""
find {root} -mindepth 1 -maxdepth 1 -type d -printf '%f|%T@\\n' |
while IFS='|' read -r object_id modified; do
    case "$object_id" in
        l) continue ;;
    esac
    size=$(du -sk -- {root}/"$object_id" | awk '{{print $1 * 1024}}') || exit 1
    printf '%s|%s|%s\\n' "$object_id" "$modified" "$size"
done
"""
    output = await _try_root_command(conn, command, "physical-tree", sources)
    if output is None:
        return [], {}

    now = time.time()
    findings: list[Overlay2Finding] = []
    inventory: dict[str, int] = {}
    for line in output.splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            continue
        object_id, modified, size = parts
        if not OVERLAY2_ID_PATTERN.fullmatch(object_id):
            continue
        try:
            age_seconds = max(0.0, now - float(modified))
            size_bytes = max(0, int(float(size)))
        except ValueError:
            continue
        finding = _classify_finding(
            object_id,
            f"{overlay2_root}/{object_id}",
            size_bytes,
            age_seconds,
            aliases,
            layerdb_ids,
            container_ids,
            process_ids,
        )
        findings.append(finding)
        inventory[finding.state.value] = inventory.get(finding.state.value, 0) + 1
    return findings, inventory


def _classify_finding(
    object_id: str,
    path: str,
    size_bytes: int,
    age_seconds: float,
    aliases: set[str],
    layerdb_ids: set[str],
    container_ids: set[str],
    process_ids: set[str],
) -> Overlay2Finding:
    """Определить безопасное предварительное состояние одной директории overlay2."""

    if object_id in process_ids:
        state, confidence, reason = (
            Overlay2FindingState.LIVE,
            Overlay2Confidence.HIGH,
            "referenced by a running process namespace",
        )
    elif object_id in layerdb_ids or object_id in container_ids:
        state, confidence, reason = (
            Overlay2FindingState.REFERENCED,
            Overlay2Confidence.HIGH,
            "referenced by Docker metadata",
        )
    elif age_seconds < ANALYZE_GRACE_SECONDS:
        state, confidence, reason = (
            Overlay2FindingState.TEMPORARY,
            Overlay2Confidence.MEDIUM,
            "younger than the 24-hour grace period",
        )
    elif object_id in aliases:
        state, confidence, reason = (
            Overlay2FindingState.UNKNOWN,
            Overlay2Confidence.LOW,
            "present in Docker link index but not in other checked sources",
        )
    else:
        state, confidence, reason = (
            Overlay2FindingState.SUSPECTED_ORPHAN,
            Overlay2Confidence.LOW,
            "not found in Docker metadata, link index, or process references",
        )
    return Overlay2Finding(
        object_type="overlay2-directory",
        object_id=object_id,
        path=path,
        size_bytes=size_bytes,
        age_seconds=age_seconds,
        state=state,
        confidence=confidence,
        reason=reason,
    )


def _build_summary(findings: list[Overlay2Finding]) -> Overlay2Summary:
    """Суммировать размеры объектов по их состояниям."""

    summary = Overlay2Summary()
    for finding in findings:
        match finding.state:
            case Overlay2FindingState.LIVE:
                summary.live_bytes += finding.size_bytes
            case Overlay2FindingState.REFERENCED:
                summary.referenced_bytes += finding.size_bytes
            case Overlay2FindingState.TEMPORARY:
                summary.temporary_bytes += finding.size_bytes
            case Overlay2FindingState.SUSPECTED_ORPHAN:
                summary.suspected_orphan_bytes += finding.size_bytes
            case Overlay2FindingState.CONFIRMED_ORPHAN:
                summary.confirmed_orphan_bytes += finding.size_bytes
            case Overlay2FindingState.UNKNOWN:
                summary.unknown_bytes += finding.size_bytes
    return summary


async def _try_command(
    conn: SSHClientConnection,
    command: str,
    source_name: str,
    sources: list[Overlay2SourceStatus],
) -> str | None:
    """Выполнить источник данных и отразить его доступность в отчёте."""

    try:
        output = await run_command(conn, command, error=f"Overlay2 source {source_name} failed")
    except Exception as exc:  # A failed source makes a cleanup report unsafe, not unavailable.
        sources.append(Overlay2SourceStatus(name=source_name, ok=False, detail=str(exc)))
        return None
    sources.append(Overlay2SourceStatus(name=source_name, ok=True, detail="available"))
    return output


async def _try_root_command(
    conn: SSHClientConnection,
    command: str,
    source_name: str,
    sources: list[Overlay2SourceStatus],
) -> str | None:
    """Выполнить команду с правами root или через беспарольный ``sudo``."""

    quoted_command = shlex.quote(command)
    root_command = (
        f'if [ "$(id -u)" -eq 0 ]; then sh -c {quoted_command}; '
        f"else sudo -n sh -c {quoted_command}; fi"
    )
    return await _try_command(conn, root_command, source_name, sources)


def _overlay_ids(value: str) -> set[str]:
    """Вернуть возможные идентификаторы физических директорий overlay2 из вывода Docker."""

    pattern = r"(?<![a-z0-9])(?:[a-z0-9]{25}|[a-f0-9]{64})(?:-init)?(?![a-z0-9])"
    return set(re.findall(pattern, value))
