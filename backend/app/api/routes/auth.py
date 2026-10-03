from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import (
    IntegrityError,
)
from sqlalchemy.orm import Session

from app.auth.cookies import (
    clear_refresh_cookie,
    refresh_cookie_from_request,
    set_refresh_cookie,
    validate_cookie_origin,
)
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
from app.services.auth_session_service import (
    RefreshSessionError,
    create_refresh_session,
    revoke_all_user_sessions,
    revoke_refresh_session,
    rotate_refresh_session,
)


router = APIRouter(
    prefix="/auth",
    tags=[
        "Autenticacion",
    ],
)


def build_auth_response(
    user: User,
) -> AuthResponse:
    return AuthResponse(
        access_token=
            create_access_token(
                user_id=user.id,
                role=user.role,
            ),
        user=user,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=
        status.HTTP_201_CREATED,
)
def register(
    payload: UserRegister,
    request: Request,
    response: Response,
    db: Session = Depends(
        get_db
    ),
):
    validate_cookie_origin(
        request
    )

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
        db.flush()

        refresh_token, _ = (
            create_refresh_session(
                db,
                user_id=user.id,
            )
        )

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

    set_refresh_cookie(
        response,
        refresh_token,
    )

    return build_auth_response(
        user
    )


@router.post(
    "/login",
    response_model=AuthResponse,
)
def login(
    payload: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(
        get_db
    ),
):
    validate_cookie_origin(
        request
    )

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
                "Correo o contrasena "
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
                "La cuenta esta "
                "desactivada."
            ),
        )

    try:
        refresh_token, _ = (
            create_refresh_session(
                db,
                user_id=user.id,
            )
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    set_refresh_cookie(
        response,
        refresh_token,
    )

    return build_auth_response(
        user
    )


@router.post(
    "/refresh",
    response_model=AuthResponse,
)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(
        get_db
    ),
):
    validate_cookie_origin(
        request
    )

    raw_token = (
        refresh_cookie_from_request(
            request
        )
    )

    if not raw_token:
        clear_refresh_cookie(
            response
        )

        raise HTTPException(
            status_code=
                status.HTTP_401_UNAUTHORIZED,
            detail=(
                "No existe una sesion "
                "renovable."
            ),
        )

    try:
        (
            user,
            new_refresh_token,
            _,
        ) = rotate_refresh_session(
            db,
            raw_token=raw_token,
        )

    except RefreshSessionError as exc:
        clear_refresh_cookie(
            response
        )

        raise HTTPException(
            status_code=
                status.HTTP_401_UNAUTHORIZED,
            detail=(
                "La sesion ya no "
                "es valida."
            ),
        ) from exc

    set_refresh_cookie(
        response,
        new_refresh_token,
    )

    return build_auth_response(
        user
    )


@router.post(
    "/logout",
)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(
        get_db
    ),
):
    validate_cookie_origin(
        request
    )

    raw_token = (
        refresh_cookie_from_request(
            request
        )
    )

    if raw_token:
        revoke_refresh_session(
            db,
            raw_token=raw_token,
        )

    clear_refresh_cookie(
        response
    )

    return {
        "status": "ok"
    }


@router.post(
    "/logout-all",
)
def logout_all(
    request: Request,
    response: Response,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
):
    validate_cookie_origin(
        request
    )

    revoke_all_user_sessions(
        db,
        user_id=current_user.id,
    )

    clear_refresh_cookie(
        response
    )

    return {
        "status": "ok"
    }


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
