from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database.base import Base


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"

    __table_args__ = (
        UniqueConstraint(
            "action",
            "key_hash",
            name=
                "uq_auth_rate_limit_action_key",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )

    key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    window_started_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    blocked_until: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
