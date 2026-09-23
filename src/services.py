from sqlalchemy import select
from sqlalchemy.orm import Session

from src.checkers import check_http, check_ssl, check_sitemap, check_robots
from src.models import Check, CheckTrigger, Site
from src.schemas import CheckHistoryItem, CheckResponse, CheckRequest


async def make_checks(
        request: CheckRequest,
        session: Session,
        trigger: CheckTrigger = CheckTrigger.MANUAL
) -> CheckResponse:
    domain = request.url.host

    assert domain is not None

    http_result = check_http(str(request.url))

    # Домен/сервер недоступен — остальные проверки выполнять бессмысленно
    if not http_result.ok:
        response = CheckResponse(
            url=request.url,
            domain=domain,
            http=http_result,
        )
        _save_check(session, response, trigger)
        return response

    ssl_result = check_ssl(domain)
    robots_result = check_robots(domain)
    sitemap_result = check_sitemap(domain)

    response = CheckResponse(
        url=request.url,
        domain=domain,

        http=http_result,
        ssl=ssl_result,
        robots=robots_result,
        sitemap=sitemap_result,
    )
    _save_check(session, response, trigger)
    return response


def _save_check(
        session: Session,
        response: CheckResponse,
        trigger: CheckTrigger
) -> None:
    """Сохраняет результат проверки для сайта. Повторный адрес использует уже существующий сайт."""

    url = str(response.url)
    site = session.scalar(select(Site).where(Site.url == url))
    if site is None:
        site = Site(url=url, domain=response.domain)
        session.add(site)
        session.flush()

    session.add(
        Check(
            site=site,
            trigger=trigger,
            data=response.model_dump(mode="json"),
        )
    )
    session.commit()


def list_checks(session: Session, limit: int = 40) -> list[CheckHistoryItem]:
    """Возвращает последние проверки, новые сверху."""

    rows = session.scalars(
        select(Check).order_by(Check.created_at.desc()).limit(limit)
    ).all()
    return [
        CheckHistoryItem(
            id=row.id,
            created_at=row.created_at,
            trigger=row.trigger.value if isinstance(row.trigger, CheckTrigger) else str(row.trigger),
            result=CheckResponse.model_validate(row.data),
        )
        for row in rows
    ]