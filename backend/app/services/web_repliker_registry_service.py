from dataclasses import dataclass
from datetime import datetime, timezone
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.security import hash_password
from app.models.repliker import (
    Repliker,
    ReplikerSkill,
)
from app.models.user import User
from app.replikers.catalogo_web import (
    WEB_REPLIKERS,
)


ECOSYSTEM_OWNER_EMAIL = (
    "ecosystem@replikers.internal"
)

ECOSYSTEM_OWNER_NAME = (
    "Replikers Ecosystem"
)

ECOSYSTEM_OWNER_ROLE = "system"


@dataclass(frozen=True, slots=True)
class WebRegistryResult:
    owner_id: int
    owner_created: bool
    replikers_created: int
    replikers_updated: int
    skills_created: int
    skills_updated: int
    skills_removed: int
    total_replikers: int


def _get_or_create_ecosystem_owner(
    db: Session,
) -> tuple[User, bool]:
    owner = db.scalar(
        select(User).where(
            User.email
            == ECOSYSTEM_OWNER_EMAIL
        )
    )

    if owner is not None:
        if owner.role != ECOSYSTEM_OWNER_ROLE:
            raise RuntimeError(
                "El correo interno del ecosistema "
                "ya pertenece a un usuario que no "
                "tiene rol system."
            )

        owner.full_name = (
            ECOSYSTEM_OWNER_NAME
        )

        # Una cuenta interna del ecosistema no
        # debe poder iniciar sesión.
        owner.is_active = False

        return owner, False

    random_password = (
        secrets.token_urlsafe(48)
    )

    owner = User(
        full_name=
            ECOSYSTEM_OWNER_NAME,
        email=
            ECOSYSTEM_OWNER_EMAIL,
        password_hash=
            hash_password(
                random_password
            ),
        role=
            ECOSYSTEM_OWNER_ROLE,
        is_active=False,
    )

    db.add(owner)
    db.flush()

    return owner, True


def _sync_repliker_skills(
    *,
    db: Session,
    repliker: Repliker,
    desired_skills,
) -> tuple[int, int, int]:
    existing_by_name = {
        item.name.strip().lower(): item
        for item in repliker.skills
    }

    desired_names: set[str] = set()

    created = 0
    updated = 0
    removed = 0

    for definition in desired_skills:
        normalized = (
            definition.name
            .strip()
            .lower()
        )

        desired_names.add(normalized)

        existing = (
            existing_by_name.get(
                normalized
            )
        )

        if existing is None:
            db.add(
                ReplikerSkill(
                    repliker_id=
                        repliker.id,
                    name=
                        definition.name,
                    level=
                        definition.level,
                )
            )

            created += 1
            continue

        changed = False

        if existing.name != definition.name:
            existing.name = (
                definition.name
            )
            changed = True

        if existing.level != definition.level:
            existing.level = (
                definition.level
            )
            changed = True

        if changed:
            updated += 1

    for normalized, existing in (
        existing_by_name.items()
    ):
        if normalized in desired_names:
            continue

        db.delete(existing)
        removed += 1

    return (
        created,
        updated,
        removed,
    )


def ensure_web_repliker_registry(
    db: Session,
) -> WebRegistryResult:
    owner, owner_created = (
        _get_or_create_ecosystem_owner(
            db
        )
    )

    existing_replikers = list(
        db.scalars(
            select(Repliker)
            .options(
                selectinload(
                    Repliker.skills
                )
            )
            .where(
                Repliker.owner_id
                == owner.id
            )
        ).all()
    )

    existing_by_name = {
        repliker.name
        .strip()
        .lower():
            repliker
        for repliker
        in existing_replikers
    }

    replikers_created = 0
    replikers_updated = 0

    skills_created = 0
    skills_updated = 0
    skills_removed = 0

    for definition in WEB_REPLIKERS:
        normalized_name = (
            definition.name
            .strip()
            .lower()
        )

        repliker = (
            existing_by_name.get(
                normalized_name
            )
        )

        if repliker is None:
            repliker = Repliker(
                owner_id=owner.id,
                name=definition.name,
                specialty=
                    definition.specialty,
                description=
                    definition.description,
                status="available",
                reputation_score=50,
                base_price_credits=(
                    definition
                    .base_price_credits
                ),
                balance_credits=0,
                total_earnings_credits=0,
                jobs_completed=0,
                is_active=True,
                is_system=True,
                is_published=True,
                published_at=
                    datetime.now(
                        timezone.utc
                    ),
            )

            db.add(repliker)
            db.flush()

            existing_by_name[
                normalized_name
            ] = repliker

            replikers_created += 1

        else:
            changed = False

            expected_values = {
                "name":
                    definition.name,
                "specialty":
                    definition.specialty,
                "description":
                    definition.description,
                "base_price_credits":
                    definition
                    .base_price_credits,
                "is_active":
                    True,
                "is_system":
                    True,
                "is_published":
                    True,
            }

            for field, expected in (
                expected_values.items()
            ):
                if (
                    getattr(
                        repliker,
                        field,
                    )
                    != expected
                ):
                    setattr(
                        repliker,
                        field,
                        expected,
                    )
                    changed = True

            if repliker.published_at is None:
                repliker.published_at = (
                    datetime.now(
                        timezone.utc
                    )
                )
                changed = True

            if changed:
                replikers_updated += 1

        (
            created,
            updated,
            removed,
        ) = _sync_repliker_skills(
            db=db,
            repliker=repliker,
            desired_skills=
                definition.skills,
        )

        skills_created += created
        skills_updated += updated
        skills_removed += removed

    db.flush()

    total_replikers = len(
        db.scalars(
            select(Repliker)
            .where(
                Repliker.owner_id
                == owner.id
            )
        ).all()
    )

    db.commit()

    return WebRegistryResult(
        owner_id=owner.id,
        owner_created=
            owner_created,
        replikers_created=
            replikers_created,
        replikers_updated=
            replikers_updated,
        skills_created=
            skills_created,
        skills_updated=
            skills_updated,
        skills_removed=
            skills_removed,
        total_replikers=
            total_replikers,
    )
