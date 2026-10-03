from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import false, true
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database.base import Base


class ReplikerDeveloperModule(Base):
    __tablename__ = "repliker_developer_modules"

    __table_args__ = (
        UniqueConstraint(
            "repliker_id",
            name=(
                "uq_repliker_developer_module"
            ),
        ),
        CheckConstraint(
            "version >= 1",
            name=(
                "ck_repliker_developer_version"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    repliker_id: Mapped[int] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    language: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="python",
        server_default="python",
    )

    filename: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="repliker_extension.py",
        server_default="repliker_extension.py",
    )

    entrypoint: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="run",
        server_default="run",
    )

    source_code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        server_default="",
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    validated_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
