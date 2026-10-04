import asyncio

from pydantic import HttpUrl

from src.checkers import check_http, check_robots, check_sitemap, check_ssl
from src.schemas import CheckResponse


async def make_checks(url: HttpUrl) -> CheckResponse:
    """
    Выполняет проверку сайта.

    Проверяет:

    - доступность сайта по HTTP;
    - корректность SSL-сертификата;
    - наличие и доступность robots.txt;
    - наличие и доступность sitemap.

    Если сайт недоступен по HTTP, остальные проверки не выполняются.
    """

    domain = url.host

    assert domain is not None

    http_result = await check_http(str(url))

    # Домен/сервер недоступен — остальные проверки выполнять бессмысленно
    if not http_result.ok:
        return CheckResponse(
            url=url,
            domain=domain,
            http=http_result,
        )

    robots_result, sitemap_result = await asyncio.gather(
        check_robots(domain),
        check_sitemap(domain),
    )
    ssl_result = check_ssl(domain)

    return CheckResponse(
        url=url,
        domain=domain,
        http=http_result,
        ssl=ssl_result,
        robots=robots_result,
        sitemap=sitemap_result,
    )
