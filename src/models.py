from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CheckTrigger(StrEnum):
    """Кто инициировал проверку."""

    MANUAL = "manual"
    AUTOMATIC = "automatic"


class Site(Base):
    """Сайт, для которого сохраняются проверки."""

    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    domain: Mapped[str] = mapped_column(Text, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    checks: Mapped[list["Check"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
        order_by="Check.created_at.desc()",
    )


class Check(Base):
    """Один запуск проверки сайта."""

    __tablename__ = "checks"
    __table_args__ = (
        Index("ix_checks_site_id_created_at", "site_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    trigger: Mapped[CheckTrigger] = mapped_column(
        Enum(
            CheckTrigger,
            name="check_trigger",
            native_enum=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    site: Mapped[Site] = relationship(back_populates="checks")
