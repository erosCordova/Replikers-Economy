from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

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
    ProjectPublic,
)


router = APIRouter(
    prefix="/projects",
    tags=["Proyectos"],
)


@router.post(
    "",
    response_model=ProjectPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = Project(
        client_id=current_user.id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        currency=payload.currency.upper().strip(),
        budget_limit_cents=payload.budget_limit_cents,
    )

    db.add(project)
    db.flush()

    for requirement_data in payload.requirements:
        requirement = ProjectRequirement(
            project_id=project.id,
            title=requirement_data.title.strip(),
            description=requirement_data.description.strip(),
            is_mandatory=requirement_data.is_mandatory,
        )

        db.add(requirement)

    db.commit()

    statement = (
        select(Project)
        .options(
            selectinload(Project.requirements)
        )
        .where(Project.id == project.id)
    )

    return db.scalar(statement)


@router.get(
    "/mine",
    response_model=list[ProjectPublic],
)
def my_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = (
        select(Project)
        .options(
            selectinload(Project.requirements)
        )
        .where(
            Project.client_id == current_user.id
        )
        .order_by(
            Project.created_at.desc()
        )
    )

    return list(
        db.scalars(statement).all()
    )


@router.get(
    "/{project_id}",
    response_model=ProjectPublic,
)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = (
        select(Project)
        .options(
            selectinload(Project.requirements)
        )
        .where(
            Project.id == project_id
        )
    )

    project = db.scalar(statement)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado.",
        )

    if (
        project.client_id != current_user.id
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a este proyecto.",
        )

    return project
