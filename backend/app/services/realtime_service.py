from __future__ import annotations

import json

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.realtime import (
    REALTIME_EVENT_KINDS,
    RealtimeEvent,
)
from app.models.project import Project


class RealtimeEventError(
    ValueError
):
    pass


def record_realtime_event(
    *,
    db: Session,
    kind: str,
    event_type: str,
    title: str = "",
    actor_type: str = "system",
    project_id: int | None = None,
    task_id: int | None = None,
    repliker_id: int | None = None,
    payload:
        Mapping[str, Any]
        | None = None,
) -> RealtimeEvent:
    normalized_kind = (
        kind.strip().lower()
    )

    if (
        normalized_kind
        not in REALTIME_EVENT_KINDS
    ):
        raise RealtimeEventError(
            "Tipo de evento realtime "
            "invalido."
        )

    normalized_type = (
        event_type.strip()
    )

    if not normalized_type:
        raise RealtimeEventError(
            "event_type es obligatorio."
        )

    if len(normalized_type) > 80:
        raise RealtimeEventError(
            "event_type excede "
            "el limite permitido."
        )

    serialized_payload = json.dumps(
        dict(payload or {}),
        ensure_ascii=False,
        separators=(
            ",",
            ":",
        ),
        default=str,
    )

    event = RealtimeEvent(
        project_id=project_id,
        task_id=task_id,
        repliker_id=repliker_id,
        kind=normalized_kind,
        event_type=
            normalized_type,
        actor_type=(
            actor_type.strip()
            or "system"
        ),
        title=title.strip()[:180],
        payload_json=
            serialized_payload,
    )

    db.add(event)

    return event


def event_payload(
    event: RealtimeEvent,
) -> dict[str, Any]:
    try:
        data = json.loads(
            event.payload_json
            or "{}"
        )

    except json.JSONDecodeError as exc:
        raise RealtimeEventError(
            "El payload del evento "
            "no contiene JSON valido."
        ) from exc

    if not isinstance(
        data,
        dict,
    ):
        raise RealtimeEventError(
            "El payload debe ser "
            "un objeto JSON."
        )

    return data


def list_project_realtime_events(
    *,
    db: Session,
    project_id: int,
    after_id: int = 0,
    limit: int = 100,
) -> list[RealtimeEvent]:
    safe_after = max(
        0,
        int(after_id),
    )

    safe_limit = max(
        1,
        min(
            int(limit),
            500,
        ),
    )

    return list(
        db.scalars(
            select(
                RealtimeEvent
            )
            .where(
                RealtimeEvent
                .project_id
                == project_id,
                RealtimeEvent.id
                > safe_after,
            )
            .order_by(
                RealtimeEvent.id.asc()
            )
            .limit(
                safe_limit
            )
        ).all()
    )


def latest_project_event_id(
    *,
    db: Session,
    project_id: int,
) -> int:
    event = db.scalar(
        select(
            RealtimeEvent
        )
        .where(
            RealtimeEvent
            .project_id
            == project_id
        )
        .order_by(
            RealtimeEvent.id.desc()
        )
        .limit(1)
    )

    if event is None:
        return 0

    return int(
        event.id
    )


def record_workflow_event(
    *,
    db: Session,
    project_id: int,
    stage: str,
    status: str,
    title: str = "",
    actor_type: str = "langgraph",
    kind: str = "workflow",
    payload:
        Mapping[str, Any]
        | None = None,
) -> RealtimeEvent:
    """
    Evento durable de una etapa LangGraph.

    kind='economy' se usa para acontecimientos
    economicos que deben distinguirse de las
    transiciones normales del workflow.
    """

    clean_stage = (
        stage
        .strip()
        .lower()
        .replace(" ", "_")
    )

    clean_status = (
        status
        .strip()
        .lower()
        .replace(" ", "_")
    )

    if not clean_stage:
        raise RealtimeEventError(
            "La etapa realtime "
            "es obligatoria."
        )

    if not clean_status:
        raise RealtimeEventError(
            "El estado realtime "
            "es obligatorio."
        )

    if kind not in {
        "workflow",
        "economy",
    }:
        raise RealtimeEventError(
            "Tipo de evento de workflow "
            "no permitido."
        )

    if kind == "economy":
        event_type = (
            f"economy_{clean_status}"
        )
    else:
        event_type = (
            f"workflow_"
            f"{clean_stage}_"
            f"{clean_status}"
        )

    event_title = (
        title.strip()
        if title.strip()
        else (
            f"{clean_stage}: "
            f"{clean_status}"
        )
    )

    full_payload = {
        "stage":
            clean_stage,
        "status":
            clean_status,
        **dict(
            payload
            or {}
        ),
    }

    return record_realtime_event(
        db=db,
        kind=kind,
        event_type=event_type,
        title=event_title,
        actor_type=actor_type,
        project_id=project_id,
        payload=full_payload,
    )



def list_account_realtime_events(
    *,
    db: Session,
    user_id: int,
    is_admin: bool,
    after_id: int = 0,
    limit: int = 100,
) -> list[RealtimeEvent]:
    """
    Stream consolidado para una cuenta.

    Un usuario normal recibe eventos
    solamente de sus propios proyectos.

    Un administrador puede observar todos.
    """

    safe_after = max(
        0,
        int(after_id),
    )

    safe_limit = max(
        1,
        min(
            int(limit),
            500,
        ),
    )

    statement = (
        select(
            RealtimeEvent
        )
        .where(
            RealtimeEvent.id
            > safe_after
        )
    )

    if not is_admin:
        statement = (
            statement
            .join(
                Project,
                Project.id
                == RealtimeEvent.project_id,
            )
            .where(
                Project.client_id
                == user_id
            )
        )

    statement = (
        statement
        .order_by(
            RealtimeEvent.id.asc()
        )
        .limit(
            safe_limit
        )
    )

    return list(
        db.scalars(
            statement
        ).all()
    )
