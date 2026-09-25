from asyncssh import SSHClientConnection


async def run_command(
    conn: SSHClientConnection,
    command: str,
    *,
    error: str = "Command failed",
) -> str:
    """Выполнить команду на удалённом VPS и вернуть stdout."""

    result = await conn.run(command, check=False)
    if result.exit_status != 0:
        raise RuntimeError(f"{error}: {result.stderr.strip()}")
    return result.stdout.strip()
