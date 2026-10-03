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


class ReplikerStudioProfile(Base):
    __tablename__ = "repliker_studio_profiles"

    __table_args__ = (
        UniqueConstraint(
            "repliker_id",
            name="uq_repliker_studio_profile",
        ),
        CheckConstraint(
            "config_version >= 1",
            name="ck_repliker_studio_config_version",
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

    purpose: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    personality: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    communication_style: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    instructions: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )

    config_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
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


class ReplikerKnowledgeItem(Base):
    __tablename__ = "repliker_knowledge_items"

    __table_args__ = (
        UniqueConstraint(
            "repliker_id",
            "title",
            name="uq_repliker_knowledge_title",
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

    title: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="manual",
        server_default="manual",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
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


class ReplikerRule(Base):
    __tablename__ = "repliker_rules"

    __table_args__ = (
        UniqueConstraint(
            "repliker_id",
            "title",
            name="uq_repliker_rule_title",
        ),
        CheckConstraint(
            "priority >= 0 AND priority <= 100",
            name="ck_repliker_rule_priority",
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

    title: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    instruction: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        server_default="50",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
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
