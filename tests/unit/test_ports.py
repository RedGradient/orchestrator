import pytest

from src.schemas import ShouldClose
from src.services.ports import _parse_docker_process, recommend_port_closure


@pytest.mark.parametrize(
    ("service", "expected_status"),
    [
        ("postgres", ShouldClose.YES),
        ("redis", ShouldClose.YES),
    ],
)
def test_recommend_port_closure_sensitive_service(
    service: str,
    expected_status: ShouldClose,
) -> None:
    """Рекомендует закрыть порт чувствительного сервиса."""

    should_close, _ = recommend_port_closure(service)

    assert should_close == expected_status


@pytest.mark.parametrize(
    "service",
    ["Postgres", "POSTGRES", "Postgres:16", "redisredis-server", "REDIS-SERVER"],
)
def test_recommend_port_closure_case_insensitive(service: str) -> None:
    """Определяет чувствительные сервисы независимо от регистра."""

    should_close, _ = recommend_port_closure(service)

    assert should_close == ShouldClose.YES


def test_recommend_port_closure_docker_proxy() -> None:
    """Не даёт рекомендации для промежуточного docker-proxy."""

    should_close, _ = recommend_port_closure("docker-proxy")

    assert should_close == ShouldClose.UNKNOWN


@pytest.mark.parametrize("service", ["sshd", "nginx"])
def test_recommend_port_closure_allowed_service(service: str) -> None:
    """Не рекомендует закрывать порт разрешённого сервиса."""

    should_close, _ = recommend_port_closure(service)

    assert should_close == ShouldClose.NO


@pytest.mark.parametrize("service", ["docker", "unknown", "custom-service"])
def test_recommend_port_closure_unknown_service(service: str) -> None:
    """Возвращает неопределённую рекомендацию для неизвестного сервиса."""

    should_close, _ = recommend_port_closure(service)

    assert should_close == ShouldClose.UNKNOWN


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (
            "UID                 PID                 PPID                C                   "
            "STIME               TTY                 TIME                CMD\n"
            "999                 22095               22072               0                   "
            "08:42               ?                   00:01:58            redis-server *:6379",
            "redis-server",
        ),
        (
            "UID                 PID                 PPID                C                   "
            "STIME               TTY                 TIME                CMD\n"
            "999                 22095               22072               0                   "
            "08:42               ?                   00:01:58            redis-server",
            "redis-server",
        ),
        (
            "UID                 PID                 PPID                C                   "
            "STIME               TTY                 TIME                CMD\n"
            "999                 22095               22072               0                   "
            "08:42               ?                   00:01:58            /usr/bin/redis-server *:6379",
            "/usr/bin/redis-server",
        ),
        (
            "UID                 PID                 PPID                C                   "
            "STIME               TTY                 TIME                CMD",
            "unknown",
        ),
        ("", "unknown"),
    ],
)
def test_parse_docker_process(output: str, expected: str) -> None:
    """Извлекает имя процесса из вывода docker top."""

    assert _parse_docker_process(output) == expected
