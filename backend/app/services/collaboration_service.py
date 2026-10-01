from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.models.collaboration import (
    ACTIVE_THREAD_STATUSES,
    CollaborationMessageState,
    CollaborationParticipant,
    CollaborationThread,
)
from app.models.contract import TaskContract
from app.models.ecosystem import (
    AgentMessage,
)
from app.models.project import Project
from app.models.repliker import Repliker
from app.models.task import Task
from app.schemas.collaboration import (
    CollaborationMessagePublic,
    CollaborationParticipantPublic,
    CollaborationProjectSnapshot,
    CollaborationThreadPublic,
)
from app.services.activity_service import (
    record_activity,
)
from app.services.message_service import (
    record_message,
)


ALLOWED_ACTOR_TYPES = {
    "project",
    "client",
    "r00",
    "repliker",
    "system",
}


class CollaborationError(Exception):
    pass


class CollaborationValidationError(
    CollaborationError
):
    pass


class CollaborationAuthorizationError(
    CollaborationError
):
    pass


def _now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _participant_key(
    actor_type: str,
    repliker_id: int | None = None,
) -> str:
    normalized = (
        actor_type
        .strip()
        .lower()
    )

    if normalized == "client":
        normalized = "project"

    if normalized == "repliker":
        if repliker_id is None:
            raise (
                CollaborationValidationError(
                    "Un participante Repliker "
                    "requiere repliker_id."
                )
            )

        return (
            f"repliker:{repliker_id}"
        )

    if normalized not in {
        "project",
        "r00",
        "system",
    }:
        raise (
            CollaborationValidationError(
                "Tipo de participante "
                "no permitido."
            )
        )

    return normalized


def _add_participant(
    *,
    db: Session,
    thread: CollaborationThread,
    participant_type: str,
    role: str,
    repliker_id: int | None = None,
) -> CollaborationParticipant:
    key = _participant_key(
        participant_type,
        repliker_id,
    )

    existing = db.scalar(
        select(
            CollaborationParticipant
        )
        .where(
            CollaborationParticipant
            .thread_id
            == thread.id,
            CollaborationParticipant
            .participant_key
            == key,
        )
    )

    if existing is not None:
        return existing

    participant = (
        CollaborationParticipant(
            thread_id=thread.id,
            participant_key=key,
            participant_type=(
                "project"
                if participant_type
                == "client"
                else participant_type
            ),
            repliker_id=repliker_id,
            role=role,
        )
    )

    db.add(
        participant
    )

    db.flush()

    return participant


def add_repliker_participant(
    *,
    db: Session,
    thread: CollaborationThread,
    repliker: Repliker,
    role: str = "collaborator",
) -> CollaborationParticipant:
    return _add_participant(
        db=db,
        thread=thread,
        participant_type="repliker",
        repliker_id=repliker.id,
        role=role,
    )


def _is_participant(
    *,
    db: Session,
    thread_id: int,
    actor_type: str,
    repliker_id: int | None,
) -> bool:
    if actor_type == "system":
        return True

    key = _participant_key(
        actor_type,
        repliker_id,
    )

    participant = db.scalar(
        select(
            CollaborationParticipant.id
        )
        .where(
            CollaborationParticipant
            .thread_id
            == thread_id,
            CollaborationParticipant
            .participant_key
            == key,
        )
    )

    return participant is not None


def _validate_task(
    *,
    project: Project,
    task: Task | None,
):
    if task is None:
        return

    if task.project_id != project.id:
        raise (
            CollaborationValidationError(
                "La tarea no pertenece "
                "al proyecto."
            )
        )


def _validate_contract(
    *,
    project: Project,
    task: Task | None,
    contract: TaskContract | None,
):
    if contract is None:
        return

    if contract.project_id != project.id:
        raise (
            CollaborationValidationError(
                "El contrato no pertenece "
                "al proyecto."
            )
        )

    if (
        task is not None
        and contract.task_id
        != task.id
    ):
        raise (
            CollaborationValidationError(
                "El contrato no corresponde "
                "a la tarea."
            )
        )


def ensure_task_execution_thread(
    *,
    db: Session,
    project: Project,
    task: Task,
    contract: TaskContract,
    repliker: Repliker,
) -> CollaborationThread:
    _validate_task(
        project=project,
        task=task,
    )

    _validate_contract(
        project=project,
        task=task,
        contract=contract,
    )

    if contract.repliker_id != repliker.id:
        raise (
            CollaborationValidationError(
                "El Repliker no corresponde "
                "al contrato."
            )
        )

    thread = db.scalar(
        select(
            CollaborationThread
        )
        .options(
            selectinload(
                CollaborationThread
                .participants
            )
        )
        .where(
            CollaborationThread
            .contract_id
            == contract.id,
            CollaborationThread.kind
            == "task_execution",
        )
    )

    if thread is None:
        thread = CollaborationThread(
            project_id=project.id,
            task_id=task.id,
            contract_id=contract.id,
            kind="task_execution",
            subject=(
                f"Coordinacion: "
                f"{task.title}"
            ),
            status="open",
            created_by_type="r00",
        )

        db.add(
            thread
        )

        db.flush()

        record_activity(
            db=db,
            actor_type="r00",
            event_type=(
                "collaboration_thread_opened"
            ),
            project_id=project.id,
            task_id=task.id,
            repliker_id=repliker.id,
            title=(
                "Canal de colaboracion abierto"
            ),
            description=(
                f"R00 abrio el canal del "
                f"contrato #{contract.id} "
                f"para '{task.title}'."
            ),
        )

    _add_participant(
        db=db,
        thread=thread,
        participant_type="project",
        role="client",
    )

    _add_participant(
        db=db,
        thread=thread,
        participant_type="r00",
        role="coordinator",
    )

    add_repliker_participant(
        db=db,
        thread=thread,
        repliker=repliker,
        role="assignee",
    )

    db.flush()

    return thread


def ensure_project_coordination_thread(
    *,
    db: Session,
    project: Project,
    task: Task | None = None,
) -> CollaborationThread:
    _validate_task(
        project=project,
        task=task,
    )

    statement = (
        select(
            CollaborationThread
        )
        .options(
            selectinload(
                CollaborationThread
                .participants
            )
        )
        .where(
            CollaborationThread
            .project_id
            == project.id,
            CollaborationThread.kind
            == "client_coordination",
            CollaborationThread.status.in_(
                ACTIVE_THREAD_STATUSES
            ),
        )
    )

    if task is None:
        statement = statement.where(
            CollaborationThread
            .task_id
            .is_(None)
        )
    else:
        statement = statement.where(
            CollaborationThread
            .task_id
            == task.id
        )

    thread = db.scalar(
        statement.order_by(
            CollaborationThread.id.desc()
        )
    )

    if thread is None:
        subject = (
            f"Coordinacion general: "
            f"{project.title}"
            if task is None
            else (
                f"Consulta del cliente: "
                f"{task.title}"
            )
        )

        thread = CollaborationThread(
            project_id=project.id,
            task_id=(
                task.id
                if task
                else None
            ),
            contract_id=None,
            kind="client_coordination",
            subject=subject,
            status="open",
            created_by_type="project",
        )

        db.add(
            thread
        )

        db.flush()

        record_activity(
            db=db,
            actor_type="project",
            event_type=(
                "client_coordination_opened"
            ),
            project_id=project.id,
            task_id=(
                task.id
                if task
                else None
            ),
            title=(
                "Canal cliente - R00 abierto"
            ),
            description=subject,
        )

    _add_participant(
        db=db,
        thread=thread,
        participant_type="project",
        role="client",
    )

    _add_participant(
        db=db,
        thread=thread,
        participant_type="r00",
        role="coordinator",
    )

    db.flush()

    return thread


def send_collaboration_message(
    *,
    db: Session,
    thread: CollaborationThread,
    sender_type: str,
    receiver_type: str,
    content: str,
    message_type: str = "coordination",
    sender_repliker_id: int | None = None,
    receiver_repliker_id: int | None = None,
    priority: str = "normal",
    requires_ack: bool = False,
    reply_to_message_id: int | None = None,
) -> AgentMessage:
    if (
        thread.status
        not in ACTIVE_THREAD_STATUSES
    ):
        raise (
            CollaborationValidationError(
                "El hilo de colaboracion "
                "ya esta cerrado."
            )
        )

    if sender_type not in ALLOWED_ACTOR_TYPES:
        raise (
            CollaborationValidationError(
                "Tipo de emisor invalido."
            )
        )

    if receiver_type not in ALLOWED_ACTOR_TYPES:
        raise (
            CollaborationValidationError(
                "Tipo de receptor invalido."
            )
        )

    clean_content = (
        content.strip()
    )

    if not clean_content:
        raise (
            CollaborationValidationError(
                "El mensaje no puede "
                "estar vacio."
            )
        )

    if len(clean_content) > 4000:
        raise (
            CollaborationValidationError(
                "El mensaje supera "
                "4000 caracteres."
            )
        )

    if priority not in {
        "low",
        "normal",
        "high",
        "urgent",
    }:
        raise (
            CollaborationValidationError(
                "Prioridad invalida."
            )
        )

    if not _is_participant(
        db=db,
        thread_id=thread.id,
        actor_type=sender_type,
        repliker_id=
            sender_repliker_id,
    ):
        raise (
            CollaborationAuthorizationError(
                "El emisor no pertenece "
                "a esta conversacion."
            )
        )

    if not _is_participant(
        db=db,
        thread_id=thread.id,
        actor_type=receiver_type,
        repliker_id=
            receiver_repliker_id,
    ):
        raise (
            CollaborationAuthorizationError(
                "El receptor no pertenece "
                "a esta conversacion."
            )
        )

    if reply_to_message_id is not None:
        parent_state = db.scalar(
            select(
                CollaborationMessageState
            )
            .where(
                CollaborationMessageState
                .message_id
                == reply_to_message_id
            )
        )

        if (
            parent_state is None
            or parent_state.thread_id
            != thread.id
        ):
            raise (
                CollaborationValidationError(
                    "La respuesta debe "
                    "pertenecer al mismo hilo."
                )
            )

    message = record_message(
        db=db,
        project_id=thread.project_id,
        task_id=thread.task_id,
        sender_type=sender_type,
        sender_repliker_id=
            sender_repliker_id,
        receiver_type=receiver_type,
        receiver_repliker_id=
            receiver_repliker_id,
        message_type=message_type,
        content=clean_content,
    )

    if message is None:
        raise (
            CollaborationValidationError(
                "No se pudo crear "
                "el mensaje."
            )
        )

    db.flush()

    state = CollaborationMessageState(
        message_id=message.id,
        thread_id=thread.id,
        contract_id=
            thread.contract_id,
        reply_to_message_id=
            reply_to_message_id,
        priority=priority,
        delivery_status="sent",
        requires_ack=requires_ack,
    )

    db.add(
        state
    )

    if message_type == "blocker":
        thread.status = "blocked"

        record_activity(
            db=db,
            actor_type=sender_type,
            event_type=(
                "collaboration_blocked"
            ),
            project_id=thread.project_id,
            task_id=thread.task_id,
            repliker_id=
                sender_repliker_id,
            title=(
                "Bloqueo reportado"
            ),
            description=clean_content,
        )

    elif message_type == "handoff":
        thread.status = "waiting"

        record_activity(
            db=db,
            actor_type=sender_type,
            event_type=(
                "collaboration_handoff"
            ),
            project_id=thread.project_id,
            task_id=thread.task_id,
            repliker_id=
                sender_repliker_id,
            title=(
                "Handoff solicitado"
            ),
            description=clean_content,
        )

    elif message_type == "client_request":
        record_activity(
            db=db,
            actor_type="project",
            event_type=(
                "client_request_sent"
            ),
            project_id=thread.project_id,
            task_id=thread.task_id,
            title=(
                "Cliente envio una solicitud"
            ),
            description=clean_content,
        )

    thread.updated_at = _now()

    db.flush()

    return message


def acknowledge_collaboration_message(
    *,
    db: Session,
    message_id: int,
    actor_type: str,
    actor_repliker_id: int | None = None,
) -> CollaborationMessageState:
    state = db.scalar(
        select(
            CollaborationMessageState
        )
        .where(
            CollaborationMessageState
            .message_id
            == message_id
        )
        .with_for_update()
    )

    if state is None:
        raise (
            CollaborationValidationError(
                "El mensaje no pertenece "
                "a la capa de colaboracion."
            )
        )

    message = db.get(
        AgentMessage,
        message_id,
    )

    if message is None:
        raise (
            CollaborationValidationError(
                "Mensaje no encontrado."
            )
        )

    expected_receiver = (
        _participant_key(
            message.receiver_type,
            message.receiver_repliker_id,
        )
    )

    actor_key = _participant_key(
        actor_type,
        actor_repliker_id,
    )

    if (
        actor_type != "system"
        and actor_key
        != expected_receiver
    ):
        raise (
            CollaborationAuthorizationError(
                "Este participante no puede "
                "confirmar el mensaje."
            )
        )

    if state.delivery_status == "resolved":
        return state

    if state.acknowledged_at is None:
        state.acknowledged_at = (
            _now()
        )

    state.delivery_status = (
        "acknowledged"
    )

    db.flush()

    return state


def resolve_collaboration_thread(
    *,
    db: Session,
    thread: CollaborationThread,
    resolver_type: str,
    resolver_repliker_id: int | None = None,
) -> CollaborationThread:
    if thread.status in {
        "resolved",
        "closed",
    }:
        return thread

    if not _is_participant(
        db=db,
        thread_id=thread.id,
        actor_type=resolver_type,
        repliker_id=
            resolver_repliker_id,
    ):
        raise (
            CollaborationAuthorizationError(
                "El participante no puede "
                "resolver este hilo."
            )
        )

    timestamp = _now()

    thread.status = "resolved"
    thread.updated_at = timestamp

    states = list(
        db.scalars(
            select(
                CollaborationMessageState
            )
            .where(
                CollaborationMessageState
                .thread_id
                == thread.id,
                CollaborationMessageState
                .delivery_status
                != "resolved",
            )
        ).all()
    )

    for state in states:
        state.delivery_status = (
            "resolved"
        )

        state.resolved_at = (
            timestamp
        )

    record_activity(
        db=db,
        actor_type=resolver_type,
        event_type=(
            "collaboration_thread_resolved"
        ),
        project_id=thread.project_id,
        task_id=thread.task_id,
        repliker_id=
            resolver_repliker_id,
        title=(
            "Conversacion resuelta"
        ),
        description=(
            thread.subject
        ),
    )

    db.flush()

    return thread


def _serialize_thread(
    *,
    thread: CollaborationThread,
    message_count: int,
) -> CollaborationThreadPublic:
    return CollaborationThreadPublic(
        id=thread.id,
        project_id=
            thread.project_id,
        task_id=
            thread.task_id,
        contract_id=
            thread.contract_id,
        kind=thread.kind,
        subject=thread.subject,
        status=thread.status,
        created_by_type=
            thread.created_by_type,
        participants=[
            CollaborationParticipantPublic(
                participant_key=
                    participant
                    .participant_key,
                participant_type=
                    participant
                    .participant_type,
                repliker_id=
                    participant
                    .repliker_id,
                role=
                    participant.role,
            )
            for participant
            in thread.participants
        ],
        message_count=
            message_count,
        created_at=
            thread.created_at,
        updated_at=
            thread.updated_at,
    )


def _serialize_message(
    *,
    message: AgentMessage,
    state:
        CollaborationMessageState | None,
    thread:
        CollaborationThread | None,
) -> CollaborationMessagePublic:
    return CollaborationMessagePublic(
        id=message.id,
        project_id=
            message.project_id,
        task_id=
            message.task_id,
        thread_id=(
            state.thread_id
            if state
            else None
        ),
        thread_subject=(
            thread.subject
            if thread
            else None
        ),
        contract_id=(
            state.contract_id
            if state
            else None
        ),
        reply_to_message_id=(
            state.reply_to_message_id
            if state
            else None
        ),
        sender_type=
            message.sender_type,
        sender_repliker_id=(
            message
            .sender_repliker_id
        ),
        receiver_type=
            message.receiver_type,
        receiver_repliker_id=(
            message
            .receiver_repliker_id
        ),
        message_type=
            message.message_type,
        content=
            message.content,
        priority=(
            state.priority
            if state
            else "normal"
        ),
        delivery_status=(
            state.delivery_status
            if state
            else "legacy"
        ),
        requires_ack=(
            state.requires_ack
            if state
            else False
        ),
        acknowledged_at=(
            state.acknowledged_at
            if state
            else None
        ),
        resolved_at=(
            state.resolved_at
            if state
            else None
        ),
        legacy=(
            state is None
        ),
        created_at=
            message.created_at,
    )


def get_collaboration_message_public(
    *,
    db: Session,
    message_id: int,
) -> CollaborationMessagePublic:
    message = db.get(
        AgentMessage,
        message_id,
    )

    if message is None:
        raise (
            CollaborationValidationError(
                "Mensaje no encontrado."
            )
        )

    state = db.scalar(
        select(
            CollaborationMessageState
        )
        .where(
            CollaborationMessageState
            .message_id
            == message.id
        )
    )

    thread = (
        db.get(
            CollaborationThread,
            state.thread_id,
        )
        if state
        else None
    )

    return _serialize_message(
        message=message,
        state=state,
        thread=thread,
    )


def build_collaboration_snapshot(
    *,
    db: Session,
    project: Project,
) -> CollaborationProjectSnapshot:
    threads = list(
        db.scalars(
            select(
                CollaborationThread
            )
            .options(
                selectinload(
                    CollaborationThread
                    .participants
                )
            )
            .where(
                CollaborationThread
                .project_id
                == project.id
            )
            .order_by(
                CollaborationThread
                .updated_at
                .desc(),
                CollaborationThread
                .id
                .desc(),
            )
        ).all()
    )

    thread_ids = [
        thread.id
        for thread
        in threads
    ]

    message_counts: dict[
        int,
        int,
    ] = {}

    if thread_ids:
        rows = db.execute(
            select(
                CollaborationMessageState
                .thread_id,
                func.count(
                    CollaborationMessageState
                    .id
                ),
            )
            .where(
                CollaborationMessageState
                .thread_id
                .in_(
                    thread_ids
                )
            )
            .group_by(
                CollaborationMessageState
                .thread_id
            )
        ).all()

        message_counts = {
            int(thread_id):
                int(count)
            for thread_id, count
            in rows
        }

    messages = list(
        db.scalars(
            select(
                AgentMessage
            )
            .where(
                AgentMessage.project_id
                == project.id
            )
            .order_by(
                AgentMessage.created_at
                .asc(),
                AgentMessage.id.asc(),
            )
            .limit(
                300
            )
        ).all()
    )

    message_ids = [
        message.id
        for message
        in messages
    ]

    states: list[
        CollaborationMessageState
    ] = []

    if message_ids:
        states = list(
            db.scalars(
                select(
                    CollaborationMessageState
                )
                .where(
                    CollaborationMessageState
                    .message_id
                    .in_(
                        message_ids
                    )
                )
            ).all()
        )

    state_map = {
        state.message_id:
            state
        for state
        in states
    }

    thread_map = {
        thread.id:
            thread
        for thread
        in threads
    }

    serialized_messages = []

    for message in messages:
        state = state_map.get(
            message.id
        )

        thread = (
            thread_map.get(
                state.thread_id
            )
            if state
            else None
        )

        serialized_messages.append(
            _serialize_message(
                message=message,
                state=state,
                thread=thread,
            )
        )

    return (
        CollaborationProjectSnapshot(
            project_id=project.id,
            threads=[
                _serialize_thread(
                    thread=thread,
                    message_count=(
                        message_counts
                        .get(
                            thread.id,
                            0,
                        )
                    ),
                )
                for thread
                in threads
            ],
            messages=
                serialized_messages,
        )
    )
