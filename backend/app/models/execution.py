from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database.base import Base


class ExecutionWorkspace(Base):
    __tablename__ = "execution_workspaces"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    contract_id: Mapped[int] = mapped_column(
        ForeignKey(
            "task_contracts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
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

    task_id: Mapped[int] = mapped_column(
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    repliker_id: Mapped[int] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="ready",
        index=True,
    )

    storage_driver: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="local",
    )

    root_ref: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
        unique=True,
    )

    max_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=250,
    )

    max_file_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2_000_000,
    )

    max_total_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=25_000_000,
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


class ExecutionArtifact(Base):
    __tablename__ = "execution_artifacts"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "relative_path",
            name="uq_execution_artifact_path",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey(
            "execution_workspaces.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    relative_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    media_type: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        default="text/plain",
    )

    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
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


class ExecutionArtifactBlob(Base):
    __tablename__ = (
        "execution_artifact_blobs"
    )

    artifact_id: Mapped[int] = mapped_column(
        ForeignKey(
            "execution_artifacts.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    content: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
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


class ProjectDeliverySnapshot(Base):
    __tablename__ = (
        "project_delivery_snapshots"
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version_label",
            name=(
                "uq_project_delivery_"
                "snapshot_version"
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

    final_review_id: Mapped[int] = mapped_column(
        ForeignKey(
            "project_final_reviews.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    review_attempt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    version_label: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    files_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    total_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    package_sha256: Mapped[str | None] = (
        mapped_column(
            String(64),
            nullable=True,
        )
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ProjectDeliverySnapshotFile(Base):
    __tablename__ = (
        "project_delivery_snapshot_files"
    )

    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "archive_path",
            name=(
                "uq_project_delivery_"
                "snapshot_file_path"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey(
            "project_delivery_snapshots.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    artifact_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    workspace_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    task_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    relative_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    archive_path: Mapped[str] = mapped_column(
        String(1200),
        nullable=False,
    )

    media_type: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    content: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ToolExecutionLog(Base):
    __tablename__ = "tool_execution_logs"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey(
            "execution_workspaces.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    contract_id: Mapped[int] = mapped_column(
        ForeignKey(
            "task_contracts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    repliker_id: Mapped[int] = mapped_column(
        ForeignKey(
            "replikers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    tool_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    target_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    input_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    output_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    error_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
