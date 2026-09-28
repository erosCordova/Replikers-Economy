from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_db,
    require_admin,
)
from app.models.user import User
from app.schemas.user import UserPublic


router = APIRouter(
    prefix="/users",
    tags=["Usuarios"],
)


@router.get(
    "",
    response_model=list[UserPublic],
)
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    users = db.scalars(
        select(User).order_by(User.created_at.desc())
    ).all()

    return list(users)
