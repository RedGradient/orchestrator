from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Host
from src.schemas import RegisterHostRequest, RegisterHostResponse


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
        username=host.username
    )