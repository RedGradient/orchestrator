from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import HostIpAlreadyExistsError, HostNotFoundError
from src.models import Host
from src.schemas import HostItem, RegisterHostRequest, RegisterHostResponse, UpdateHostRequest


async def create_host(
    session: AsyncSession,
    request: RegisterHostRequest,
) -> RegisterHostResponse:
    ip = str(request.ip)
    await ensure_active_ip_available(session, ip)
    host = Host(
        label=request.label,
        ip=ip,
        username=request.username,
        password=request.password,
    )

    session.add(host)
    await session.commit()
    await session.refresh(host)

    return RegisterHostResponse(
        id=host.id,
        label=host.label,
        ip=host.ip,
        username=host.username,
    )


async def list_hosts(session: AsyncSession) -> list[HostItem]:
    """Возвращает активные зарегистрированные хосты, новые сверху."""

    statement = select(Host).where(Host.deleted_at.is_(None)).order_by(Host.created_at.desc())
    rows = (await session.scalars(statement)).all()
    return [HostItem.model_validate(row) for row in rows]


async def update_host(
    session: AsyncSession,
    host_id: int,
    request: UpdateHostRequest,
) -> HostItem:
    host = await get_active_host(session, host_id)
    fields = request.model_fields_set

    if "ip" in fields and request.ip is not None:
        ip = str(request.ip)
        await ensure_active_ip_available(session, ip, exclude_host_id=host.id)
        host.ip = ip
    if "label" in fields:
        host.label = request.label
    if "password" in fields and request.password is not None:
        host.password = request.password

    await session.commit()
    await session.refresh(host)
    return HostItem.model_validate(host)


async def delete_host(session: AsyncSession, host_id: int) -> None:
    host = await get_active_host(session, host_id)
    host.deleted_at = datetime.now(UTC)
    await session.commit()


async def get_active_host(session: AsyncSession, host_id: int) -> Host:
    host = await session.scalar(select(Host).where(Host.id == host_id, Host.deleted_at.is_(None)))
    if host is None:
        raise HostNotFoundError(host_id)
    return host


async def ensure_active_ip_available(
    session: AsyncSession,
    ip: str,
    *,
    exclude_host_id: int | None = None,
) -> None:
    statement = select(Host.id).where(Host.ip == ip, Host.deleted_at.is_(None))
    if exclude_host_id is not None:
        statement = statement.where(Host.id != exclude_host_id)
    if await session.scalar(statement) is not None:
        raise HostIpAlreadyExistsError(ip)
