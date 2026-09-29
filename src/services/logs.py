import json
import shlex
from pathlib import Path

from asyncssh import SSHClientConnection

from src.schemas import (
    DockerDaemonResult,
    Fail2BanResult,
    JournaldResult,
    LogrotateResult,
    LogsCleanupResult,
    PackageInstallResult,
)
from src.services.helpers.ssh import run_command

LOG_PATHS = [
    "/var/log/btmp",
]

JOURNALD_MAX_USE = "200M"
JOURNALD_MAX_FILE_SIZE = "50M"

FAIL2BAN_BANTIME = "1h"
FAIL2BAN_FINDTIME = "10m"
FAIL2BAN_MAX_RETRY = 5


async def logs_cleanup(conn: SSHClientConnection) -> LogsCleanupResult:
    """Устанавливает и настраивает инструменты очистки системных логов."""

    result = LogsCleanupResult()

    result.logrotate = await install_logrotate(conn)
    result.fail2ban = await install_fail2ban(conn)

    # Включение ротации для log-файлов, указанных в LOG_PATHS.
    for log_path in LOG_PATHS:
        logrotate_result = await configure_logrotate(conn, log_path, rotate_now=True)
        freed_bytes = await cleanup_rotated_log(conn, log_path, max_size_mb=10, keep_size_mb=10)
        result.logrotate_config.append(logrotate_result)
        result.freed_bytes += freed_bytes

    # Конфигурация логов journald.
    result.journald = await configure_journald(conn)

    # Настройка fail2ban.
    result.fail2ban_config = await configure_fail2ban(conn)

    # Конфигурация логов dockerd.
    result.dockerd = await configure_docker_daemon(conn)

    return result


async def configure_docker_daemon(
    conn: SSHClientConnection,
) -> DockerDaemonResult:
    """Настраивает ротацию логов Docker daemon."""

    try:
        config = {
            "log-driver": "json-file",
            "log-opts": {
                "max-size": "50m",
                "max-file": "3",
            },
        }

        config_json = json.dumps(config, indent=4)

        # Создаём конфигурацию Docker daemon.
        await run_command(
            conn,
            f"printf '%s\\n' {shlex.quote(config_json)} | "
            "sudo tee /etc/docker/daemon.json > /dev/null",
            error="Failed to configure Docker daemon",
        )

        # Перезапускаем Docker для применения конфигурации.
        await run_command(
            conn,
            "sudo systemctl restart docker",
            error="Failed to restart Docker",
        )

        return DockerDaemonResult(
            success=True,
        )

    except Exception as exc:
        return DockerDaemonResult(
            success=False,
            error=str(exc),
        )


async def install_logrotate(
    conn: SSHClientConnection,
) -> PackageInstallResult:
    """Проверяет наличие logrotate и устанавливает его при отсутствии."""

    try:
        stdout = await run_command(
            conn,
            "command -v logrotate || true",
            error="Failed to check logrotate",
        )

        if stdout.strip():
            return PackageInstallResult(
                already_installed=True,
                success=True,
            )

        await run_command(
            conn,
            "sudo DEBIAN_FRONTEND=noninteractive apt-get update",
            error="Failed to update apt package lists",
        )

        await run_command(
            conn,
            (
                "sudo DEBIAN_FRONTEND=noninteractive "
                "apt-get install -y "
                '-o Dpkg::Options::="--force-confold" '
                "logrotate"
            ),
            error="Failed to install logrotate",
        )

        return PackageInstallResult(
            already_installed=False,
            success=True,
        )

    except Exception as exc:
        return PackageInstallResult(
            already_installed=False,
            success=False,
            error=str(exc),
        )


async def configure_logrotate(
    conn: SSHClientConnection,
    log_path: str,
    rotate_now: bool = False,
) -> LogrotateResult:
    """Создаёт конфигурацию logrotate для указанного лог-файла."""

    config_path = f"/etc/logrotate.d/{Path(log_path).name}"

    config = f"""\
{log_path} {{
daily
size 50M
rotate 4
compress
delaycompress
missingok
notifempty
}}
"""

    try:
        command = f"echo {shlex.quote(config)} | sudo tee {shlex.quote(config_path)} > /dev/null"
        await run_command(
            conn,
            command,
            error="Failed to configure logrotate",
        )

        # Принудительная ротация
        if rotate_now:
            await run_command(
                conn,
                f"sudo logrotate -f {shlex.quote(config_path)}",
                error="Failed to rotate log",
            )

        return LogrotateResult(
            path=log_path,
            success=True,
        )

    except Exception as exc:
        return LogrotateResult(
            path=log_path,
            success=False,
            error=str(exc),
        )


async def install_fail2ban(
    conn: SSHClientConnection,
) -> PackageInstallResult:
    """Проверяет наличие fail2ban и устанавливает его при отсутствии."""

    try:
        stdout = await run_command(
            conn,
            "command -v fail2ban-client || true",
            error="Failed to check fail2ban",
        )

        if stdout.strip():
            return PackageInstallResult(
                already_installed=True,
                success=True,
            )

        await run_command(
            conn,
            "sudo apt-get update && sudo apt-get install -y fail2ban",
            error="Failed to install fail2ban",
        )

        return PackageInstallResult(
            already_installed=False,
            success=True,
        )

    except Exception as exc:
        return PackageInstallResult(
            already_installed=False,
            success=False,
            error=str(exc),
        )


async def configure_fail2ban(conn: SSHClientConnection) -> Fail2BanResult:
    """Настраивает fail2ban для защиты SSH от перебора паролей"""

    config = f"""\
[DEFAULT]
bantime = {FAIL2BAN_BANTIME}
findtime = {FAIL2BAN_FINDTIME}
maxretry = {FAIL2BAN_MAX_RETRY}

[sshd]
enabled = true
"""

    try:
        # Пишем конфиг в /etc/fail2ban/jail.local
        await run_command(
            conn,
            f"echo {shlex.quote(config)} | sudo tee /etc/fail2ban/jail.local > /dev/null",
            error="Failed to configure fail2ban",
        )

        # Включаем fail2ban и заносим в автозагрузку
        await run_command(
            conn,
            "sudo systemctl enable --now fail2ban",
            error="Failed to start fail2ban",
        )

        return Fail2BanResult(
            success=True,
        )
    except Exception as exc:
        return Fail2BanResult(success=False, error=str(exc))


async def configure_journald(
    conn: SSHClientConnection,
) -> JournaldResult:
    """Ограничивает размер журналов systemd-journald."""

    config = f"""\
[Journal]
SystemMaxUse={JOURNALD_MAX_USE}
SystemMaxFileSize={JOURNALD_MAX_FILE_SIZE}
"""

    try:
        # Создаём директорию для drop-in конфигурации journald.
        await run_command(
            conn,
            "sudo mkdir -p /etc/systemd/journald.conf.d",
            error="Failed to create journald config directory",
        )

        # Создаём конфигурацию с ограничениями размера журналов.
        await run_command(
            conn,
            f"printf '%s\\n' {shlex.quote(config)} | "
            "sudo tee /etc/systemd/journald.conf.d/limits.conf > /dev/null",
            error="Failed to configure journald",
        )

        # Перезапускаем journald для применения новой конфигурации.
        await run_command(
            conn,
            "sudo systemctl restart systemd-journald",
            error="Failed to restart systemd-journald",
        )

        return JournaldResult(
            success=True,
            system_max_use=JOURNALD_MAX_USE,
            system_max_file_size=JOURNALD_MAX_FILE_SIZE,
        )

    except Exception as exc:
        return JournaldResult(
            success=False,
            error=str(exc),
        )


async def cleanup_rotated_log(
    conn: SSHClientConnection,
    log_path: str,
    max_size_mb: int = 50,
    keep_size_mb: int = 10,
) -> int:
    """Очищает ротированный лог и возвращает освобождённое место в байтах."""

    rotated_path = f"{log_path}.1"

    max_size_bytes = max_size_mb * 1024 * 1024
    keep_size_bytes = keep_size_mb * 1024 * 1024

    command = (
        f"if [ -f {shlex.quote(rotated_path)} ]; then "
        f"size_before=$(stat -c %s {shlex.quote(rotated_path)}); "
        f'if [ "$size_before" -gt {max_size_bytes} ]; then '
        f"tail -c {keep_size_bytes} {shlex.quote(rotated_path)} "
        f"> /tmp/logrotate_cleanup && "
        f"cat /tmp/logrotate_cleanup > {shlex.quote(rotated_path)} && "
        f"rm -f /tmp/logrotate_cleanup; "
        f"fi; "
        f"size_after=$(stat -c %s {shlex.quote(rotated_path)}); "
        f"echo $((size_before - size_after)); "
        f"else "
        f"echo 0; "
        f"fi"
    )

    stdout = await run_command(
        conn,
        command,
        error="Failed to cleanup rotated log",
    )

    return int(stdout.strip())
