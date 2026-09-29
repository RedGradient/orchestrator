import json
import shlex

import pytest
from asyncssh import SSHClientConnection

from src.services.helpers.ssh import run_command
from src.services.logs import (
    cleanup_rotated_log,
    configure_docker_daemon,
    configure_fail2ban,
    configure_journald,
    configure_logrotate,
    install_fail2ban,
    install_logrotate,
    logs_cleanup,
)

pytestmark = pytest.mark.integration

MIB = 1024 * 1024
BTMP = "/var/log/btmp"

LOGROTATE_CONFIG = """\
/var/log/btmp {
daily
size 50M
rotate 4
compress
delaycompress
missingok
notifempty
}
"""

JOURNALD_CONFIG = """\
[Journal]
SystemMaxUse=200M
SystemMaxFileSize=50M
"""

FAIL2BAN_CONFIG = """\
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
"""


async def remote_text(conn: SSHClientConnection, path: str) -> str:
    return await run_command(conn, f"sudo cat {shlex.quote(path)}")


async def assert_active(conn: SSHClientConnection, unit: str) -> None:
    state = await run_command(conn, f"systemctl is-active {shlex.quote(unit)}")
    assert state == "active"


@pytest.mark.asyncio
async def test_install_logrotate_when_present(ssh_conn: SSHClientConnection) -> None:
    result = await install_logrotate(ssh_conn)

    assert result.success
    assert result.already_installed is True
    assert result.error is None


@pytest.mark.asyncio
async def test_install_fail2ban_when_present(ssh_conn: SSHClientConnection) -> None:
    result = await install_fail2ban(ssh_conn)

    assert result.success
    assert result.already_installed is True
    assert result.error is None


@pytest.mark.asyncio
async def test_install_logrotate_when_missing(ssh_conn: SSHClientConnection) -> None:
    await run_command(
        ssh_conn,
        "sudo DEBIAN_FRONTEND=noninteractive apt-get remove -y logrotate",
    )

    result = await install_logrotate(ssh_conn)

    assert result.success, result.error
    assert result.already_installed is False
    binary = await run_command(ssh_conn, "command -v logrotate")
    assert binary.endswith("/logrotate")


@pytest.mark.asyncio
async def test_configure_logrotate_writes_config(ssh_conn: SSHClientConnection) -> None:
    result = await configure_logrotate(ssh_conn, BTMP)

    assert result.success, result.error
    assert result.path == BTMP
    assert await remote_text(ssh_conn, "/etc/logrotate.d/btmp") == LOGROTATE_CONFIG.strip()


@pytest.mark.asyncio
async def test_configure_logrotate_rotates_now(ssh_conn: SSHClientConnection) -> None:
    marker = "rotate-marker"
    await run_command(
        ssh_conn,
        f"sudo rm -f {shlex.quote(BTMP)} {shlex.quote(BTMP + '.1')} && "
        f"printf '%s\\n' {shlex.quote(marker)} | sudo tee {shlex.quote(BTMP)} > /dev/null",
    )

    result = await configure_logrotate(ssh_conn, BTMP, rotate_now=True)

    assert result.success, result.error
    rotated = await remote_text(ssh_conn, f"{BTMP}.1")
    assert marker in rotated


@pytest.mark.asyncio
async def test_cleanup_rotated_log_when_missing(ssh_conn: SSHClientConnection) -> None:
    await run_command(ssh_conn, f"sudo rm -f {shlex.quote(BTMP + '.1')}")

    freed = await cleanup_rotated_log(ssh_conn, BTMP, max_size_mb=1, keep_size_mb=1)

    assert freed == 0


@pytest.mark.asyncio
async def test_cleanup_rotated_log_below_threshold(ssh_conn: SSHClientConnection) -> None:
    rotated = f"{BTMP}.1"
    await run_command(
        ssh_conn,
        f"printf small | sudo tee {shlex.quote(rotated)} > /dev/null",
    )
    size_before = await run_command(ssh_conn, f"sudo stat -c %s {shlex.quote(rotated)}")

    freed = await cleanup_rotated_log(ssh_conn, BTMP, max_size_mb=1, keep_size_mb=1)

    size_after = await run_command(ssh_conn, f"sudo stat -c %s {shlex.quote(rotated)}")
    assert freed == 0
    assert size_before == size_after


@pytest.mark.asyncio
async def test_cleanup_rotated_log_above_threshold(ssh_conn: SSHClientConnection) -> None:
    rotated = f"{BTMP}.1"
    await run_command(
        ssh_conn,
        f"sudo dd if=/dev/zero of={shlex.quote(rotated)} bs={2 * MIB} count=1 status=none && "
        f"sudo chown testuser:testuser {shlex.quote(rotated)}",
    )

    freed = await cleanup_rotated_log(ssh_conn, BTMP, max_size_mb=1, keep_size_mb=1)

    size_after = int(await run_command(ssh_conn, f"stat -c %s {shlex.quote(rotated)}"))
    assert freed == MIB
    assert size_after == MIB


@pytest.mark.asyncio
async def test_configure_journald(ssh_conn: SSHClientConnection) -> None:
    result = await configure_journald(ssh_conn)

    assert result.success, result.error
    assert result.system_max_use == "200M"
    assert result.system_max_file_size == "50M"
    text = await remote_text(ssh_conn, "/etc/systemd/journald.conf.d/limits.conf")
    assert text == JOURNALD_CONFIG.strip()
    await assert_active(ssh_conn, "systemd-journald")


@pytest.mark.asyncio
async def test_configure_fail2ban(ssh_conn: SSHClientConnection) -> None:
    result = await configure_fail2ban(ssh_conn)

    assert result.success, result.error
    text = await remote_text(ssh_conn, "/etc/fail2ban/jail.local")
    assert text == FAIL2BAN_CONFIG.strip()
    await assert_active(ssh_conn, "fail2ban")


@pytest.mark.asyncio
async def test_configure_docker_daemon(
    ssh_conn: SSHClientConnection,
) -> None:
    result = await configure_docker_daemon(ssh_conn)

    assert result.success, result.error

    daemon_config = json.loads(await remote_text(ssh_conn, "/etc/docker/daemon.json"))

    assert daemon_config == {
        "log-driver": "json-file",
        "log-opts": {
            "max-size": "50m",
            "max-file": "3",
        },
    }

    logging_driver = await run_command(
        ssh_conn,
        "sudo docker info --format '{{.LoggingDriver}}'",
    )

    assert logging_driver == "json-file"

    container_name = "logs-config-test"

    await run_command(
        ssh_conn,
        f"sudo docker create --name {container_name} alpine",
    )

    try:
        inspect_result = await run_command(
            ssh_conn,
            f"sudo docker inspect {container_name}",
        )

        payload = json.loads(inspect_result)
        log_config = payload[0]["HostConfig"]["LogConfig"]

        assert log_config == {
            "Type": "json-file",
            "Config": {
                "max-size": "50m",
                "max-file": "3",
            },
        }

    finally:
        await run_command(
            ssh_conn,
            f"sudo docker rm {container_name}",
        )

    await assert_active(ssh_conn, "docker")


@pytest.mark.asyncio
async def test_logs_cleanup(ssh_conn: SSHClientConnection) -> None:
    await run_command(
        ssh_conn,
        f"sudo rm -f {shlex.quote(BTMP)} {shlex.quote(BTMP + '.1')} && "
        f"sudo dd if=/dev/zero of={shlex.quote(BTMP)} bs={11 * MIB} count=1 status=none && "
        f"sudo chown testuser:testuser {shlex.quote(BTMP)}",
    )

    result = await logs_cleanup(ssh_conn)

    assert result.logrotate is not None
    assert result.logrotate.success, result.logrotate.error
    assert result.logrotate.already_installed is True
    assert result.fail2ban is not None
    assert result.fail2ban.success, result.fail2ban.error
    assert result.fail2ban.already_installed is True
    assert len(result.logrotate_config) == 1
    assert result.logrotate_config[0].success, result.logrotate_config[0].error
    assert result.logrotate_config[0].path == BTMP
    assert result.journald is not None
    assert result.journald.success, result.journald.error
    assert result.journald.system_max_use == "200M"
    assert result.journald.system_max_file_size == "50M"
    assert result.fail2ban_config is not None
    assert result.fail2ban_config.success, result.fail2ban_config.error
    assert result.dockerd is not None
    assert result.dockerd.success, result.dockerd.error
    assert result.freed_bytes > 0
    size_after = int(await run_command(ssh_conn, f"stat -c %s {shlex.quote(BTMP + '.1')}"))
    assert size_after == 10 * MIB
