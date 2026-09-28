from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user, get_db
from app.models.project import Project
from app.models.repliker import Repliker
from app.models.task import (
    Task,
    TaskBid,
    TaskSkillRequirement,
)
from app.models.user import User
from app.schemas.task import (
    BidCreate,
    BidPublic,
    TaskCreate,
    TaskPublic,
)


router = APIRouter(
    tags=["Mercado de tareas"],
)


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    project_id: int,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Proyecto no encontrado.",
        )

    if (
        project.client_id != current_user.id
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail="No tienes acceso a este proyecto.",
        )

    if (
        payload.max_budget_cents is not None
        and project.budget_limit_cents is not None
        and payload.max_budget_cents > project.budget_limit_cents
    ):
        raise HTTPException(
            status_code=400,
            detail="La tarea supera el presupuesto total del proyecto.",
        )

    task = Task(
        project_id=project.id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        complexity=payload.complexity,
        max_budget_cents=payload.max_budget_cents,
    )

    db.add(task)
    db.flush()

    used_skills = set()

    for item in payload.required_skills:
        skill_name = item.skill_name.strip()
        normalized = skill_name.lower()

        if normalized in used_skills:
            continue

        used_skills.add(normalized)

        db.add(
            TaskSkillRequirement(
                task_id=task.id,
                skill_name=skill_name,
                minimum_level=item.minimum_level,
            )
        )

    db.commit()

    statement = (
        select(Task)
        .options(
            selectinload(Task.required_skills)
        )
        .where(Task.id == task.id)
    )

    return db.scalar(statement)


@router.get(
    "/tasks/open",
    response_model=list[TaskPublic],
)
def open_tasks(
    db: Session = Depends(get_db),
):
    statement = (
        select(Task)
        .options(
            selectinload(Task.required_skills)
        )
        .where(Task.status == "open")
        .order_by(Task.created_at.desc())
    )

    return list(
        db.scalars(statement).all()
    )


@router.post(
    "/tasks/{task_id}/bids",
    response_model=BidPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_bid(
    task_id: int,
    payload: BidCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Tarea no encontrada.",
        )

    if task.status != "open":
        raise HTTPException(
            status_code=400,
            detail="La tarea ya no acepta ofertas.",
        )

    repliker = db.get(
        Repliker,
        payload.repliker_id,
    )

    if repliker is None:
        raise HTTPException(
            status_code=404,
            detail="Repliker no encontrado.",
        )

    if repliker.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="No eres propietario de este Repliker.",
        )

    if not repliker.is_active:
        raise HTTPException(
            status_code=400,
            detail="El Repliker está desactivado.",
        )

    if (
        task.max_budget_cents is not None
        and payload.amount_cents > task.max_budget_cents
    ):
        raise HTTPException(
            status_code=400,
            detail="La oferta supera el presupuesto máximo de la tarea.",
        )

    bid = TaskBid(
        task_id=task.id,
        repliker_id=repliker.id,
        amount_cents=payload.amount_cents,
        confidence_score=payload.confidence_score,
        estimated_minutes=payload.estimated_minutes,
        message=payload.message.strip(),
    )

    db.add(bid)

    try:
        db.commit()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Este Repliker ya presentó una oferta para esta tarea.",
        )

    db.refresh(bid)

    return bid


@router.get(
    "/tasks/{task_id}/bids",
    response_model=list[BidPublic],
)
def get_task_bids(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.get(Task, task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Tarea no encontrada.",
        )

    project = db.get(
        Project,
        task.project_id,
    )

    if (
        project.client_id != current_user.id
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail="No puedes ver las ofertas de esta tarea.",
        )

    statement = (
        select(TaskBid)
        .where(TaskBid.task_id == task.id)
        .order_by(
            TaskBid.amount_cents.asc(),
            TaskBid.confidence_score.desc(),
        )
    )

    return list(
        db.scalars(statement).all()
    )
