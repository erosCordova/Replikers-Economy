from sqlalchemy.orm import Session

from app.models.ecosystem import (
    AgentMessage,
)
from app.services.realtime_service import (
    record_realtime_event,
)


def record_message(
    *,
    db: Session,
    project_id: int,
    content: str,
    sender_type: str,
    receiver_type: str,
    message_type: str = "coordination",
    task_id: int | None = None,
    sender_repliker_id: int | None = None,
    receiver_repliker_id: int | None = None,
) -> AgentMessage | None:
    clean_content = (
        content.strip()
    )

    if not clean_content:
        return None

    clean_message_type = (
        message_type.strip()
        or "coordination"
    )

    message = AgentMessage(
        project_id=project_id,
        task_id=task_id,
        sender_type=sender_type,
        sender_repliker_id=
            sender_repliker_id,
        receiver_type=
            receiver_type,
        receiver_repliker_id=
            receiver_repliker_id,
        message_type=
            clean_message_type,
        content=
            clean_content,
    )

    db.add(message)

    record_realtime_event(
        db=db,
        kind="message",
        event_type=
            clean_message_type,
        title="Mensaje de agente",
        actor_type=
            sender_type,
        project_id=
            project_id,
        task_id=
            task_id,
        repliker_id=
            sender_repliker_id,
        payload={
            "content":
                clean_content,
            "sender_type":
                sender_type,
            "sender_repliker_id":
                sender_repliker_id,
            "receiver_type":
                receiver_type,
            "receiver_repliker_id":
                receiver_repliker_id,
        },
    )

    return message
