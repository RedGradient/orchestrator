from asyncssh import SSHClientConnection

from src.exceptions import CommandError, CommandOutputError


async def run_command(
    conn: SSHClientConnection,
    command: str,
    *,
    error: str = "Command failed",
) -> str:
    """Выполнить команду на удалённом VPS и вернуть stdout."""

    result = await conn.run(command, check=False)

    host = conn.get_extra_info("host")
    if not isinstance(host, str):
        raise RuntimeError("Не удалось определить host SSH-соединения")

    if result.exit_status != 0:
        if not isinstance(result.stderr, str):
            raise CommandOutputError(
                "Команда вернула stderr в неподдерживаемом формате",
                host=host,
            )

        raise CommandError(
            f"{error}: {result.stderr.strip()}",
            host=host,
        )

    if not isinstance(result.stdout, str):
        raise CommandOutputError(
            "Команда вернула stdout в неподдерживаемом формате",
            host=host,
        )

    return result.stdout.strip()