from sqlalchemy.orm import Session

from app.models.ecosystem import AgentActivityEvent


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
    event = AgentActivityEvent(
        project_id=project_id,
        task_id=task_id,
        repliker_id=repliker_id,
        actor_type=actor_type,
        event_type=event_type.strip(),
        title=title.strip(),
        description=description.strip(),
    )

    db.add(event)

    return event
