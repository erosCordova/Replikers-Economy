from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import (
    IntegrityError,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password_constant_time,
)
from app.models.user import User
from app.schemas.user import (
    AuthResponse,
    UserLogin,
    UserPublic,
    UserRegister,
)


router = APIRouter(
    prefix="/auth",
    tags=[
        "Autenticación",
    ],
)


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=
        status.HTTP_201_CREATED,
)
def register(
    payload: UserRegister,
    db: Session = Depends(
        get_db
    ),
):
    email = (
        str(payload.email)
        .lower()
        .strip()
    )

    existing_user = db.scalar(
        select(User)
        .where(
            User.email == email
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Ya existe una cuenta "
                "con este correo."
            ),
        )

    user = User(
        full_name=
            payload.full_name,
        email=email,
        password_hash=
            hash_password(
                payload.password
            ),
        role="user",
        is_active=True,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=
                status.HTTP_409_CONFLICT,
            detail=(
                "Ya existe una cuenta "
                "con este correo."
            ),
        ) from exc

    except Exception:
        db.rollback()
        raise

    token = create_access_token(
        user_id=user.id,
        role=user.role,
    )

    return AuthResponse(
        access_token=token,
        user=user,
    )


@router.post(
    "/login",
    response_model=AuthResponse,
)
def login(
    payload: UserLogin,
    db: Session = Depends(
        get_db
    ),
):
    email = (
        str(payload.email)
        .lower()
        .strip()
    )

    user = db.scalar(
        select(User)
        .where(
            User.email == email
        )
    )

    password_valid = (
        verify_password_constant_time(
            payload.password,
            (
                user.password_hash
                if user is not None
                else None
            ),
        )
    )

    if (
        user is None
        or not password_valid
    ):
        raise HTTPException(
            status_code=
                status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Correo o contraseña "
                "incorrectos."
            ),
            headers={
                "WWW-Authenticate":
                    "Bearer",
            },
        )

    if not user.is_active:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "La cuenta está "
                "desactivada."
            ),
        )

    token = create_access_token(
        user_id=user.id,
        role=user.role,
    )

    return AuthResponse(
        access_token=token,
        user=user,
    )


@router.get(
    "/me",
    response_model=UserPublic,
)
def me(
    user: User = Depends(
        get_current_user
    ),
):
    return user
