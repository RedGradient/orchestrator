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
