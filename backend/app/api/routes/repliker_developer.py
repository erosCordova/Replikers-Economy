from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.repliker import (
    Repliker,
)
from app.models.user import User
from app.schemas.repliker_developer import (
    ReplikerDeveloperPublic,
    ReplikerDeveloperUpdate,
)
from app.services.repliker_developer_service import (
    ReplikerDeveloperError,
    developer_snapshot,
    save_developer_module,
)


router = APIRouter(
    prefix="/replikers",
    tags=[
        "Taller de Replikers",
    ],
)


def _editable_repliker(
    *,
    db: Session,
    repliker_id: int,
    current_user: User,
    write: bool = False,
) -> Repliker:
    repliker = db.get(
        Repliker,
        repliker_id,
    )

    if repliker is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Repliker no encontrado."
            ),
        )

    if write and repliker.is_system:
        raise HTTPException(
            status_code=403,
            detail=(
                "Los Replikers oficiales "
                "están protegidos y no "
                "pueden modificarse."
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
                "modificar este código."
            ),
        )

    return repliker


@router.get(
    "/{repliker_id}/developer",
    response_model=
        ReplikerDeveloperPublic,
)
def get_repliker_developer(
    repliker_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    _editable_repliker(
        db=db,
        repliker_id=repliker_id,
        current_user=current_user,
    )

    return developer_snapshot(
        db=db,
        repliker_id=repliker_id,
    )


@router.put(
    "/{repliker_id}/developer",
    response_model=
        ReplikerDeveloperPublic,
)
def update_repliker_developer(
    repliker_id: int,
    payload:
        ReplikerDeveloperUpdate,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    _editable_repliker(
        db=db,
        repliker_id=repliker_id,
        current_user=current_user,
        write=True,
    )

    try:
        result = (
            save_developer_module(
                db=db,
                repliker_id=
                    repliker_id,
                payload=
                    payload,
            )
        )

        db.commit()

        return result

    except (
        ReplikerDeveloperError,
        ValueError,
    ) as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
