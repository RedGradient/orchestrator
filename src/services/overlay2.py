"""Безопасный read-only анализ Docker overlay2 на удалённом хосте."""

import json
import re
import shlex
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from asyncssh import SSHClientConnection

from src.schemas import (
    Overlay2AnalyzeResult,
    Overlay2CleanupRecord,
    Overlay2CleanupResult,
    Overlay2Confidence,
    Overlay2Finding,
    Overlay2FindingState,
    Overlay2Fingerprint,
    Overlay2SourceStatus,
    Overlay2Summary,
)
from src.services.helpers.ssh import run_command

OVERLAY2_ID_PATTERN = re.compile(r"^(?:[a-z0-9]{25}|[a-f0-9]{64})(?:-init)?$")
ANALYZE_GRACE_SECONDS = 24 * 60 * 60
MAX_FINDINGS = 100
CLEANUP_METHOD = "atomic_stage_then_recursive_delete"
CLEANUP_RECHECK_DELAY_SECONDS = 30
CLEANUP_LOCK_PATH = "/run/lock/orchestrator-overlay2-cleanup.lock"


async def analyze_overlay2(
    conn: SSHClientConnection, *, max_findings: int | None = MAX_FINDINGS
) -> Overlay2AnalyzeResult:
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
    report_findings = visible_findings if max_findings is None else visible_findings[:max_findings]
    return Overlay2AnalyzeResult(
        docker_root=docker_root,
        overlay2_root=overlay2_root,
        disk_usage_bytes=sum(finding.size_bytes for finding in findings),
        inventory=inventory,
        sources=sources,
        unsafe=not all(source.ok for source in sources),
        summary=summary,
        findings=report_findings,
        omitted_findings_count=max(0, len(visible_findings) - len(report_findings)),
    )


def plan_overlay2_cleanup(
    first_scan: Overlay2AnalyzeResult, second_scan: Overlay2AnalyzeResult
) -> list[Overlay2Finding]:
    """Подтвердить неизменные orphan-кандидаты по двум полным безопасным снимкам.

    Функция только формирует план. Повторная проверка непосредственно перед
    удалением и сама очистка будут выполнены следующим этапом.
    """

    if (
        first_scan.unsafe
        or second_scan.unsafe
        or first_scan.overlay2_root != second_scan.overlay2_root
        or first_scan.inventory != second_scan.inventory
        or first_scan.omitted_findings_count != 0
        or second_scan.omitted_findings_count != 0
    ):
        return []

    first_findings = {finding.path: finding for finding in first_scan.findings}
    confirmed: list[Overlay2Finding] = []
    for finding in second_scan.findings:
        previous = first_findings.get(finding.path)
        if (
            previous is None
            or previous.state != Overlay2FindingState.SUSPECTED_ORPHAN
            or finding.state != Overlay2FindingState.SUSPECTED_ORPHAN
            or previous.fingerprint is None
            or finding.fingerprint != previous.fingerprint
            or not finding.checks
            or not all(finding.checks.values())
        ):
            continue
        confirmed.append(
            finding.model_copy(
                update={
                    "state": Overlay2FindingState.CONFIRMED_ORPHAN,
                    "confidence": Overlay2Confidence.HIGH,
                    "reason": (
                        "absent from Docker metadata, link index and process references; "
                        "older than grace period and unchanged between two full scans"
                    ),
                    "cleanup_method": CLEANUP_METHOD,
                }
            )
        )
    return confirmed


async def cleanup_overlay2(conn: SSHClientConnection) -> Overlay2CleanupResult:
    """Безопасно удалить подтверждённые orphan-директории overlay2 через SSH."""

    async with _remote_cleanup_lock(conn):
        first_scan = await analyze_overlay2(conn, max_findings=None)
        await run_command(
            conn,
            f"sleep {CLEANUP_RECHECK_DELAY_SECONDS}",
            error="Overlay2 cleanup recheck delay failed",
        )
        second_scan = await analyze_overlay2(conn, max_findings=None)
        operation_plan = plan_overlay2_cleanup(first_scan, second_scan)

        operations: list[Overlay2CleanupRecord] = []
        freed_bytes = 0
        for candidate in operation_plan:
            fresh_scan = await analyze_overlay2(conn, max_findings=None)
            safe, reason = _candidate_is_safe(candidate, fresh_scan)
            if not safe:
                operations.append(
                    Overlay2CleanupRecord(
                        path=candidate.path,
                        result=f"SKIPPED: {reason}",
                        method=CLEANUP_METHOD,
                    )
                )
                continue
            try:
                result = await _stage_and_delete_candidate(conn, candidate)
            except Exception as exc:
                operations.append(
                    Overlay2CleanupRecord(
                        path=candidate.path,
                        result=f"FAILED: {type(exc).__name__}: {exc}",
                        method=CLEANUP_METHOD,
                    )
                )
                continue
            operations.append(
                Overlay2CleanupRecord(
                    path=candidate.path,
                    result=result,
                    method=CLEANUP_METHOD,
                )
            )
            if result == "DELETED":
                freed_bytes += candidate.size_bytes

        final_scan = await analyze_overlay2(conn)
    return Overlay2CleanupResult(
        **final_scan.model_dump(),
        operation_plan=operation_plan,
        operations=operations,
        freed_bytes=freed_bytes,
    )


def _candidate_is_safe(
    candidate: Overlay2Finding, fresh_scan: Overlay2AnalyzeResult
) -> tuple[bool, str]:
    """Проверить кандидата повторным полным снимком непосредственно перед удалением."""

    if fresh_scan.unsafe or fresh_scan.omitted_findings_count:
        return False, "fresh safety inventory is incomplete"
    fresh = next((item for item in fresh_scan.findings if item.path == candidate.path), None)
    if fresh is None or fresh.state != Overlay2FindingState.SUSPECTED_ORPHAN:
        return False, "candidate gained a reference or disappeared"
    if fresh.fingerprint != candidate.fingerprint:
        return False, "candidate changed after confirmation"
    if not fresh.checks or not all(fresh.checks.values()):
        return False, "candidate no longer passes all orphan checks"
    return True, "candidate passed immediate safety checks"


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
    root_info=$(stat -c '%d|%i|%f' -- {root}/"$object_id") || exit 1
    tree_info=$(find -P {root}/"$object_id" -printf '%b|%T@\\n' | awk -F'|' '
        {{ size += $1 * 512; if ($2 > newest) newest = $2; entries += 1 }}
        END {{
            if (NR == 0) exit 1
            printf "%.0f|%.0f|%d", size, newest * 1000000000, entries - 1
        }}
    ') || exit 1
    printf '%s|%s|%s|%s\\n' "$object_id" "$modified" "$root_info" "$tree_info"
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
        if len(parts) != 8:
            continue
        object_id, modified, device, inode, mode, size, mtime_ns, entries = parts
        if not OVERLAY2_ID_PATTERN.fullmatch(object_id):
            continue
        try:
            age_seconds = max(0.0, now - float(modified))
            fingerprint = Overlay2Fingerprint(
                device=int(device),
                inode=int(inode),
                mode=int(mode, 16),
                size_bytes=max(0, int(float(size))),
                mtime_ns=max(0, int(float(mtime_ns))),
                entries=max(0, int(entries)),
            )
        except ValueError:
            continue
        finding = _classify_finding(
            object_id,
            f"{overlay2_root}/{object_id}",
            fingerprint,
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
    fingerprint: Overlay2Fingerprint,
    age_seconds: float,
    aliases: set[str],
    layerdb_ids: set[str],
    container_ids: set[str],
    process_ids: set[str],
) -> Overlay2Finding:
    """Определить безопасное предварительное состояние одной директории overlay2."""

    checks = {
        "absent_from_layerdb": object_id not in layerdb_ids,
        "absent_from_container_inspect": object_id not in container_ids,
        "absent_from_kernel_and_processes": object_id not in process_ids,
        "absent_from_overlay2_link_index": object_id not in aliases,
        "older_than_grace": age_seconds >= ANALYZE_GRACE_SECONDS,
    }
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
        size_bytes=fingerprint.size_bytes,
        age_seconds=age_seconds,
        state=state,
        confidence=confidence,
        reason=reason,
        checks=checks,
        fingerprint=fingerprint,
        cleanup_method=CLEANUP_METHOD,
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


async def _stage_and_delete_candidate(conn: SSHClientConnection, candidate: Overlay2Finding) -> str:
    """Атомарно переместить проверенный объект в staging-каталог и удалить его."""

    if candidate.fingerprint is None or not OVERLAY2_ID_PATTERN.fullmatch(candidate.object_id):
        raise ValueError("Overlay2 cleanup candidate has no valid fingerprint or identifier")
    overlay_root = candidate.path.rsplit("/", maxsplit=1)[0]
    destination_name = f"{candidate.object_id}.{uuid.uuid4().hex}"
    command = _delete_candidate_command(
        overlay_root,
        candidate.object_id,
        destination_name,
        _fingerprint_value(candidate.fingerprint),
    )
    return await _try_root_command_or_raise(conn, command, "Overlay2 candidate cleanup failed")


def _delete_candidate_command(
    overlay_root: str, object_id: str, destination_name: str, expected: str
) -> str:
    """Построить shell-команду безопасного staging и удаления одного кандидата."""

    return f"""
overlay_root={shlex.quote(overlay_root)}
object_id={shlex.quote(object_id)}
source="$overlay_root/$object_id"
trash="$overlay_root/../.orchestrator-overlay2-trash"
destination="$trash/{destination_name}"
expected={shlex.quote(expected)}

fingerprint() {{
    root_info=$(stat -c '%d|%i|%f' -- "$1") || return 1
    tree_info=$(find -P "$1" -printf '%b|%T@\n' | awk -F'|' '
        {{ size += $1 * 512; if ($2 > newest) newest = $2; entries += 1 }}
        END {{
            if (NR == 0) exit 1
            printf "%.0f|%.0f|%d", size, newest * 1000000000, entries - 1
        }}
    ') || return 1
    printf '%s|%s' "$root_info" "$tree_info"
}}

[ -d "$source" ] && [ ! -L "$source" ] || {{
    printf '%s\n' "candidate is not a real directory" >&2
    exit 2
}}
[ "$(fingerprint "$source")" = "$expected" ] || {{
    printf '%s\n' "candidate changed before staging" >&2
    exit 3
}}
if [ -e "$trash" ] && {{ [ -L "$trash" ] || [ ! -d "$trash" ]; }}; then
    printf '%s\n' "staging path is not a real directory" >&2
    exit 4
fi
mkdir -p -m 700 "$trash"
[ "$(stat -c '%d' "$trash")" = "$(stat -c '%d' "$overlay_root")" ] || {{
    printf '%s\n' "staging path is on another filesystem" >&2
    exit 5
}}
[ ! -e "$destination" ] || {{
    printf '%s\n' "staging destination already exists" >&2
    exit 6
}}
mv -- "$source" "$destination"
if [ "$(fingerprint "$destination")" != "$expected" ]; then
    if [ ! -e "$source" ]; then
        mv -- "$destination" "$source"
        printf '%s\n' "candidate changed during staging and was restored" >&2
    else
        printf '%s\n' "candidate changed during staging and was preserved in staging" >&2
    fi
    exit 7
fi
find -P "$destination" -depth -delete
printf 'DELETED'
"""


@asynccontextmanager
async def _remote_cleanup_lock(conn: SSHClientConnection) -> AsyncIterator[None]:
    """Удерживать удалённую flock-блокировку в течение всего действия очистки."""

    command = f"""
exec 9>{shlex.quote(CLEANUP_LOCK_PATH)}
flock -n 9 || {{ printf 'LOCKED\n'; exit 1; }}
printf 'ACQUIRED\n'
read _
"""
    process = await conn.create_process(_as_root_command(command))
    if process.stdout is None:
        raise RuntimeError("Overlay2 cleanup lock did not provide stdout")
    status = await process.stdout.readline()
    if status != "ACQUIRED\n":
        if process.stdin is not None:
            process.stdin.write_eof()
        await process.wait_closed()
        raise RuntimeError("Another overlay2 cleanup is already running on this host")
    try:
        yield
    finally:
        if process.stdin is not None:
            process.stdin.write("\n")
            process.stdin.write_eof()
        await process.wait_closed()


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

    return await _try_command(conn, _as_root_command(command), source_name, sources)


async def _try_root_command_or_raise(conn: SSHClientConnection, command: str, error: str) -> str:
    """Выполнить root-команду и передать её ошибку вызывающему коду."""

    return await run_command(conn, _as_root_command(command), error=error)


def _as_root_command(command: str) -> str:
    """Обернуть команду для выполнения root-пользователем или через ``sudo -n``."""

    quoted_command = shlex.quote(command)
    return (
        f'if [ "$(id -u)" -eq 0 ]; then sh -c {quoted_command}; '
        f"else sudo -n sh -c {quoted_command}; fi"
    )


def _fingerprint_value(fingerprint: Overlay2Fingerprint) -> str:
    """Сериализовать отпечаток в формат, который сравнивает удалённая shell-команда."""

    return "|".join(
        (
            str(fingerprint.device),
            str(fingerprint.inode),
            format(fingerprint.mode, "x"),
            str(fingerprint.size_bytes),
            str(fingerprint.mtime_ns),
            str(fingerprint.entries),
        )
    )


def _overlay_ids(value: str) -> set[str]:
    """Вернуть возможные идентификаторы физических директорий overlay2 из вывода Docker."""

    pattern = r"(?<![a-z0-9])(?:[a-z0-9]{25}|[a-f0-9]{64})(?:-init)?(?![a-z0-9])"
    return set(re.findall(pattern, value))
