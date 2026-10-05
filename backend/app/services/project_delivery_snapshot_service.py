from __future__ import annotations

import hashlib
import io
import json
import zipfile

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.models.execution import (
    ExecutionArtifact,
    ExecutionWorkspace,
    ProjectDeliverySnapshot,
    ProjectDeliverySnapshotFile,
)
from app.models.project import Project
from app.models.project_specialist import (
    ProjectFinalReview,
)
from app.services.workspace_service import (
    read_durable_artifact_bytes,
)


class DeliverySnapshotError(
    ValueError
):
    pass


def _version_label(
    *,
    db: Session,
    review: ProjectFinalReview,
) -> str:
    approved_before = int(
        db.scalar(
            select(
                func.count(
                    ProjectFinalReview.id
                )
            )
            .where(
                ProjectFinalReview.project_id
                == review.project_id,

                ProjectFinalReview.status
                == "approved",

                ProjectFinalReview.attempt_number
                < review.attempt_number,
            )
        )
        or 0
    )

    return f"v1.{approved_before}"


def get_delivery_snapshot(
    *,
    db: Session,
    final_review_id: int,
) -> ProjectDeliverySnapshot | None:
    return db.scalar(
        select(
            ProjectDeliverySnapshot
        )
        .where(
            ProjectDeliverySnapshot.final_review_id
            == final_review_id
        )
    )


def list_snapshot_files(
    *,
    db: Session,
    snapshot_id: int,
) -> list[
    ProjectDeliverySnapshotFile
]:
    return list(
        db.scalars(
            select(
                ProjectDeliverySnapshotFile
            )
            .where(
                ProjectDeliverySnapshotFile.snapshot_id
                == snapshot_id
            )
            .order_by(
                ProjectDeliverySnapshotFile.archive_path,
                ProjectDeliverySnapshotFile.id,
            )
        ).all()
    )


def _archive_path(
    *,
    workspace: ExecutionWorkspace,
    artifact: ExecutionArtifact,
) -> str:
    relative = (
        artifact.relative_path
        .replace("\\", "/")
        .lstrip("/")
    )

    return (
        f"tarea-{workspace.task_id}/"
        f"{relative}"
    )


def _zip_info(
    filename: str,
) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(
        filename=filename,
        date_time=(
            1980,
            1,
            1,
            0,
            0,
            0,
        ),
    )

    info.compress_type = (
        zipfile.ZIP_DEFLATED
    )

    info.external_attr = (
        0o100644 << 16
    )

    return info


def build_snapshot_zip(
    *,
    db: Session,
    snapshot: ProjectDeliverySnapshot,
) -> bytes:
    files = list_snapshot_files(
        db=db,
        snapshot_id=snapshot.id,
    )

    manifest = {
        "version":
            snapshot.version_label,

        "review_attempt":
            snapshot.review_attempt,

        "files_count":
            len(files),

        "total_size_bytes":
            sum(
                item.size_bytes
                for item in files
            ),

        "files": [
            {
                "path":
                    item.archive_path,

                "size_bytes":
                    item.size_bytes,

                "sha256":
                    item.sha256,

                "media_type":
                    item.media_type,
            }
            for item in files
        ],
    }

    buffer = io.BytesIO()

    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=
            zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as package:
        package.writestr(
            _zip_info(
                "MANIFIESTO.json"
            ),
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
        )

        for item in files:
            payload = bytes(
                item.content
            )

            digest = (
                hashlib.sha256(
                    payload
                )
                .hexdigest()
            )

            if digest != item.sha256:
                raise DeliverySnapshotError(
                    "La integridad de un "
                    "archivo histórico "
                    "es inválida."
                )

            package.writestr(
                _zip_info(
                    item.archive_path
                ),
                payload,
            )

    return buffer.getvalue()


def ensure_delivery_snapshot(
    *,
    db: Session,
    project_id: int,
    final_review_id: int,
) -> ProjectDeliverySnapshot:
    existing = (
        get_delivery_snapshot(
            db=db,
            final_review_id=
                final_review_id,
        )
    )

    if existing is not None:
        return existing

    project = db.get(
        Project,
        project_id,
    )

    review = db.get(
        ProjectFinalReview,
        final_review_id,
    )

    if project is None:
        raise DeliverySnapshotError(
            "Proyecto no encontrado."
        )

    if (
        review is None
        or review.project_id
        != project.id
    ):
        raise DeliverySnapshotError(
            "Revisión final no encontrada."
        )

    if review.status != "approved":
        raise DeliverySnapshotError(
            "Solo una revisión aprobada "
            "puede generar una versión."
        )

    version_label = _version_label(
        db=db,
        review=review,
    )

    workspaces = list(
        db.scalars(
            select(
                ExecutionWorkspace
            )
            .where(
                ExecutionWorkspace.project_id
                == project.id
            )
            .order_by(
                ExecutionWorkspace.id
            )
        ).all()
    )

    workspace_by_id = {
        workspace.id:
            workspace
        for workspace
        in workspaces
    }

    workspace_ids = list(
        workspace_by_id
    )

    if workspace_ids:
        artifacts = list(
            db.scalars(
                select(
                    ExecutionArtifact
                )
                .where(
                    ExecutionArtifact.workspace_id
                    .in_(
                        workspace_ids
                    )
                )
                .order_by(
                    ExecutionArtifact.id
                )
            ).all()
        )

    else:
        artifacts = []

    # ---------------------------------------------------------
    # IMPORTANTE:
    # primero validamos TODOS los archivos.
    #
    # Si alguno falta o no supera SHA-256,
    # no se crea ningún snapshot parcial.
    # ---------------------------------------------------------

    prepared_files: list[dict] = []

    total_size = 0

    used_paths: set[str] = set()

    for artifact in artifacts:
        workspace = (
            workspace_by_id.get(
                artifact.workspace_id
            )
        )

        if workspace is None:
            raise DeliverySnapshotError(
                "Un artefacto no tiene "
                "workspace válido."
            )

        try:
            payload = (
                read_durable_artifact_bytes(
                    db=db,
                    workspace=workspace,
                    artifact=artifact,
                )
            )

        except FileNotFoundError as exc:
            raise DeliverySnapshotError(
                "No se puede congelar "
                "la versión porque falta "
                f"'{artifact.relative_path}'."
            ) from exc

        digest = (
            hashlib.sha256(
                payload
            )
            .hexdigest()
        )

        if digest != artifact.sha256:
            raise DeliverySnapshotError(
                "El archivo "
                f"'{artifact.relative_path}' "
                "no supera la validación "
                "SHA-256."
            )

        if (
            len(payload)
            != artifact.size_bytes
        ):
            raise DeliverySnapshotError(
                "El tamaño real de "
                f"'{artifact.relative_path}' "
                "no coincide con sus "
                "metadatos."
            )

        archive_path = (
            _archive_path(
                workspace=workspace,
                artifact=artifact,
            )
        )

        if archive_path in used_paths:
            archive_path = (
                f"workspace-"
                f"{workspace.id}/"
                f"{archive_path}"
            )

        used_paths.add(
            archive_path
        )

        prepared_files.append(
            {
                "artifact":
                    artifact,

                "workspace":
                    workspace,

                "payload":
                    payload,

                "sha256":
                    digest,

                "archive_path":
                    archive_path,
            }
        )

        total_size += len(
            payload
        )

    # ---------------------------------------------------------
    # Todos los archivos son válidos.
    # Recién ahora creamos la versión inmutable.
    # ---------------------------------------------------------

    snapshot = ProjectDeliverySnapshot(
        project_id=
            project.id,

        final_review_id=
            review.id,

        review_attempt=
            review.attempt_number,

        version_label=
            version_label,

        files_count=
            len(prepared_files),

        total_size_bytes=
            total_size,
    )

    db.add(
        snapshot
    )

    db.flush()

    for item in prepared_files:
        artifact = item[
            "artifact"
        ]

        workspace = item[
            "workspace"
        ]

        db.add(
            ProjectDeliverySnapshotFile(
                snapshot_id=
                    snapshot.id,

                artifact_id=
                    artifact.id,

                workspace_id=
                    workspace.id,

                task_id=
                    workspace.task_id,

                relative_path=
                    artifact.relative_path,

                archive_path=
                    item[
                        "archive_path"
                    ],

                media_type=
                    artifact.media_type,

                size_bytes=
                    len(
                        item[
                            "payload"
                        ]
                    ),

                sha256=
                    item[
                        "sha256"
                    ],

                content=
                    item[
                        "payload"
                    ],
            )
        )

    db.flush()

    package = build_snapshot_zip(
        db=db,
        snapshot=snapshot,
    )

    snapshot.package_sha256 = (
        hashlib.sha256(
            package
        )
        .hexdigest()
    )

    db.flush()

    return snapshot
