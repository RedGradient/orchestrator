import re
import shlex
from dataclasses import dataclass

from asyncssh import SSHClientConnection

from src.schemas import PortCheckItem, PortsCheckResult, ShouldClose
from src.services.helpers.ssh import run_command

DOCKER_PROXY = "docker-proxy"

ALLOWED_SERVICES = {
    "sshd": "SSH должен оставаться доступным для удалённого администрирования.",
    "nginx": "HTTP-сервис может быть доступен из интернета.",
}
SENSITIVE_SERVICES = {
    "postgres": ("PostgreSQL не должен быть доступен из интернета."),
    "redis": ("Redis не должен быть доступен из интернета."),
}


@dataclass(frozen=True)
class ListeningPort:
    """Описывает TCP-порт, прослушиваемый процессом."""

    port: int
    service: str


@dataclass(frozen=True)
class DockerPortProcess:
    """Описывает процесс, связанный с опубликованным Docker-портом."""

    port: int
    container: str
    image: str
    container_port: int
    service: str


async def check_ports(conn: SSHClientConnection) -> PortsCheckResult:
    """Проверяет открытые порты хоста и возвращает рекомендации по их закрытию."""

    # Получить все порты, видимые из интернета
    open_ports = await get_open_ports(conn)

    # Если сервис находится за докер-прокси, то ищем реальный сервис в докере
    port_checks: list[PortCheckItem] = []

    for port in open_ports:
        service = port.service

        # Если сервис находится в докере, извлекаем название сервиса из докера
        if port.service == DOCKER_PROXY:
            if dp := await find_docker_process(conn, port.port):
                if dp.service:
                    service = dp.service

        # Даем рекомендацию по закрытию
        should_close, reason = recommend_port_closure(service)

        port_checks.append(
            PortCheckItem(
                port=port.port,
                service=service,
                is_docker=port.service == DOCKER_PROXY,
                should_close=should_close,
                reason=reason,
            )
        )

    return PortsCheckResult(ports=port_checks)


async def get_open_ports(
    conn: SSHClientConnection,
) -> list[ListeningPort]:
    """Возвращает TCP-порты и процессы, слушающие на всех интерфейсах."""

    output = await run_command(
        conn, "sudo ss -ltnpH", error="Failed to get the list of listening TCP ports"
    )

    ports: dict[tuple[int, str], ListeningPort] = {}

    for line in output.splitlines():
        fields = line.split()

        if len(fields) < 4:
            continue

        local_address = fields[3]

        if not local_address.startswith(("0.0.0.0:", "[::]:")):
            continue

        port = int(local_address.rsplit(":", 1)[1])

        match = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)

        if match:
            process = match.group(1)
        else:
            process = "unknown"

        ports[(port, process)] = ListeningPort(
            port=port,
            service=process,
        )

    return sorted(ports.values(), key=lambda item: (item.port, item.service))


def recommend_port_closure(
    service: str,
) -> tuple[ShouldClose, str]:
    """Возвращает рекомендацию по закрытию обнаруженных внешних портов."""

    for sensitive_service, message in SENSITIVE_SERVICES.items():
        if sensitive_service.lower() in service.lower():
            return ShouldClose.YES, message

    for allowed_service, message in ALLOWED_SERVICES.items():
        if allowed_service.lower() in service.lower():
            return ShouldClose.NO, message

    return (
        ShouldClose.UNKNOWN,
        "Не удалось определить сервис или правила для этого сервиса не настроены.",
    )


def _parse_docker_process(output: str) -> str:
    """Извлекает имя процесса из вывода docker top."""

    lines = output.splitlines()

    if len(lines) < 2:
        return "unknown"

    command = lines[1].split(None, 7)[-1].strip()

    if not command:
        return "unknown"

    return command.split(None, 1)[0]


async def find_docker_process(
    conn: SSHClientConnection,
    port: int,
) -> DockerPortProcess | None:
    """Ищет Docker-контейнер и процесс, связанные с указанным портом."""

    output = await run_command(
        conn,
        "sudo docker ps --format '{{.Names}}\\t{{.Image}}\\t{{.Ports}}'",
    )

    for line in output.splitlines():
        container_name, image, ports = line.split("\t", 2)

        for mapping in ports.split(", "):
            match = re.search(
                rf"(?:0\.0\.0\.0|127\.0\.0\.1|::):{port}->(\d+)/tcp",
                mapping,
            )

            if not match:
                continue

            container_port = int(match.group(1))

            process_output = await run_command(
                conn,
                f"sudo docker top {shlex.quote(container_name)}",
            )

            process = _parse_docker_process(process_output)

            return DockerPortProcess(
                port=port,
                container=container_name,
                image=image,
                container_port=container_port,
                service=process,
            )

    return None
