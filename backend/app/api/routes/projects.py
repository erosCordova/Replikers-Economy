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

from app.auth.dependencies import (
    get_current_user,
    get_db,
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

        db.commit()

        return result

    except DeliveryDecisionError as exc:
        db.rollback()

        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


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
