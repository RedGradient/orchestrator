from datetime import datetime
from ipaddress import IPv4Address

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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


class CheckHistoryItem(BaseModel):
    id: int
    created_at: datetime
    trigger: str
    result: CheckResponse


class RegisterHostRequest(BaseModel):
    ip: IPv4Address
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RegisterHostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ip: str
    username: str
