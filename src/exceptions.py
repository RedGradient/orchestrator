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
        super().__init__(f"Хост с идентификатором {host_id} не найден")


class HostIpAlreadyExistsError(Exception):
    """Активный хост с таким IP уже зарегистрирован."""

    def __init__(self, ip: str):
        self.ip = ip
        super().__init__(f"Хост с IP-адресом {ip} уже существует")


class HostsNotFoundError(Exception):
    """Часть хостов, переданных для запуска операции, не существует."""

    def __init__(self, host_ids: list[int]):
        self.host_ids = host_ids
        identifiers = ", ".join(map(str, host_ids))
        super().__init__(f"Не найдены хосты с идентификаторами: {identifiers}")


class HostsWithoutSiteUrlError(Exception):
    """Для части хостов не указан сайт, необходимый для проверки."""

    def __init__(self, hosts: list[tuple[int, str | None, str]]):
        self.host_ids = [host_id for host_id, _, _ in hosts]
        self.hosts = [{"id": host_id, "label": label, "ip": ip} for host_id, label, ip in hosts]
        names = ", ".join(f"{label} ({ip})" if label else ip for _, label, ip in hosts)
        super().__init__(
            f"Чтобы запустить проверку сайта, укажите адрес сайта для следующих хостов: {names}."
        )


class OperationNotFoundError(Exception):
    """Операция не найдена."""

    def __init__(self, operation_id: int):
        self.operation_id = operation_id
        super().__init__(f"Операция с идентификатором {operation_id} не найдена")


class UnsupportedOperationParametersError(Exception):
    """Переданные параметры пока не поддерживаются выбранным действием."""

    def __init__(self, command: str):
        self.command = command
        super().__init__(f"Действие «{command}» не поддерживает параметры")
