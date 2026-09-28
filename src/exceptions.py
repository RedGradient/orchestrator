class CommandOutputError(Exception):
    """Команда завершилась успешно, но её stdout имеет неподдерживаемый формат."""

    def __init__(self, message: str, *, host: str) -> None:
        super().__init__(message)
        self.host = host


class CommandError(Exception):
    """Это исключение выбрасывается при какой-либо ошибке в выполнении SSH команды"""

    def __init__(self, message: str, *, host: str) -> None:
        super().__init__(message)
        self.host = host


class HostNotFoundError(Exception):
    """Хост не найден в базе данных"""

    def __init__(self, host_id: int):
        self.host_id = host_id
        super().__init__(f"Host with id {host_id} not found")
