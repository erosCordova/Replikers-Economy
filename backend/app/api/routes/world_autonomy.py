
"""API de configuracion de autonomia de Replikers World.

Utiliza autenticacion existente.
No crea contratos ni transfiere creditos.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.models.user import User

from app.services.world_access_service import (
    require_owned_repliker,
)
from app.services.world_autonomy_policy import (
    AutonomyPolicyError,
    AutonomyPolicyConflict,
    AutonomyPolicyDenied,
    get_policy,
    update_policy,
    check_proposal,
    policy_history,
)

router = APIRouter(
    prefix="/world",
    tags=["Replikers World - Autonomia"],
)


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool
    max_price_cents: StrictInt = Field(ge=0, le=100000)
    max_cost_cents: StrictInt = Field(ge=0, le=20000)
    max_proposals_per_round: StrictInt = Field(ge=1, le=5)
    expected_version: StrictInt = Field(ge=0)


class ProposalCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_cents: StrictInt = Field(gt=0)
    estimated_cost_cents: StrictInt = Field(ge=0)


def _http_error(exc):
    if isinstance(exc, AutonomyPolicyConflict):
        return HTTPException(409, str(exc))
    if isinstance(exc, AutonomyPolicyDenied):
        return HTTPException(403, str(exc))
    if isinstance(exc, AutonomyPolicyError):
        return HTTPException(400, str(exc))
    return HTTPException(
        503, "La base de datos requiere migracion World."
    )


@router.get("/mine/{repliker_id}/autonomy")
def get_my_autonomy(
    repliker_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_owned_repliker(db, user, repliker_id)

    try:
        return get_policy(
            db, owner_id=user.id, repliker_id=repliker_id
        )
    except (AutonomyPolicyError, DBAPIError) as exc:
        raise _http_error(exc) from exc


@router.put("/mine/{repliker_id}/autonomy")
def configure_my_autonomy(
    repliker_id: int,
    payload: PolicyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_owned_repliker(db, user, repliker_id)

    try:
        result = update_policy(
            db,
            owner_id=user.id,
            repliker_id=repliker_id,
            **payload.model_dump(),
        )
        db.commit()
        return result
    except (
        AutonomyPolicyError, DBAPIError,
        IntegrityError,
    ) as exc:
        db.rollback()
        if isinstance(exc, IntegrityError):
            raise HTTPException(
                409, "La politica fue modificada simultaneamente."
            ) from exc
        raise _http_error(exc) from exc


@router.post("/mine/{repliker_id}/autonomy/check")
def preview_my_proposal(
    repliker_id: int,
    payload: ProposalCheck,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_owned_repliker(db, user, repliker_id)

    try:
        return check_proposal(
            db,
            owner_id=user.id,
            repliker_id=repliker_id,
            **payload.model_dump(),
        )
    except (AutonomyPolicyError, DBAPIError) as exc:
        raise _http_error(exc) from exc


@router.get("/mine/{repliker_id}/autonomy/history")
def my_autonomy_history(
    repliker_id: int,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_owned_repliker(db, user, repliker_id)

    try:
        return {
            "repliker_id": repliker_id,
            "history": policy_history(
                db,
                owner_id=user.id,
                repliker_id=repliker_id,
                limit=limit,
            ),
        }
    except (AutonomyPolicyError, DBAPIError) as exc:
        raise _http_error(exc) from exc
