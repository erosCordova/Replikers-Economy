import hashlib
from pathlib import Path


from fastapi.responses import Response

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.execution.policy import (
    ExecutionPolicyError,
)
from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.execution import (
    ExecutionArtifact,
    ExecutionWorkspace,
    ProjectDeliverySnapshotFile,
)
from app.models.project import (
    Project,
    ProjectRequirement,
)
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectDeliveryDecisionCreate,
    ProjectDeliveryDecisionPublic,
    ProjectPublic,
    ProjectTrackingPublic,
)
from app.services.client_correction_cycle_service import (
    run_client_correction_cycle,
)
from app.services.client_correction_service import (
    ClientCorrectionPreparationError,
    prepare_client_correction_review,
)
from app.services.project_delivery_snapshot_service import (
    DeliverySnapshotError,
    build_snapshot_zip,
    ensure_delivery_snapshot,
    get_delivery_snapshot,
)
from app.services.workspace_service import (
    read_durable_artifact_bytes,
)
from app.services.project_delivery_service import (
    DeliveryDecisionError,
    submit_delivery_decision,
)
from app.services.project_tracking_service import (
    build_project_tracking,
)


router = APIRouter(
    prefix="/projects",
    tags=["Proyectos"],
)


def _get_accessible_project(
    *,
    project_id: int,
    db: Session,
    current_user: User,
) -> Project:
    statement = (
        select(Project)
        .options(
            selectinload(
                Project.requirements
            )
        )
        .where(
            Project.id
            == project_id
        )
    )

    project = db.scalar(
        statement
    )

    if project is None:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail=
                "Proyecto no encontrado.",
        )

    if (
        project.client_id
        != current_user.id
        and current_user.role
        != "admin"
    ):
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "No tienes acceso "
                "a este proyecto."
            ),
        )

    return project


@router.post(
    "",
    response_model=ProjectPublic,
    status_code=
        status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = Project(
        client_id=current_user.id,
        title=payload.title.strip(),
        description=
            payload.description.strip(),
        currency=
            payload.currency
            .upper()
            .strip(),
        budget_limit_cents=
            payload.budget_limit_cents,

        is_admin_free=(
            current_user.role
            == "admin"
        ),

        payment_status=(
            "admin_free"
            if current_user.role
            == "admin"
            else "unpaid"
        ),
    )

    db.add(project)
    db.flush()

    for requirement_data in (
        payload.requirements
    ):
        requirement = (
            ProjectRequirement(
                project_id=project.id,
                title=
                    requirement_data
                    .title
                    .strip(),
                description=
                    requirement_data
                    .description
                    .strip(),
                is_mandatory=
                    requirement_data
                    .is_mandatory,
            )
        )

        db.add(requirement)

    db.commit()

    statement = (
        select(Project)
        .options(
            selectinload(
                Project.requirements
            )
        )
        .where(
            Project.id
            == project.id
        )
    )

    return db.scalar(statement)


@router.get(
    "/mine",
    response_model=list[
        ProjectPublic
    ],
)
def my_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    statement = (
        select(Project)
        .options(
            selectinload(
                Project.requirements
            )
        )
        .where(
            Project.client_id
            == current_user.id
        )
        .order_by(
            Project.created_at.desc()
        )
    )

    return list(
        db.scalars(
            statement
        ).all()
    )


@router.get(
    "/{project_id}/tracking",
    response_model=
        ProjectTrackingPublic,
)
def get_project_tracking(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = (
        _get_accessible_project(
            project_id=project_id,
            db=db,
            current_user=current_user,
        )
    )

    return build_project_tracking(
        db=db,
        project=project,
    )


@router.post(
    "/{project_id}/delivery-decision",
    response_model=
        ProjectDeliveryDecisionPublic,
)
def project_delivery_decision(
    project_id: int,
    payload:
        ProjectDeliveryDecisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = (
        _get_accessible_project(
            project_id=project_id,
            db=db,
            current_user=current_user,
        )
    )

    if (
        project.client_id
        != current_user.id
    ):
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo el cliente "
                "propietario del proyecto "
                "puede decidir sobre "
                "la entrega."
            ),
        )

    tracking = (
        build_project_tracking(
            db=db,
            project=project,
        )
    )

    delivery = tracking[
        "delivery"
    ]

    final_review = tracking[
        "final_review"
    ]

    if final_review is None:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "La entrega aún no tiene "
                "revisión final de Vera."
            ),
        )

    if (
        delivery[
            "client_decision"
        ]
        == "accepted"
    ):
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "La entrega ya fue "
                "aceptada."
            ),
        )

    if (
        payload.decision
        == "accepted"
        and not delivery[
            "ready"
        ]
    ):
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Esta versión todavía "
                "no está disponible "
                "para aceptación."
            ),
        )

    if (
        payload.decision
        == "corrections_requested"
    ):
        if not delivery[
            "technical_ready"
        ]:
            raise HTTPException(
                status_code=
                    status.HTTP_409_CONFLICT,
                detail=(
                    "Solo puedes solicitar "
                    "correcciones cuando "
                    "Vera haya aprobado "
                    "la versión entregada."
                ),
            )

        if len(
            payload.comment.strip()
        ) < 5:
            raise HTTPException(
                status_code=
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Describe claramente "
                    "qué deseas corregir."
                ),
            )

    try:
        result = (
            submit_delivery_decision(
                db=db,
                project=project,
                decision=
                    payload.decision,
                comment=
                    payload.comment,
                review_attempt=
                    final_review[
                        "attempt_number"
                    ],
            )
        )

        if (
            payload.decision
            == "corrections_requested"
        ):
            prepare_client_correction_review(
                db=db,
                project=project,
                client_request=
                    payload.comment,
                source_review_attempt=
                    final_review[
                        "attempt_number"
                    ],
            )

        db.commit()

        if (
            payload.decision
            == "corrections_requested"
        ):
            cycle_result = (
                run_client_correction_cycle(
                    db=db,
                    project_id=
                        project.id,
                    max_cycles=3,
                )
            )

            result[
                "cycle_status"
            ] = cycle_result[
                "status"
            ]

        return result

    except (
        DeliveryDecisionError,
        ClientCorrectionPreparationError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/{project_id}/artifacts/"
    "{artifact_id}/download",
)
def download_project_artifact(
    project_id: int,
    artifact_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = _get_accessible_project(
        project_id=project_id,
        db=db,
        current_user=current_user,
    )

    artifact = db.get(
        ExecutionArtifact,
        artifact_id,
    )

    if artifact is None:
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail=(
                "Archivo no encontrado."
            ),
        )

    workspace = db.get(
        ExecutionWorkspace,
        artifact.workspace_id,
    )

    if (
        workspace is None
        or workspace.project_id
        != project.id
    ):
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail=(
                "Archivo no encontrado "
                "en este proyecto."
            ),
        )

    try:
        payload = (
            read_durable_artifact_bytes(
                db=db,
                workspace=workspace,
                artifact=artifact,
            )
        )

        db.commit()

    except FileNotFoundError as exc:
        db.rollback()

        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail=(
                "El archivo original "
                "ya no está disponible."
            ),
        ) from exc

    except ExecutionPolicyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    filename = (
        Path(
            artifact.relative_path
        )
        .name
        .replace('"', "")
        .replace("\\", "_")
    )

    if not filename:
        filename = (
            f"archivo-{artifact.id}"
        )

    return Response(
        content=payload,
        media_type=
            artifact.media_type,
        headers={
            "Content-Disposition":
                (
                    'attachment; '
                    f'filename="{filename}"'
                ),

            "X-Content-SHA256":
                artifact.sha256,

            "Cache-Control":
                "private, no-store",
        },
    )


@router.get(
    "/{project_id}/versions/"
    "{final_review_id}/package",
)
def download_project_version_package(
    project_id: int,
    final_review_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = _get_accessible_project(
        project_id=project_id,
        db=db,
        current_user=current_user,
    )

    snapshot = (
        get_delivery_snapshot(
            db=db,
            final_review_id=
                final_review_id,
        )
    )

    try:
        if snapshot is None:
            snapshot = (
                ensure_delivery_snapshot(
                    db=db,
                    project_id=
                        project.id,
                    final_review_id=
                        final_review_id,
                )
            )

        if (
            snapshot.project_id
            != project.id
        ):
            raise HTTPException(
                status_code=
                    status.HTTP_404_NOT_FOUND,
                detail=(
                    "Versión no encontrada."
                ),
            )

        payload = build_snapshot_zip(
            db=db,
            snapshot=snapshot,
        )

        digest = (
            hashlib.sha256(
                payload
            )
            .hexdigest()
        )

        if (
            snapshot.package_sha256
            and digest
            != snapshot.package_sha256
        ):
            raise DeliverySnapshotError(
                "La integridad del paquete "
                "de entrega es inválida."
            )

        if not snapshot.package_sha256:
            snapshot.package_sha256 = (
                digest
            )

        db.commit()

    except DeliverySnapshotError as exc:
        db.rollback()

        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    safe_version = (
        snapshot.version_label
        .replace("/", "-")
    )

    filename = (
        f"replikers-proyecto-"
        f"{project.id}-"
        f"{safe_version}.zip"
    )

    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition":
                (
                    'attachment; '
                    f'filename="{filename}"'
                ),

            "X-Content-SHA256":
                digest,

            "Cache-Control":
                "private, no-store",
        },
    )


@router.get(
    "/{project_id}/versions/"
    "{final_review_id}/files/"
    "{snapshot_file_id}/download",
)
def download_project_version_file(
    project_id: int,
    final_review_id: int,
    snapshot_file_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = _get_accessible_project(
        project_id=project_id,
        db=db,
        current_user=current_user,
    )

    snapshot = (
        get_delivery_snapshot(
            db=db,
            final_review_id=
                final_review_id,
        )
    )

    if (
        snapshot is None
        or snapshot.project_id
        != project.id
    ):
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail=(
                "Versión no encontrada."
            ),
        )

    item = db.get(
        ProjectDeliverySnapshotFile,
        snapshot_file_id,
    )

    if (
        item is None
        or item.snapshot_id
        != snapshot.id
    ):
        raise HTTPException(
            status_code=
                status.HTTP_404_NOT_FOUND,
            detail=(
                "Archivo histórico "
                "no encontrado."
            ),
        )

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
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "La integridad del archivo "
                "histórico es inválida."
            ),
        )

    filename = (
        Path(
            item.relative_path
        )
        .name
        .replace('"', "")
        .replace("\\", "_")
    )

    return Response(
        content=payload,
        media_type=
            item.media_type,
        headers={
            "Content-Disposition":
                (
                    'attachment; '
                    f'filename="{filename}"'
                ),

            "X-Content-SHA256":
                item.sha256,

            "Cache-Control":
                "private, no-store",
        },
    )


@router.get(
    "/{project_id}",
    response_model=ProjectPublic,
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    return _get_accessible_project(
        project_id=project_id,
        db=db,
        current_user=current_user,
    )
