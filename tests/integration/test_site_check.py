import pytest
from pydantic import HttpUrl

from src.services.checker import make_checks
from tests.integration.conftest import SiteCheckServer


@pytest.mark.asyncio
@pytest.mark.integration
async def test_make_checks_succeeds_for_site_with_http_tls_robots_and_sitemap(
    site_check_server: SiteCheckServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Проверяет Site Check на локальном сайте с HTTP, TLS, robots.txt и sitemap.xml."""

    # Проверка TLS должна доверять только CA, который сгенерировал тестовый контейнер.
    monkeypatch.setenv("SSL_CERT_FILE", str(site_check_server.ca_certificate))

    result = await make_checks(HttpUrl(site_check_server.url))

    assert result.domain == site_check_server.domain

    assert result.http is not None
    assert result.http.ok is True
    assert result.http.status_code == 200
    assert result.http.response_time_ms is not None

    assert result.ssl is not None
    assert result.ssl.ok is True
    assert result.ssl.version is not None
    assert result.ssl.issuer is not None
    assert result.ssl.expires_at is not None
    assert result.ssl.days_remaining is not None

    assert result.robots is not None
    assert result.robots.available is True
    assert result.robots.status_code == 200
    assert result.robots.valid is True
    assert result.robots.errors == []
    assert [str(url) for url in result.robots.sitemaps] == [f"{site_check_server.url}/sitemap.xml"]

    assert result.sitemap is not None
    assert result.sitemap.available is True
    assert result.sitemap.status_code == 200
    assert result.sitemap.valid is True
    assert result.sitemap.errors == []
    assert result.sitemap.url_count == 2
