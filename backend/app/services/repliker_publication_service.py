from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from app.models.repliker import (
    Repliker,
)


class ReplikerPublicationError(
    ValueError
):
    pass


def validate_repliker_for_publication(
    repliker: Repliker,
) -> None:
    if repliker.is_system:
        raise ReplikerPublicationError(
            "Los Replikers oficiales "
            "son administrados internamente."
        )

    if not repliker.is_active:
        raise ReplikerPublicationError(
            "El Repliker debe estar activo "
            "antes de publicarse."
        )

    if not repliker.name.strip():
        raise ReplikerPublicationError(
            "El Repliker necesita un nombre."
        )

    if not repliker.specialty.strip():
        raise ReplikerPublicationError(
            "El Repliker necesita "
            "una especialidad."
        )

    if not repliker.description.strip():
        raise ReplikerPublicationError(
            "Añade una descripción antes "
            "de publicar el Repliker."
        )

    skills = [
        item
        for item
        in repliker.skills
        if item.name.strip()
    ]

    if not skills:
        raise ReplikerPublicationError(
            "Añade al menos una habilidad "
            "antes de publicar el Repliker."
        )


def set_repliker_publication(
    *,
    repliker: Repliker,
    published: bool,
) -> Repliker:
    if repliker.is_system:
        raise ReplikerPublicationError(
            "Los Replikers oficiales "
            "no pueden modificarse "
            "desde el Taller."
        )

    if published:
        validate_repliker_for_publication(
            repliker
        )

        repliker.is_published = True

        repliker.published_at = (
            datetime.now(
                timezone.utc
            )
        )

    else:
        repliker.is_published = False
        repliker.published_at = None

    return repliker
