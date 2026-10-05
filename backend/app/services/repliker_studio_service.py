from __future__ import annotations

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.orm import Session

from app.models.repliker import (
    Repliker,
    ReplikerSkill,
)
from app.models.repliker_studio import (
    ReplikerKnowledgeItem,
    ReplikerRule,
    ReplikerStudioProfile,
)
from app.schemas.repliker_studio import (
    ReplikerStudioUpdate,
)
from app.services.activity_service import (
    record_activity,
)
from app.services.agentic_service import (
    replace_repliker_tools,
    repliker_tool_profile,
)


from app.services.repliker_photo_service import (
    get_repliker_photo,
)
from app.services.repliker_publication_service import (
    validate_repliker_for_publication,
)


class ReplikerStudioError(
    ValueError
):
    pass


def _clean_required(
    value: str,
    *,
    field_name: str,
) -> str:
    result = value.strip()

    if not result:
        raise ReplikerStudioError(
            f"{field_name} no puede estar vacío."
        )

    return result


def _unique_titles(
    values,
    *,
    label: str,
):
    seen: set[str] = set()

    for value in values:
        normalized = (
            value.title
            .strip()
            .casefold()
        )

        if normalized in seen:
            raise ReplikerStudioError(
                f"Hay {label} con títulos repetidos."
            )

        seen.add(
            normalized
        )


def _knowledge_rows(
    *,
    db: Session,
    repliker_id: int,
):
    return list(
        db.scalars(
            select(
                ReplikerKnowledgeItem
            )
            .where(
                ReplikerKnowledgeItem
                .repliker_id
                == repliker_id
            )
            .order_by(
                ReplikerKnowledgeItem.id
            )
        ).all()
    )


def _rule_rows(
    *,
    db: Session,
    repliker_id: int,
):
    return list(
        db.scalars(
            select(
                ReplikerRule
            )
            .where(
                ReplikerRule.repliker_id
                == repliker_id
            )
            .order_by(
                ReplikerRule.priority.desc(),
                ReplikerRule.id,
            )
        ).all()
    )


def studio_snapshot(
    *,
    db: Session,
    repliker: Repliker,
) -> dict:
    profile = db.scalar(
        select(
            ReplikerStudioProfile
        )
        .where(
            ReplikerStudioProfile.repliker_id
            == repliker.id
        )
    )

    tool_profile = (
        repliker_tool_profile(
            db=db,
            repliker=repliker,
        )
    )

    knowledge = _knowledge_rows(
        db=db,
        repliker_id=repliker.id,
    )

    rules = _rule_rows(
        db=db,
        repliker_id=repliker.id,
    )

    return {
        "repliker_id":
            repliker.id,

        "owner_id":
            repliker.owner_id,

        "name":
            repliker.name,

        "specialty":
            repliker.specialty,

        "description":
            repliker.description,

        "base_price_credits":
            repliker.base_price_credits,

        "avatar_url":
            get_repliker_photo(
                db=db,
                repliker_id=repliker.id,
            ),

        "purpose":
            (
                profile.purpose
                if profile is not None
                else ""
            ),

        "personality":
            (
                profile.personality
                if profile is not None
                else ""
            ),

        "communication_style":
            (
                profile.communication_style
                if profile is not None
                else ""
            ),

        "instructions":
            (
                profile.instructions
                if profile is not None
                else ""
            ),

        "config_version":
            (
                profile.config_version
                if profile is not None
                else 0
            ),

        "skills": [
            {
                "id": skill.id,
                "name": skill.name,
                "level": skill.level,
            }
            for skill
            in repliker.skills
        ],

        "knowledge": [
            {
                "id": item.id,
                "title": item.title,
                "content": item.content,
                "enabled": item.enabled,
            }
            for item
            in knowledge
        ],

        "rules": [
            {
                "id": item.id,
                "title": item.title,
                "instruction":
                    item.instruction,
                "priority":
                    item.priority,
                "enabled":
                    item.enabled,
            }
            for item
            in rules
        ],

        "tools":
            tool_profile["tools"],

        "explicit_tool_configuration":
            tool_profile[
                "explicit_configuration"
            ],
    }


def update_repliker_studio(
    *,
    db: Session,
    repliker: Repliker,
    payload: ReplikerStudioUpdate,
) -> dict:
    name = _clean_required(
        payload.name,
        field_name="El nombre",
    )

    specialty = _clean_required(
        payload.specialty,
        field_name="La especialidad",
    )

    used_skills: set[str] = set()

    normalized_skills = []

    for skill in payload.skills:
        skill_name = _clean_required(
            skill.name,
            field_name=(
                "El nombre de la habilidad"
            ),
        )

        normalized = (
            skill_name.casefold()
        )

        if normalized in used_skills:
            raise ReplikerStudioError(
                "Hay habilidades repetidas."
            )

        used_skills.add(
            normalized
        )

        normalized_skills.append(
            (
                skill_name,
                skill.level,
            )
        )

    _unique_titles(
        payload.knowledge,
        label="conocimientos",
    )

    _unique_titles(
        payload.rules,
        label="reglas",
    )

    repliker.name = name

    repliker.specialty = specialty

    repliker.description = (
        payload.description.strip()
    )

    repliker.base_price_credits = (
        payload.base_price_credits
    )

    db.execute(
        delete(
            ReplikerSkill
        )
        .where(
            ReplikerSkill.repliker_id
            == repliker.id
        )
    )

    for (
        skill_name,
        skill_level,
    ) in normalized_skills:
        db.add(
            ReplikerSkill(
                repliker_id=
                    repliker.id,
                name=
                    skill_name,
                level=
                    skill_level,
            )
        )

    profile = db.scalar(
        select(
            ReplikerStudioProfile
        )
        .where(
            ReplikerStudioProfile.repliker_id
            == repliker.id
        )
    )

    if profile is None:
        profile = ReplikerStudioProfile(
            repliker_id=
                repliker.id,
            config_version=1,
        )

        db.add(
            profile
        )

    else:
        profile.config_version += 1

    profile.purpose = (
        payload.purpose.strip()
    )

    profile.personality = (
        payload.personality.strip()
    )

    profile.communication_style = (
        payload
        .communication_style
        .strip()
    )

    profile.instructions = (
        payload.instructions.strip()
    )

    db.execute(
        delete(
            ReplikerKnowledgeItem
        )
        .where(
            ReplikerKnowledgeItem.repliker_id
            == repliker.id
        )
    )

    for item in payload.knowledge:
        db.add(
            ReplikerKnowledgeItem(
                repliker_id=
                    repliker.id,
                title=
                    _clean_required(
                        item.title,
                        field_name=(
                            "El título del "
                            "conocimiento"
                        ),
                    ),
                content=
                    _clean_required(
                        item.content,
                        field_name=(
                            "El contenido del "
                            "conocimiento"
                        ),
                    ),
                source_type="manual",
                enabled=item.enabled,
            )
        )

    db.execute(
        delete(
            ReplikerRule
        )
        .where(
            ReplikerRule.repliker_id
            == repliker.id
        )
    )

    for item in payload.rules:
        db.add(
            ReplikerRule(
                repliker_id=
                    repliker.id,
                title=
                    _clean_required(
                        item.title,
                        field_name=(
                            "El título de la regla"
                        ),
                    ),
                instruction=
                    _clean_required(
                        item.instruction,
                        field_name=(
                            "La instrucción "
                            "de la regla"
                        ),
                    ),
                priority=
                    item.priority,
                enabled=
                    item.enabled,
            )
        )

    replace_repliker_tools(
        db=db,
        repliker=repliker,
        tool_names=
            payload.tool_names,
    )

    db.flush()

    # Recargamos las habilidades porque se
    # sustituyeron en esta misma transacción.
    db.expire(
        repliker,
        ["skills"],
    )

    if repliker.is_published:
        validate_repliker_for_publication(
            repliker
        )

    record_activity(
        db=db,
        actor_type="system",
        event_type=(
            "repliker_studio_updated"
        ),
        repliker_id=repliker.id,
        title=(
            f"Configuración actualizada "
            f"para {repliker.name}"
        ),
        description=(
            "El propietario actualizó el "
            "perfil, habilidades, conocimiento, "
            "reglas y herramientas del Repliker."
        ),
    )

    return studio_snapshot(
        db=db,
        repliker=repliker,
    )
