from sqlalchemy.orm import Session

from app.models.ecosystem import (
    AgentActivityEvent,
)
from app.services.realtime_service import (
    record_realtime_event,
)


def record_activity(
    *,
    db: Session,
    event_type: str,
    title: str,
    description: str = "",
    actor_type: str = "system",
    project_id: int | None = None,
    task_id: int | None = None,
    repliker_id: int | None = None,
) -> AgentActivityEvent:
    clean_event_type = (
        event_type.strip()
    )

    clean_title = (
        title.strip()
    )

    clean_description = (
        description.strip()
    )

    event = AgentActivityEvent(
        project_id=project_id,
        task_id=task_id,
        repliker_id=repliker_id,
        actor_type=actor_type,
        event_type=
            clean_event_type,
        title=clean_title,
        description=
            clean_description,
    )

    db.add(event)

    record_realtime_event(
        db=db,
        kind="activity",
        event_type=
            clean_event_type,
        title=clean_title,
        actor_type=
            actor_type,
        project_id=
            project_id,
        task_id=
            task_id,
        repliker_id=
            repliker_id,
        payload={
            "description":
                clean_description,
        },
    )

    return event
