from datetime import datetime
from enum import StrEnum
from ipaddress import IPv4Address
from typing import Any

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


class Command(StrEnum):
    DOCKER_CLEANUP = "docker_cleanup"
    POSTGRES_BACKUP = "postgres_backup"
    CREATE_SWAP = "create_swap"
    LOGS_CLEANUP = "logs_cleanup"
    PORTS = "ports"


class CommandRequest(BaseModel):
    host_id: int
    command: Command


class CommandStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


class CommandResponse(BaseModel):
    host: str
    status: CommandStatus
    result: Any | None = None
    error: str | None = None


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


class HostItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ip: str
    username: str
    created_at: datetime


class SwapEntry(BaseModel):
    path: str
    size_bytes: int


class SwapInfo(BaseModel):
    is_active: bool
    total_swap_size_bytes: int
    free_disk_space_bytes: int
    swaps: list[SwapEntry]


class CreateSwapResult(BaseModel):
    created: bool
    swap_info: SwapInfo | None = None


class LogrotateResult(BaseModel):
    path: str
    success: bool
    error: str | None = None


class Fail2BanResult(BaseModel):
    success: bool
    error: str | None = None


class DockerDaemonResult(BaseModel):
    """Результат настройки Docker daemon."""

    success: bool
    error: str | None = None


class JournaldResult(BaseModel):
    success: bool
    system_max_use: str | None = None
    system_max_file_size: str | None = None
    error: str | None = None


class PackageInstallResult(BaseModel):
    """Результат проверки и установки пакета."""

    already_installed: bool = Field(
        description="Был ли пакет уже установлен до начала операции.",
    )
    success: bool = Field(
        description="Завершилась ли проверка или установка пакета успешно.",
    )
    error: str | None = Field(
        default=None,
        description="Описание ошибки при проверке или установке пакета.",
    )


class LogsCleanupResult(BaseModel):
    """Результат установки и настройки механизмов очистки системных логов."""

    logrotate: PackageInstallResult | None = None
    fail2ban: PackageInstallResult | None = None
    logrotate_config: list[LogrotateResult] = Field(
        default_factory=list,
        description="Результаты настройки ротации отдельных файлов логов.",
    )
    journald: JournaldResult | None = Field(
        default=None,
        description="Результат настройки systemd-journald.",
    )
    fail2ban_config: Fail2BanResult | None = None
    dockerd: DockerDaemonResult | None = None
    freed_bytes: int = 0


class ShouldClose(StrEnum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class PortCheckItem(BaseModel):
    port: int
    service: str
    is_docker: bool
    should_close: ShouldClose
    reason: str


class PortsCheckResult(BaseModel):
    ports: list[PortCheckItem] = Field(default_factory=list)
