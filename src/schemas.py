from datetime import datetime
from enum import Enum
from ipaddress import IPv4Address
from typing import Any

from pydantic import BaseModel, HttpUrl, Field, ConfigDict


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


class JobAction(str, Enum):
    DOCKER_CLEANUP = "docker_cleanup"


class CommandRequest(BaseModel):
    host_id: int
    action: JobAction

class CommandResponse(BaseModel):
    ip: IPv4Address
    result: Any


class DockerPruneResult(BaseModel):
    deleted_containers: list[str] = Field(default_factory=list)
    deleted_volumes: list[str] = Field(default_factory=list)
    deleted_networks: list[str] = Field(default_factory=list)
    untagged_images: list[str] = Field(default_factory=list)
    deleted_images: list[str] = Field(default_factory=list)
    deleted_build_cache_objects: list[str] = Field(default_factory=list)
    disk_space_reclaimed: str = "0B"


class RegisterHostRequest(BaseModel):
    ip: IPv4Address
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RegisterHostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ip: str
    username: str