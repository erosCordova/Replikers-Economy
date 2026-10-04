from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.ecosystem import (
    ReplikerAppearance,
)
from app.models.repliker import Repliker
from app.models.user import User
from app.schemas.ecosystem import (
    AppearancePublic,
    AppearanceUpdate,
    EcosystemSnapshot,
)
from app.services.ecosystem_service import (
    build_ecosystem_snapshot,
    serialize_appearance,
)


router = APIRouter(
    prefix="/ecosystem",
    tags=["Ecosistema"],
)


@router.get(
    "",
    response_model=EcosystemSnapshot,
)
def get_ecosystem(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    return build_ecosystem_snapshot(
        db=db,
        current_user=current_user,
    )


@router.put(
    "/replikers/{repliker_id}/appearance",
    response_model=AppearancePublic,
)
def update_repliker_appearance(
    repliker_id: int,
    payload: AppearanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    repliker = db.get(
        Repliker,
        repliker_id,
    )

    if repliker is None:
        raise HTTPException(
            status_code=404,
            detail="Repliker no encontrado.",
        )

    if repliker.is_system:
        raise HTTPException(
            status_code=403,
            detail=(
                "Los Replikers oficiales "
                "están protegidos y no "
                "pueden personalizarse "
                "desde una cuenta."
            ),
        )

    if (
        repliker.owner_id
        != current_user.id
        and current_user.role != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Solo el propietario puede "
                "personalizar este Repliker."
            ),
        )

    appearance = db.scalar(
        select(ReplikerAppearance)
        .where(
            ReplikerAppearance.repliker_id
            == repliker.id
        )
    )

    if appearance is None:
        appearance = ReplikerAppearance(
            repliker_id=repliker.id,
        )

        db.add(appearance)

    appearance.avatar_style = (
        payload.avatar_style
    )

    appearance.primary_color = (
        payload.primary_color
    )

    appearance.secondary_color = (
        payload.secondary_color
    )

    appearance.face_type = (
        payload.face_type
    )

    appearance.eye_style = (
        payload.eye_style
    )

    appearance.accessory = (
        payload.accessory
    )

    appearance.background_style = (
        payload.background_style
    )

    appearance.avatar_url = (
        payload.avatar_url
    )

    db.commit()
    db.refresh(appearance)

    return serialize_appearance(
        appearance
    )
