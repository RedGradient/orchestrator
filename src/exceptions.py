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


class HostsNotFoundError(Exception):
    """Часть хостов, переданных для запуска операции, не существует."""

    def __init__(self, host_ids: list[int]):
        self.host_ids = host_ids
        super().__init__(f"Hosts with ids {host_ids} not found")


class OperationNotFoundError(Exception):
    """Операция не найдена."""

    def __init__(self, operation_id: int):
        self.operation_id = operation_id
        super().__init__(f"Operation with id {operation_id} not found")


class UnsupportedOperationParametersError(Exception):
    """Переданные параметры пока не поддерживаются выбранным действием."""

    def __init__(self, command: str):
        self.command = command
        super().__init__(f"Command {command!r} does not support parameters")
