from fastapi import (
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.auth.security import (
    decode_access_token,
)
from app.database.session import (
    SessionLocal,
)
from app.models.user import User


bearer_scheme = HTTPBearer(
    auto_error=False
)


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def unauthorized(
    detail: str,
) -> HTTPException:
    return HTTPException(
        status_code=
            status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={
            "WWW-Authenticate":
                "Bearer",
        },
    )


def get_current_user(
    credentials:
        HTTPAuthorizationCredentials | None
        = Depends(
            bearer_scheme
        ),
    db: Session = Depends(
        get_db
    ),
) -> User:
    if credentials is None:
        raise unauthorized(
            "Autenticación requerida."
        )

    try:
        payload = decode_access_token(
            credentials.credentials
        )

        user_id = int(
            payload["sub"]
        )

    except (
        InvalidTokenError,
        KeyError,
        ValueError,
        TypeError,
    ):
        raise unauthorized(
            "Token inválido o expirado."
        )

    user = db.get(
        User,
        user_id,
    )

    if user is None:
        raise unauthorized(
            "Usuario no encontrado."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=
                "Usuario desactivado.",
        )

    return user


def require_admin(
    user: User = Depends(
        get_current_user
    ),
) -> User:
    # La autorizacion usa el rol actual
    # almacenado en la base, no el claim
    # role del JWT.
    if user.role != "admin":
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "Se requieren permisos "
                "de administrador."
            ),
        )

    return user
