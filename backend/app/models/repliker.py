from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Repliker(Base):
    __tablename__ = "replikers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    specialty: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="available",
    )

    reputation_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
    )

    base_price_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
    )

    balance_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    total_earnings_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    jobs_completed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),  # pylint: disable=not-callable
    )

    owner = relationship(
        "User",
        back_populates="replikers",
    )

    skills = relationship(
        "ReplikerSkill",
        back_populates="repliker",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    bids = relationship(
        "TaskBid",
        back_populates="repliker",
        lazy="selectin",
    )


class ReplikerSkill(Base):
    __tablename__ = "repliker_skills"

    __table_args__ = (
        UniqueConstraint(
            "repliker_id",
            "name",
            name="uq_repliker_skill",
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

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
    )

    repliker = relationship(
        "Repliker",
        back_populates="skills",
    )
