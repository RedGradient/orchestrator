import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.checkers import check_http, check_robots, check_sitemap, check_ssl
from src.models import Check
from src.schemas import CheckHistoryItem, CheckRequest, CheckResponse


async def make_checks(request: CheckRequest) -> CheckResponse:
    """
    Выполняет проверку сайта.

    Проверяет:

    - доступность сайта по HTTP;
    - корректность SSL-сертификата;
    - наличие и доступность robots.txt;
    - наличие и доступность sitemap.

    Если сайт недоступен по HTTP, остальные проверки не выполняются.
    """

    domain = request.url.host

    assert domain is not None

    http_result = await check_http(str(request.url))

    # Домен/сервер недоступен — остальные проверки выполнять бессмысленно
    if not http_result.ok:
        return CheckResponse(
            url=request.url,
            domain=domain,
            http=http_result,
        )

    robots_result, sitemap_result = await asyncio.gather(
        check_robots(domain),
        check_sitemap(domain),
    )
    ssl_result = check_ssl(domain)

    return CheckResponse(
        url=request.url,
        domain=domain,
        http=http_result,
        ssl=ssl_result,
        robots=robots_result,
        sitemap=sitemap_result,
    )


async def list_checks(session: AsyncSession, limit: int = 40) -> list[CheckHistoryItem]:
    """Возвращает последние проверки, новые сверху."""

    rows = (
        await session.scalars(select(Check).order_by(Check.created_at.desc()).limit(limit))
    ).all()
    return [
        CheckHistoryItem(
            id=row.id,
            created_at=row.created_at,
            trigger=row.trigger.value,
            result=CheckResponse.model_validate(row.data),
        )
        for row in rows
    ]
