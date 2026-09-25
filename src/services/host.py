from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Host
from src.schemas import HostItem, RegisterHostRequest, RegisterHostResponse


async def create_host(
    session: AsyncSession,
    request: RegisterHostRequest,
) -> RegisterHostResponse:
    host = Host(
        ip=str(request.ip),
        username=request.username,
        password=request.password,
    )

    session.add(host)
    await session.commit()
    await session.refresh(host)

    return RegisterHostResponse(
        id=host.id,
        ip=host.ip,
        username=host.username,
    )


async def list_hosts(session: AsyncSession) -> list[HostItem]:
    """Возвращает зарегистрированные хосты, новые сверху."""

    rows = (
        await session.scalars(select(Host).order_by(Host.created_at.desc()))
    ).all()
    return [HostItem.model_validate(row) for row in rows]
