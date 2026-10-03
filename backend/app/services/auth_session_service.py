from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
import hashlib
import secrets
from uuid import uuid4

from sqlalchemy import (
    select,
    update,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth_session import (
    AuthSession,
)
from app.models.user import User


class RefreshSessionError(
    ValueError
):
    pass


class RefreshTokenReuseError(
    RefreshSessionError
):
    pass


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def normalize_utc(
    value: datetime,
) -> datetime:
    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def hash_refresh_token(
    raw_token: str,
) -> str:
    return hashlib.sha256(
        raw_token.encode(
            "utf-8"
        )
    ).hexdigest()


def create_refresh_session(
    db: Session,
    *,
    user_id: int,
    family_id: str | None = None,
    rotated_from_id: int | None = None,
) -> tuple[
    str,
    AuthSession,
]:
    raw_token = (
        secrets.token_urlsafe(
            48
        )
    )

    now = utc_now()

    session = AuthSession(
        user_id=user_id,
        token_hash=
            hash_refresh_token(
                raw_token
            ),
        family_id=(
            family_id
            or uuid4().hex
        ),
        rotated_from_id=
            rotated_from_id,
        expires_at=(
            now
            + timedelta(
                days=
                    settings
                    .REFRESH_TOKEN_EXPIRE_DAYS
            )
        ),
    )

    db.add(session)
    db.flush()

    return (
        raw_token,
        session,
    )


def revoke_session_family(
    db: Session,
    *,
    family_id: str,
    now: datetime | None = None,
) -> None:
    timestamp = (
        now
        or utc_now()
    )

    db.execute(
        update(
            AuthSession
        )
        .where(
            AuthSession.family_id
            == family_id,
            AuthSession.revoked_at
            .is_(None),
        )
        .values(
            revoked_at=timestamp
        )
    )


def rotate_refresh_session(
    db: Session,
    *,
    raw_token: str,
) -> tuple[
    User,
    str,
    AuthSession,
]:
    token_hash = (
        hash_refresh_token(
            raw_token
        )
    )

    current = db.scalar(
        select(
            AuthSession
        )
        .where(
            AuthSession.token_hash
            == token_hash
        )
        .with_for_update()
    )

    if current is None:
        raise RefreshSessionError(
            "Refresh token invalido."
        )

    now = utc_now()

    if current.revoked_at is not None:
        revoke_session_family(
            db,
            family_id=
                current.family_id,
            now=now,
        )

        db.commit()

        raise RefreshTokenReuseError(
            "Se detecto reutilizacion "
            "de un refresh token."
        )

    if (
        normalize_utc(
            current.expires_at
        )
        <= now
    ):
        current.revoked_at = now

        db.commit()

        raise RefreshSessionError(
            "Refresh token expirado."
        )

    user = db.get(
        User,
        current.user_id,
    )

    if (
        user is None
        or not user.is_active
    ):
        revoke_session_family(
            db,
            family_id=
                current.family_id,
            now=now,
        )

        db.commit()

        raise RefreshSessionError(
            "Sesion no disponible."
        )

    new_raw_token, new_session = (
        create_refresh_session(
            db,
            user_id=user.id,
            family_id=
                current.family_id,
            rotated_from_id=
                current.id,
        )
    )

    current.revoked_at = now
    current.last_used_at = now
    current.replaced_by_id = (
        new_session.id
    )

    db.commit()
    db.refresh(new_session)

    return (
        user,
        new_raw_token,
        new_session,
    )


def revoke_refresh_session(
    db: Session,
    *,
    raw_token: str,
) -> None:
    session = db.scalar(
        select(
            AuthSession
        )
        .where(
            AuthSession.token_hash
            == hash_refresh_token(
                raw_token
            )
        )
        .with_for_update()
    )

    if (
        session is not None
        and session.revoked_at
        is None
    ):
        session.revoked_at = (
            utc_now()
        )

    db.commit()


def revoke_all_user_sessions(
    db: Session,
    *,
    user_id: int,
) -> None:
    db.execute(
        update(
            AuthSession
        )
        .where(
            AuthSession.user_id
            == user_id,
            AuthSession.revoked_at
            .is_(None),
        )
        .values(
            revoked_at=utc_now()
        )
    )

    db.commit()
