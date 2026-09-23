from datetime import datetime, timezone

import dns.resolver
import httpx
import socket
import ssl

from src.helpers import _format_issuer, _inspect_robots, _inspect_sitemap, _strip_errno
from src.schemas import HttpCheckResult, RobotsCheckResult, SslCheckResult, SitemapCheckResult


def resolve_domain(domain: str) -> list[tuple[str, int]]:
    """Возвращает [ip, port], ассоциированные с доменом"""

    answers = dns.resolver.resolve(domain, "A")
    return [answer.address for answer in answers]


def check_http(url: str) -> HttpCheckResult:
    """Возвращает результат HTTP запроса по переданному URL"""

    try:
        response = httpx.get(
            url,
            timeout=10,
            follow_redirects=True,
            verify=False,
        )

        return HttpCheckResult(
            ok=True,
            status_code=response.status_code,
            response_time_ms=response.elapsed.seconds,
        )

    except httpx.TimeoutException:
        return HttpCheckResult(
            ok=False,
            error="timeout",
        )

    except httpx.RequestError as e:
        return HttpCheckResult(
            ok=False,
            error=_strip_errno(str(e)),
        )



def check_ssl(domain: str, port: int = 443) -> SslCheckResult:
    """TLS handshake"""

    context = ssl.create_default_context()

    try:
        with socket.create_connection(
            (domain, port),
            timeout=10,
        ) as sock:
            with context.wrap_socket(
                sock,
                server_hostname=domain,
            ) as ssock:
                certificate = ssock.getpeercert()
                expires_at = datetime.fromtimestamp(
                    ssl.cert_time_to_seconds(certificate["notAfter"]),
                    tz=timezone.utc,
                )

                return SslCheckResult(
                    ok=True,
                    version=ssock.version(),
                    issuer=_format_issuer(certificate),
                    expires_at=expires_at,
                    days_remaining=(expires_at - datetime.now(timezone.utc)).days,
                    error=None,
                )

    except TimeoutError:
        return SslCheckResult(
            ok=False,
            error="timeout",
        )

    except socket.gaierror as e:
        return SslCheckResult(
            ok=False,
            error=_strip_errno(str(e)),
        )

    except ConnectionError as e:
        return SslCheckResult(
            ok=False,
            error=_strip_errno(str(e)),
        )

    except ssl.SSLCertVerificationError as e:
        return SslCheckResult(
            ok=False,
            error=_strip_errno(str(e)),
        )

    except ssl.SSLError as e:
        return SslCheckResult(
            ok=False,
            error=_strip_errno(str(e)),
        )

    except OSError as e:
        return SslCheckResult(
            ok=False,
            error=_strip_errno(str(e)),
        )



def check_robots(domain: str) -> RobotsCheckResult:
    """Загружает robots.txt домена и проверяет, доступен ли файл и правильно ли он составлен."""

    url = f"https://{domain}/robots.txt"

    try:
        response = httpx.get(
            url,
            timeout=10,
            follow_redirects=True,
            verify=False,
        )

        if response.status_code == 200:
            valid, errors, warnings, sitemaps = _inspect_robots(response.text)
        else:
            valid, errors, warnings, sitemaps = None, [], [], []

        return RobotsCheckResult(
            available=response.status_code == 200,
            status_code=response.status_code,
            valid=valid,
            errors=errors,
            warnings=warnings,
            sitemaps=sitemaps,
        )

    except httpx.TimeoutException:
        return RobotsCheckResult(
            available=False,
            error="timeout",
        )

    except httpx.RequestError as e:
        return RobotsCheckResult(
            available=False,
            error=_strip_errno(str(e)),
        )


def check_sitemap(domain: str) -> SitemapCheckResult:
    """Загружает sitemap.xml домена и проверяет, доступен ли файл и правильно ли он составлен."""

    url = f"https://{domain}/sitemap.xml"

    try:
        response = httpx.get(
            url,
            timeout=10,
            follow_redirects=True,
            verify=False,
        )

        if response.status_code != 200:
            return SitemapCheckResult(
                available=False,
                status_code=response.status_code,
                valid=None,
                errors=[],
                warnings=[],
                url_count=None,
            )

        valid, errors, warnings, url_count = _inspect_sitemap(response.text)
        return SitemapCheckResult(
            available=True,
            status_code=response.status_code,
            valid=valid,
            errors=errors,
            warnings=warnings,
            url_count=url_count,
        )

    except httpx.TimeoutException:
        return SitemapCheckResult(
            available=False,
            error="timeout",
        )

    except httpx.RequestError as e:
        return SitemapCheckResult(
            available=False,
            error=_strip_errno(str(e)),
        )