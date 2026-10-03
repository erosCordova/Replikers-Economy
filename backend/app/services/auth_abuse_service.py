from __future__ import annotations

from collections.abc import Callable
from datetime import (
    datetime,
    timedelta,
    timezone,
)
import hashlib
import hmac

from fastapi import Request
from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import (
    SessionLocal,
)
from app.models.auth_rate_limit import (
    AuthRateLimit,
)


class AuthRateLimitExceeded(
    ValueError
):
    def __init__(
        self,
        retry_after_seconds: int,
    ):
        self.retry_after_seconds = max(
            1,
            retry_after_seconds,
        )

        super().__init__(
            "Demasiadas solicitudes."
        )


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


def request_ip(
    request: Request,
) -> str:
    if (
        request.client is None
        or not request.client.host
    ):
        return "unknown"

    return (
        request.client.host
        .strip()
        .lower()
    )


def build_identity(
    request: Request,
    *,
    extra: str = "",
    include_ip: bool = True,
) -> str:
    parts: list[str] = []

    if include_ip:
        parts.append(
            request_ip(
                request
            )
        )

    normalized_extra = (
        extra.strip().lower()
    )

    if normalized_extra:
        parts.append(
            normalized_extra
        )

    if not parts:
        return "unknown"

    return "|".join(
        parts
    )


def hash_identity(
    *,
    action: str,
    identity: str,
) -> str:
    message = (
        action
        + "|"
        + identity
    ).encode(
        "utf-8"
    )

    return hmac.new(
        settings.SECRET_KEY.encode(
            "utf-8"
        ),
        message,
        hashlib.sha256,
    ).hexdigest()


def consume_auth_rate_limit(
    *,
    action: str,
    identity: str,
    max_requests: int,
    window_seconds: int,
    block_seconds: int,
    session_factory: Callable[
        [],
        Session,
    ] = SessionLocal,
) -> None:
    action = action.strip()

    if not action:
        raise ValueError(
            "action es obligatorio."
        )

    if max_requests < 1:
        raise ValueError(
            "max_requests debe ser positivo."
        )

    if window_seconds < 1:
        raise ValueError(
            "window_seconds debe ser positivo."
        )

    if block_seconds < 1:
        raise ValueError(
            "block_seconds debe ser positivo."
        )

    key_hash = hash_identity(
        action=action,
        identity=identity,
    )

    # Dos intentos resuelven la carrera
    # cuando dos procesos intentan crear
    # por primera vez la misma clave.
    for attempt in range(2):
        db = session_factory()

        try:
            now = utc_now()

            row = db.scalar(
                select(
                    AuthRateLimit
                )
                .where(
                    AuthRateLimit.action
                    == action,
                    AuthRateLimit.key_hash
                    == key_hash,
                )
                .with_for_update()
            )

            if row is None:
                row = AuthRateLimit(
                    action=action,
                    key_hash=key_hash,
                    window_started_at=now,
                    attempts=0,
                )

                db.add(
                    row
                )

                try:
                    db.flush()

                except IntegrityError:
                    db.rollback()

                    if attempt == 0:
                        continue

                    raise

            if (
                row.blocked_until
                is not None
            ):
                blocked_until = (
                    normalize_utc(
                        row.blocked_until
                    )
                )

                if blocked_until > now:
                    retry_after = max(
                        1,
                        int(
                            (
                                blocked_until
                                - now
                            ).total_seconds()
                        ),
                    )

                    db.commit()

                    raise (
                        AuthRateLimitExceeded(
                            retry_after
                        )
                    )

                row.blocked_until = None

            window_start = (
                normalize_utc(
                    row.window_started_at
                )
            )

            if (
                window_start
                + timedelta(
                    seconds=
                        window_seconds
                )
                <= now
            ):
                row.window_started_at = now
                row.attempts = 0

            row.attempts += 1

            if (
                row.attempts
                > max_requests
            ):
                row.blocked_until = (
                    now
                    + timedelta(
                        seconds=
                            block_seconds
                    )
                )

                db.commit()

                raise (
                    AuthRateLimitExceeded(
                        block_seconds
                    )
                )

            db.commit()

            return

        except AuthRateLimitExceeded:
            raise

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

    raise RuntimeError(
        "No se pudo actualizar "
        "el rate limit."
    )


def clear_auth_rate_limit(
    *,
    action: str,
    identity: str,
    session_factory: Callable[
        [],
        Session,
    ] = SessionLocal,
) -> None:
    clean_action = (
        action.strip()
    )

    if not clean_action:
        return

    key_hash = hash_identity(
        action=clean_action,
        identity=identity,
    )

    db = session_factory()

    try:
        db.execute(
            delete(
                AuthRateLimit
            )
            .where(
                AuthRateLimit.action
                == clean_action,
                AuthRateLimit.key_hash
                == key_hash,
            )
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
