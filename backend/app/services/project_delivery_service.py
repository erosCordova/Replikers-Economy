from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ecosystem import AgentMessage
from app.models.project import Project
from app.services.activity_service import (
    record_activity,
)
from app.services.message_service import (
    record_message,
)


DELIVERY_MESSAGE_PREFIX = (
    "DECISIÓN DE ENTREGA — "
)


class DeliveryDecisionError(
    ValueError
):
    pass


def latest_delivery_decision(
    *,
    db: Session,
    project_id: int,
) -> AgentMessage | None:
    return db.scalar(
        select(
            AgentMessage
        )
        .where(
            AgentMessage.project_id
            == project_id,
            AgentMessage.message_type
            == "client_response",
            AgentMessage.content.like(
                f"{DELIVERY_MESSAGE_PREFIX}%"
            ),
        )
        .order_by(
            AgentMessage.created_at.desc(),
            AgentMessage.id.desc(),
        )
        .limit(1)
    )


def parse_delivery_message(
    message: AgentMessage | None,
) -> dict:
    if message is None:
        return {
            "decision": "pending",
            "comment": "",
            "review_attempt": None,
        }

    content = (
        message.content
        or ""
    )

    version_match = re.search(
        r"Versión v(\d+)",
        content,
    )

    review_attempt = (
        int(
            version_match.group(1)
        )
        if version_match
        else None
    )

    if (
        "Correcciones solicitadas."
        in content
    ):
        decision = (
            "corrections_requested"
        )

        marker = "Solicitud:"
    elif "Aceptada." in content:
        decision = "accepted"
        marker = "Comentario:"
    else:
        decision = "pending"
        marker = ""

    comment = ""

    if (
        marker
        and marker in content
    ):
        comment = (
            content
            .split(
                marker,
                1,
            )[1]
            .strip()
        )

    return {
        "decision":
            decision,

        "comment":
            comment,

        "review_attempt":
            review_attempt,
    }


def submit_delivery_decision(
    *,
    db: Session,
    project: Project,
    decision: str,
    comment: str,
    review_attempt: int,
) -> dict:
    normalized = (
        decision
        .strip()
        .lower()
    )

    if normalized not in {
        "accepted",
        "corrections_requested",
    }:
        raise DeliveryDecisionError(
            "Decisión de entrega inválida."
        )

    clean_comment = (
        comment
        .strip()
    )

    latest = latest_delivery_decision(
        db=db,
        project_id=project.id,
    )

    latest_data = (
        parse_delivery_message(
            latest
        )
    )

    if (
        latest_data["decision"]
        == "accepted"
    ):
        raise DeliveryDecisionError(
            "La entrega ya fue aceptada "
            "por el cliente."
        )

    if (
        normalized
        == "corrections_requested"
        and latest_data["decision"]
        == "corrections_requested"
        and latest_data[
            "review_attempt"
        ]
        == review_attempt
    ):
        raise DeliveryDecisionError(
            "Ya existe una solicitud "
            "de corrección para "
            "esta versión."
        )

    if normalized == "accepted":
        visible_content = (
            "DECISIÓN DE ENTREGA — "
            f"Versión v{review_attempt} — "
            "Aceptada. "
            "Comentario: "
            + (
                clean_comment
                or
                "Sin comentarios adicionales."
            )
        )

        event_type = (
            "client_delivery_accepted"
        )

        title = (
            "El cliente aceptó "
            "la entrega"
        )

        project.status = "completed"

    else:
        if len(
            clean_comment
        ) < 5:
            raise DeliveryDecisionError(
                "Describe qué debe corregirse."
            )

        visible_content = (
            "DECISIÓN DE ENTREGA — "
            f"Versión v{review_attempt} — "
            "Correcciones solicitadas. "
            f"Solicitud: {clean_comment}"
        )

        event_type = (
            "client_delivery_corrections_requested"
        )

        title = (
            "El cliente solicitó "
            "correcciones"
        )

        project.status = (
            "client_corrections_requested"
        )

    message = record_message(
        db=db,
        project_id=project.id,
        sender_type="project",
        receiver_type="r00",
        message_type="client_response",
        content=visible_content,
    )

    if message is None:
        raise DeliveryDecisionError(
            "No se pudo registrar "
            "la decisión."
        )

    record_activity(
        db=db,
        actor_type="client",
        event_type=event_type,
        project_id=project.id,
        title=title,
        description=visible_content,
    )

    db.flush()
    db.refresh(message)

    return {
        "project_id":
            project.id,

        "decision":
            normalized,

        "comment":
            clean_comment,

        "review_attempt":
            review_attempt,

        "created_at":
            message.created_at,
    }
