from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database.base import Base


class ProjectSpecialistRequirement(Base):
    __tablename__ = (
        "project_specialist_requirements"
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "specialty",
            name=(
                "uq_project_specialist_"
                "requirement"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    specialty: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    is_mandatory: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )

    is_final_gate: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    coverage_status: Mapped[str] = (
        mapped_column(
            String(30),
            nullable=False,
            default="pending",
        )
    )

    assigned_repliker_id: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )

    updated_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )

    project = relationship(
        "Project",
    )

    assigned_repliker = relationship(
        "Repliker",
    )
