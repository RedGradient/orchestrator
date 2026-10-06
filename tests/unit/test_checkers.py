import socket
import ssl

import httpx
import pytest

from src import checkers


class StubAsyncClient:
    """Минимальная замена httpx.AsyncClient с заранее заданным результатом GET."""

    def __init__(self, outcome: httpx.Response | Exception) -> None:
        self.outcome = outcome

    async def __aenter__(self) -> StubAsyncClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, _: str) -> httpx.Response:
        """Вернуть подготовленный ответ или возбудить подготовленную ошибку."""

        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _stub_http_client(monkeypatch: pytest.MonkeyPatch, outcome: httpx.Response | Exception) -> None:
    """Подменить HTTP-клиент проверок ответом или ошибкой без сетевого запроса."""

    monkeypatch.setattr(checkers.httpx, "AsyncClient", lambda **_: StubAsyncClient(outcome))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (httpx.TimeoutException("request timed out"), "timeout"),
        (httpx.ConnectError("[Errno 111] Connection refused"), "Connection refused"),
    ],
)
async def test_check_http_returns_readable_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception, expected_error: str
) -> None:
    """Возвращает нормализованную ошибку для таймаута и ошибки соединения."""

    _stub_http_client(monkeypatch, error)

    result = await checkers.check_http("https://example.test")

    assert result.ok is False
    assert result.error == expected_error


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (ssl.SSLCertVerificationError(1, "untrusted certificate"), "untrusted certificate"),
        (ConnectionRefusedError(111, "Connection refused"), "Connection refused"),
    ],
)
def test_check_ssl_returns_error_for_invalid_or_unavailable_tls(
    monkeypatch: pytest.MonkeyPatch, error: OSError, expected_error: str
) -> None:
    """Сообщает об ошибке недоверенного сертификата и отсутствующего TLS-сервиса."""

    def fail_connection(*_: object, **__: object) -> socket.socket:
        raise error

    monkeypatch.setattr(checkers.socket, "create_connection", fail_connection)

    result = checkers.check_ssl("example.test")

    assert result.ok is False
    assert result.error == expected_error


@pytest.mark.asyncio
async def test_check_robots_reports_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Считает robots.txt недоступным, если сервер возвращает 404 по HTTP и HTTPS."""

    _stub_http_client(monkeypatch, httpx.Response(404))

    result = await checkers.check_robots("example.test")

    assert result.available is False
    assert result.error == "robots.txt is not available"


@pytest.mark.asyncio
async def test_check_robots_accepts_empty_file_with_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Считает пустой robots.txt доступным и добавляет предупреждение."""

    _stub_http_client(monkeypatch, httpx.Response(200, text=""))

    result = await checkers.check_robots("example.test")

    assert result.available is True
    assert result.valid is True
    assert result.errors == []
    assert result.warnings == ["Файл robots.txt пустой"]


@pytest.mark.asyncio
async def test_check_robots_reports_invalid_syntax(monkeypatch: pytest.MonkeyPatch) -> None:
    """Возвращает ошибку синтаксиса для некорректной строки robots.txt."""

    _stub_http_client(monkeypatch, httpx.Response(200, text="not a directive"))

    result = await checkers.check_robots("example.test")

    assert result.available is True
    assert result.valid is False
    assert result.errors == ["Строка 1: ожидается директива вида «имя: значение»"]


@pytest.mark.asyncio
async def test_check_sitemap_reports_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Считает sitemap.xml недоступным, если сервер возвращает 404 по HTTP и HTTPS."""

    _stub_http_client(monkeypatch, httpx.Response(404))

    result = await checkers.check_sitemap("example.test")

    assert result.available is False
    assert result.status_code is None
    assert result.error == "sitemap.xml is not available"


@pytest.mark.asyncio
async def test_check_sitemap_reports_invalid_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    """Возвращает ошибку валидации для sitemap.xml с некорректным XML."""

    _stub_http_client(monkeypatch, httpx.Response(200, text="<urlset>"))

    result = await checkers.check_sitemap("example.test")

    assert result.available is True
    assert result.valid is False
    assert result.errors
    assert result.errors[0].startswith("Некорректный XML:")
