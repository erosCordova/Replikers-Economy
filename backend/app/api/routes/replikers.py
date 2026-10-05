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
from app.models.repliker import (
    Repliker,
    ReplikerSkill,
)
from app.models.user import User
from app.schemas.repliker import (
    ReplikerCreate,
    ReplikerPublic,
    ReplikerPublicationUpdate,
)
from app.schemas.repliker_studio import (
    ReplikerPhotoPublic,
    ReplikerPhotoUpdate,
    ReplikerStudioPublic,
    ReplikerStudioUpdate,
)
from app.services.repliker_photo_service import (
    ReplikerPhotoError,
    remove_repliker_photo,
    save_repliker_photo,
)
from app.services.repliker_publication_service import (
    ReplikerPublicationError,
    set_repliker_publication,
)
from app.services.repliker_studio_service import (
    ReplikerStudioError,
    studio_snapshot,
    update_repliker_studio,
)


router = APIRouter(
    prefix="/replikers",
    tags=["Replikers"],
)


def _editable_repliker(
    *,
    db: Session,
    repliker_id: int,
    current_user: User,
    lock: bool = False,
) -> Repliker:
    statement = (
        select(Repliker)
        .options(
            selectinload(
                Repliker.skills
            )
        )
        .where(
            Repliker.id
            == repliker_id
        )
    )

    if lock:
        statement = (
            statement.with_for_update()
        )

    repliker = db.scalar(
        statement
    )

    if repliker is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Repliker no encontrado."
            ),
        )

    if (
        repliker.owner_id
        != current_user.id
        and current_user.role
        != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Solo el propietario "
                "del Repliker o un "
                "administrador puede "
                "acceder a su configuración."
            ),
        )

    if (
        lock
        and repliker.is_system
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Los Replikers oficiales "
                "están protegidos y no "
                "pueden modificarse."
            ),
        )

    return repliker


def _public_repliker(
    *,
    db: Session,
    repliker_id: int,
) -> Repliker:
    repliker = db.scalar(
        select(Repliker)
        .options(
            selectinload(
                Repliker.skills
            )
        )
        .where(
            Repliker.id
            == repliker_id
        )
    )

    if repliker is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Repliker no encontrado."
            ),
        )

    return repliker


@router.post(
    "",
    response_model=ReplikerPublic,
    status_code=
        status.HTTP_201_CREATED,
)
def create_repliker(
    payload: ReplikerCreate,
    db: Session = Depends(
        get_db
    ),
    owner: User = Depends(
        get_current_user
    ),
):
    repliker = Repliker(
        owner_id=owner.id,
        name=payload.name.strip(),
        specialty=
            payload.specialty.strip(),
        description=
            payload.description.strip(),
        base_price_credits=
            payload.base_price_credits,

        # Todo Repliker creado por un
        # usuario comienza como borrador.
        is_system=False,
        is_published=False,
        published_at=None,
    )

    db.add(
        repliker
    )

    db.flush()

    used_skills = set()

    for skill_data in payload.skills:
        skill_name = (
            skill_data.name.strip()
        )

        normalized = (
            skill_name.casefold()
        )

        if normalized in used_skills:
            continue

        used_skills.add(
            normalized
        )

        db.add(
            ReplikerSkill(
                repliker_id=
                    repliker.id,
                name=
                    skill_name,
                level=
                    skill_data.level,
            )
        )

    db.commit()

    return _public_repliker(
        db=db,
        repliker_id=repliker.id,
    )


@router.get(
    "/mine",
    response_model=
        list[ReplikerPublic],
)
def get_my_replikers(
    db: Session = Depends(
        get_db
    ),
    owner: User = Depends(
        get_current_user
    ),
):
    statement = (
        select(Repliker)
        .options(
            selectinload(
                Repliker.skills
            )
        )
        .where(
            Repliker.owner_id
            == owner.id
        )
        .order_by(
            Repliker.created_at.desc()
        )
    )

    return list(
        db.scalars(
            statement
        ).all()
    )


@router.get(
    "/marketplace",
    response_model=
        list[ReplikerPublic],
)
def marketplace(
    db: Session = Depends(
        get_db
    ),
):
    statement = (
        select(Repliker)
        .options(
            selectinload(
                Repliker.skills
            )
        )
        .where(
            Repliker.is_active
            .is_(True),
            Repliker.is_published
            .is_(True),
        )
        .order_by(
            Repliker
            .reputation_score
            .desc(),
            Repliker
            .jobs_completed
            .desc(),
        )
    )

    return list(
        db.scalars(
            statement
        ).all()
    )


@router.put(
    "/{repliker_id}/publication",
    response_model=ReplikerPublic,
)
def update_repliker_publication(
    repliker_id: int,
    payload:
        ReplikerPublicationUpdate,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    repliker = _editable_repliker(
        db=db,
        repliker_id=repliker_id,
        current_user=current_user,
        lock=True,
    )

    try:
        set_repliker_publication(
            repliker=repliker,
            published=
                payload.published,
        )

        db.commit()

    except (
        ReplikerPublicationError,
        ValueError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return _public_repliker(
        db=db,
        repliker_id=repliker_id,
    )


@router.get(
    "/{repliker_id}/studio",
    response_model=
        ReplikerStudioPublic,
)
def get_repliker_studio(
    repliker_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    repliker = _editable_repliker(
        db=db,
        repliker_id=
            repliker_id,
        current_user=
            current_user,
    )

    return studio_snapshot(
        db=db,
        repliker=repliker,
    )


@router.put(
    "/{repliker_id}/studio",
    response_model=
        ReplikerStudioPublic,
)
def save_repliker_studio(
    repliker_id: int,
    payload: ReplikerStudioUpdate,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    repliker = _editable_repliker(
        db=db,
        repliker_id=
            repliker_id,
        current_user=
            current_user,
        lock=True,
    )

    try:
        result = (
            update_repliker_studio(
                db=db,
                repliker=repliker,
                payload=payload,
            )
        )

        db.commit()

        return result

    except (
        ReplikerStudioError,
        ReplikerPublicationError,
        ValueError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.put(
    "/{repliker_id}/photo",
    response_model=ReplikerPhotoPublic,
)
def update_repliker_photo(
    repliker_id: int,
    payload: ReplikerPhotoUpdate,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    repliker = _editable_repliker(
        db=db,
        repliker_id=repliker_id,
        current_user=current_user,
        lock=True,
    )

    try:
        result = save_repliker_photo(
            db=db,
            repliker=repliker,
            image_data_url=
                payload.image_data_url,
        )

        db.commit()

        return result

    except ReplikerPhotoError as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{repliker_id}/photo",
    response_model=ReplikerPhotoPublic,
)
def delete_repliker_photo(
    repliker_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    repliker = _editable_repliker(
        db=db,
        repliker_id=repliker_id,
        current_user=current_user,
        lock=True,
    )

    result = remove_repliker_photo(
        db=db,
        repliker=repliker,
    )

    db.commit()

    return result


@router.get(
    "/{repliker_id}",
    response_model=ReplikerPublic,
)
def get_repliker(
    repliker_id: int,
    db: Session = Depends(
        get_db
    ),
):
    repliker = _public_repliker(
        db=db,
        repliker_id=repliker_id,
    )

    if not repliker.is_published:
        raise HTTPException(
            status_code=404,
            detail=(
                "Repliker no encontrado."
            ),
        )

    return repliker
