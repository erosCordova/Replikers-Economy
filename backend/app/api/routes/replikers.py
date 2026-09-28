from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.repliker import (
    Repliker,
    ReplikerSkill,
)
from app.models.user import User
from app.schemas.repliker import (
    ReplikerCreate,
    ReplikerPublic,
)


router = APIRouter(
    prefix="/replikers",
    tags=["Replikers"],
)


@router.post(
    "",
    response_model=ReplikerPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_repliker(
    payload: ReplikerCreate,
    db: Session = Depends(get_db),
    owner: User = Depends(get_current_user),
):
    repliker = Repliker(
        owner_id=owner.id,
        name=payload.name.strip(),
        specialty=payload.specialty.strip(),
        description=payload.description.strip(),
        base_price_credits=payload.base_price_credits,
    )

    db.add(repliker)
    db.flush()

    used_skills = set()

    for skill_data in payload.skills:
        skill_name = skill_data.name.strip()
        normalized = skill_name.lower()

        if normalized in used_skills:
            continue

        used_skills.add(normalized)

        skill = ReplikerSkill(
            repliker_id=repliker.id,
            name=skill_name,
            level=skill_data.level,
        )

        db.add(skill)

    db.commit()

    statement = (
        select(Repliker)
        .options(selectinload(Repliker.skills))
        .where(Repliker.id == repliker.id)
    )

    return db.scalar(statement)


@router.get(
    "/mine",
    response_model=list[ReplikerPublic],
)
def get_my_replikers(
    db: Session = Depends(get_db),
    owner: User = Depends(get_current_user),
):
    statement = (
        select(Repliker)
        .options(selectinload(Repliker.skills))
        .where(Repliker.owner_id == owner.id)
        .order_by(Repliker.created_at.desc())
    )

    return list(
        db.scalars(statement).all()
    )


@router.get(
    "/marketplace",
    response_model=list[ReplikerPublic],
)
def marketplace(
    db: Session = Depends(get_db),
):
    statement = (
        select(Repliker)
        .options(selectinload(Repliker.skills))
        .where(Repliker.is_active.is_(True))
        .order_by(
            Repliker.reputation_score.desc(),
            Repliker.jobs_completed.desc(),
        )
    )

    return list(
        db.scalars(statement).all()
    )


@router.get(
    "/{repliker_id}",
    response_model=ReplikerPublic,
)
def get_repliker(
    repliker_id: int,
    db: Session = Depends(get_db),
):
    statement = (
        select(Repliker)
        .options(selectinload(Repliker.skills))
        .where(Repliker.id == repliker_id)
    )

    repliker = db.scalar(statement)

    if repliker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repliker no encontrado.",
        )

    return repliker
