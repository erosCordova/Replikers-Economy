from datetime import (
    datetime,
    timedelta,
    timezone,
)

from fastapi import (
    HTTPException,
    Request,
    Response,
    status,
)

from app.core.config import settings


def set_refresh_cookie(
    response: Response,
    raw_token: str,
) -> None:
    max_age = (
        settings
        .REFRESH_TOKEN_EXPIRE_DAYS
        * 24
        * 60
        * 60
    )

    response.set_cookie(
        key=
            settings
            .REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=max_age,
        expires=(
            datetime.now(
                timezone.utc
            )
            + timedelta(
                days=
                    settings
                    .REFRESH_TOKEN_EXPIRE_DAYS
            )
        ),
        path=
            settings
            .REFRESH_COOKIE_PATH,
        domain=(
            settings
            .REFRESH_COOKIE_DOMAIN
            or None
        ),
        secure=
            settings
            .refresh_cookie_secure,
        httponly=True,
        samesite=
            settings
            .REFRESH_COOKIE_SAMESITE,
    )


def clear_refresh_cookie(
    response: Response,
) -> None:
    response.delete_cookie(
        key=
            settings
            .REFRESH_COOKIE_NAME,
        path=
            settings
            .REFRESH_COOKIE_PATH,
        domain=(
            settings
            .REFRESH_COOKIE_DOMAIN
            or None
        ),
        secure=
            settings
            .refresh_cookie_secure,
        httponly=True,
        samesite=
            settings
            .REFRESH_COOKIE_SAMESITE,
    )


def refresh_cookie_from_request(
    request: Request,
) -> str | None:
    return request.cookies.get(
        settings
        .REFRESH_COOKIE_NAME
    )


def validate_cookie_origin(
    request: Request,
) -> None:
    origin = request.headers.get(
        "origin"
    )

    if origin is None:
        return

    normalized = (
        origin
        .strip()
        .rstrip("/")
    )

    if (
        normalized
        not in settings.cors_origins
    ):
        raise HTTPException(
            status_code=
                status.HTTP_403_FORBIDDEN,
            detail=(
                "Origen no permitido "
                "para una operacion "
                "de sesion."
            ),
        )
