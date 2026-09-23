from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.checkers import resolve_domain, check_http, check_ssl, check_robots, check_sitemap
from src.schemas import CheckRequest, CheckResponse


app = FastAPI()






@app.post("/api/check")
async def check(request: CheckRequest) -> CheckResponse:
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


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True),
    name="frontend",
)