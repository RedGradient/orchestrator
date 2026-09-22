from datetime import datetime

from pydantic import BaseModel, HttpUrl


class CheckRequest(BaseModel):
    url: HttpUrl

class HttpCheckResult(BaseModel):
    ok: bool
    status_code: int | None = None
    response_time_ms: float | None = None
    error: str | None = None

class SslCheckResult(BaseModel):
    ok: bool
    version: str | None = None
    issuer: str | None = None
    expires_at: datetime | None = None
    days_remaining: int | None = None
    error: str | None = None


class RobotsCheckResult(BaseModel):
    available: bool
    status_code: int | None = None
    valid: bool | None = None
    errors: list[str] = []
    warnings: list[str] = []
    sitemaps: list[HttpUrl] = []
    error: str | None = None


class SitemapCheckResult(BaseModel):
    available: bool
    status_code: int | None = None
    valid: bool | None = None
    errors: list[str] = []
    warnings: list[str] = []
    url_count: int | None = None
    error: str | None = None

class CheckResponse(BaseModel):
    url: HttpUrl
    domain: str | None = None

    http: HttpCheckResult | None = None
    ssl: SslCheckResult | None = None
    robots: RobotsCheckResult | None = None
    sitemap: SitemapCheckResult | None = None