from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hasher = (
    PasswordHash.recommended()
)


# Hash artificial para que un login con
# correo inexistente siga realizando una
# verificacion criptografica.
DUMMY_PASSWORD_HASH = (
    password_hasher.hash(
        "replikers-dummy-password-value"
    )
)


def hash_password(
    password: str,
) -> str:
    return password_hasher.hash(
        password
    )


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hasher.verify(
        plain_password,
        hashed_password,
    )


def verify_password_constant_time(
    plain_password: str,
    hashed_password: str | None,
) -> bool:
    candidate_hash = (
        hashed_password
        or DUMMY_PASSWORD_HASH
    )

    valid = verify_password(
        plain_password,
        candidate_hash,
    )

    return (
        hashed_password is not None
        and valid
    )


def create_access_token(
    user_id: int,
    role: str,
) -> str:
    now = datetime.now(
        timezone.utc
    )

    expires = (
        now
        + timedelta(
            minutes=
                settings
                .ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    payload = {
        "sub":
            str(user_id),

        "role":
            role,

        "iat":
            now,

        "nbf":
            now,

        "exp":
            expires,

        "iss":
            settings.JWT_ISSUER,

        "aud":
            settings.JWT_AUDIENCE,

        "jti":
            uuid4().hex,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=
            settings.ALGORITHM,
    )


def decode_access_token(
    token: str,
) -> dict:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[
            settings.ALGORITHM,
        ],
        audience=
            settings.JWT_AUDIENCE,
        issuer=
            settings.JWT_ISSUER,
        leeway=
            settings.JWT_LEEWAY_SECONDS,
        options={
            "require": [
                "sub",
                "iat",
                "nbf",
                "exp",
                "iss",
                "aud",
                "jti",
            ],
        },
    )
