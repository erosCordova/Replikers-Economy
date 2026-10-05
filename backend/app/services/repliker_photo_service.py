from __future__ import annotations

import base64
import binascii
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ecosystem import (
    ReplikerAppearance,
)
from app.models.repliker import Repliker
from app.services.activity_service import (
    record_activity,
)


MAX_PHOTO_BYTES = 600_000

PHOTO_DATA_URL_PATTERN = re.compile(
    r"^data:"
    r"(image/(?:jpeg|png|webp));"
    r"base64,"
    r"(.+)$",
    re.DOTALL,
)


class ReplikerPhotoError(
    ValueError
):
    pass


def _appearance(
    *,
    db: Session,
    repliker_id: int,
) -> ReplikerAppearance | None:
    return db.scalar(
        select(
            ReplikerAppearance
        )
        .where(
            ReplikerAppearance.repliker_id
            == repliker_id
        )
    )


def get_repliker_photo(
    *,
    db: Session,
    repliker_id: int,
) -> str | None:
    appearance = _appearance(
        db=db,
        repliker_id=repliker_id,
    )

    if appearance is None:
        return None

    value = (
        appearance.avatar_url
        or ""
    ).strip()

    return value or None


def _validate_signature(
    *,
    media_type: str,
    content: bytes,
) -> None:
    if media_type == "image/png":
        valid = content.startswith(
            b"\x89PNG\r\n\x1a\n"
        )

    elif media_type == "image/jpeg":
        valid = content.startswith(
            b"\xff\xd8\xff"
        )

    elif media_type == "image/webp":
        valid = (
            len(content) >= 12
            and content[:4] == b"RIFF"
            and content[8:12] == b"WEBP"
        )

    else:
        valid = False

    if not valid:
        raise ReplikerPhotoError(
            "El contenido de la imagen "
            "no coincide con su formato."
        )


def validate_photo_data_url(
    value: str,
) -> str:
    candidate = value.strip()

    match = PHOTO_DATA_URL_PATTERN.fullmatch(
        candidate
    )

    if match is None:
        raise ReplikerPhotoError(
            "La foto debe ser JPG, PNG "
            "o WebP."
        )

    media_type = (
        match.group(1)
        .lower()
    )

    encoded = (
        match.group(2)
        .replace("\n", "")
        .replace("\r", "")
    )

    try:
        content = base64.b64decode(
            encoded,
            validate=True,
        )

    except (
        binascii.Error,
        ValueError,
    ) as exc:
        raise ReplikerPhotoError(
            "La imagen contiene datos "
            "inválidos."
        ) from exc

    if not content:
        raise ReplikerPhotoError(
            "La imagen está vacía."
        )

    if len(content) > MAX_PHOTO_BYTES:
        raise ReplikerPhotoError(
            "La foto optimizada supera "
            "el tamaño permitido."
        )

    _validate_signature(
        media_type=media_type,
        content=content,
    )

    normalized = (
        base64.b64encode(
            content
        )
        .decode("ascii")
    )

    return (
        f"data:{media_type};"
        f"base64,{normalized}"
    )


def save_repliker_photo(
    *,
    db: Session,
    repliker: Repliker,
    image_data_url: str,
) -> dict:
    normalized = (
        validate_photo_data_url(
            image_data_url
        )
    )

    appearance = _appearance(
        db=db,
        repliker_id=repliker.id,
    )

    if appearance is None:
        appearance = (
            ReplikerAppearance(
                repliker_id=
                    repliker.id,
            )
        )

        db.add(
            appearance
        )

    appearance.avatar_url = (
        normalized
    )

    db.flush()

    record_activity(
        db=db,
        actor_type="system",
        event_type=(
            "repliker_photo_updated"
        ),
        repliker_id=repliker.id,
        title=(
            f"Foto actualizada para "
            f"{repliker.name}"
        ),
        description=(
            "Se actualizó la foto "
            "de identificación del Repliker."
        ),
    )

    return {
        "repliker_id":
            repliker.id,

        "avatar_url":
            normalized,
    }


def remove_repliker_photo(
    *,
    db: Session,
    repliker: Repliker,
) -> dict:
    appearance = _appearance(
        db=db,
        repliker_id=repliker.id,
    )

    if appearance is not None:
        appearance.avatar_url = None

    db.flush()

    record_activity(
        db=db,
        actor_type="system",
        event_type=(
            "repliker_photo_removed"
        ),
        repliker_id=repliker.id,
        title=(
            f"Foto eliminada de "
            f"{repliker.name}"
        ),
        description=(
            "Se eliminó la foto "
            "de identificación del Repliker."
        ),
    )

    return {
        "repliker_id":
            repliker.id,

        "avatar_url":
            None,
    }
