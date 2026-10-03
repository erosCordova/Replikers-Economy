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
    delete,
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


def enforce_user_session_policy(
    db: Session,
    *,
    user_id: int,
    exclude_session_id:
        int | None = None,
) -> None:
    now = utc_now()

    # Primero invalida sesiones expiradas.
    db.execute(
        update(
            AuthSession
        )
        .where(
            AuthSession.user_id
            == user_id,
            AuthSession.revoked_at
            .is_(None),
            AuthSession.expires_at
            <= now,
        )
        .values(
            revoked_at=now
        )
    )

    history_cutoff = (
        now
        - timedelta(
            days=
                settings
                .AUTH_SESSION_HISTORY_DAYS
        )
    )

    # Conservamos historial desde el momento
    # real de revocacion, no desde created_at.
    db.execute(
        delete(
            AuthSession
        )
        .where(
            AuthSession.user_id
            == user_id,
            AuthSession.revoked_at
            .is_not(None),
            AuthSession.revoked_at
            < history_cutoff,
        )
    )

    conditions = [
        AuthSession.user_id
        == user_id,

        AuthSession.revoked_at
        .is_(None),

        AuthSession.expires_at
        > now,
    ]

    # Durante una rotacion, la sesion actual
    # sera reemplazada en esta misma transaccion.
    # No debe provocar la expulsion adicional
    # de otra sesion valida.
    if exclude_session_id is not None:
        conditions.append(
            AuthSession.id
            != exclude_session_id
        )

    active_sessions = list(
        db.scalars(
            select(
                AuthSession
            )
            .where(
                *conditions
            )
            .order_by(
                AuthSession.created_at,
                AuthSession.id,
            )
            .with_for_update()
        )
    )

    maximum = max(
        1,
        settings
        .MAX_ACTIVE_SESSIONS_PER_USER,
    )

    # Dejamos un hueco para la nueva sesion.
    maximum_existing = max(
        0,
        maximum - 1,
    )

    excess = (
        len(active_sessions)
        - maximum_existing
    )

    if excess <= 0:
        return

    for session in (
        active_sessions[
            :excess
        ]
    ):
        session.revoked_at = now


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
    enforce_user_session_policy(
        db,
        user_id=user_id,
        exclude_session_id=
            rotated_from_id,
    )

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
