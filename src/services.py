from src.checkers import check_http, check_ssl, check_sitemap, check_robots
from src.schemas import CheckResponse, CheckRequest


async def make_checks(request: CheckRequest) -> CheckResponse:
    domain = request.url.host

    assert domain is not None

    http_result = check_http(str(request.url))

    # Домен/сервер недоступен — остальные проверки выполнять бессмысленно
    if not http_result.ok:
        return CheckResponse(
            url=request.url,
            domain=domain,
            http=http_result,
        )

    ssl_result = check_ssl(domain)
    robots_result = check_robots(domain)
    sitemap_result = check_sitemap(domain)

    return CheckResponse(
        url=request.url,
        domain=domain,

        http=http_result,
        ssl=ssl_result,
        robots=robots_result,
        sitemap=sitemap_result,
    )