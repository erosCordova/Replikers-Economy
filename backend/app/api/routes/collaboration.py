from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.collaboration import (
    CollaborationMessageState,
    CollaborationThread,
)
from app.models.ecosystem import (
    AgentMessage,
)
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.collaboration import (
    ClientMessageCreate,
    ClientReplyCreate,
    CollaborationActionResponse,
    CollaborationMessagePublic,
    CollaborationProjectSnapshot,
)
from app.services.collaboration_service import (
    CollaborationAuthorizationError,
    CollaborationValidationError,
    acknowledge_collaboration_message,
    build_collaboration_snapshot,
    ensure_project_coordination_thread,
    get_collaboration_message_public,
    resolve_collaboration_thread,
    send_collaboration_message,
)


router = APIRouter(
    prefix="/collaboration",
    tags=[
        "Colaboracion",
    ],
)


def _project_or_404(
    *,
    db: Session,
    project_id: int,
) -> Project:
    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Proyecto no encontrado."
            ),
        )

    return project


def _check_project_access(
    *,
    project: Project,
    current_user: User,
):
    if (
        project.client_id
        != current_user.id
        and current_user.role
        != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes acceso "
                "a este proyecto."
            ),
        )


def _handle_collaboration_error(
    exc: Exception,
):
    if isinstance(
        exc,
        CollaborationAuthorizationError,
    ):
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    if isinstance(
        exc,
        CollaborationValidationError,
    ):
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    raise exc


@router.get(
    "/projects/{project_id}",
    response_model=
        CollaborationProjectSnapshot,
)
def get_project_collaboration(
    project_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = _project_or_404(
        db=db,
        project_id=project_id,
    )

    _check_project_access(
        project=project,
        current_user=current_user,
    )

    return build_collaboration_snapshot(
        db=db,
        project=project,
    )


@router.post(
    "/projects/{project_id}/messages",
    response_model=
        CollaborationMessagePublic,
)
def send_client_message(
    project_id: int,
    payload: ClientMessageCreate,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = _project_or_404(
        db=db,
        project_id=project_id,
    )

    _check_project_access(
        project=project,
        current_user=current_user,
    )

    task = None

    if payload.task_id is not None:
        task = db.get(
            Task,
            payload.task_id,
        )

        if (
            task is None
            or task.project_id
            != project.id
        ):
            raise HTTPException(
                status_code=404,
                detail=(
                    "Tarea no encontrada "
                    "en este proyecto."
                ),
            )

    try:
        thread = (
            ensure_project_coordination_thread(
                db=db,
                project=project,
                task=task,
            )
        )

        message = (
            send_collaboration_message(
                db=db,
                thread=thread,
                sender_type="project",
                receiver_type="r00",
                message_type="client_request",
                content=payload.content,
                priority=
                    payload.priority,
                requires_ack=True,
            )
        )

        db.commit()

        return (
            get_collaboration_message_public(
                db=db,
                message_id=message.id,
            )
        )

    except Exception as exc:
        db.rollback()
        _handle_collaboration_error(
            exc
        )


@router.post(
    "/threads/{thread_id}/reply",
    response_model=
        CollaborationMessagePublic,
)
def reply_to_thread(
    thread_id: int,
    payload: ClientReplyCreate,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    thread = db.get(
        CollaborationThread,
        thread_id,
    )

    if thread is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Conversacion no encontrada."
            ),
        )

    project = _project_or_404(
        db=db,
        project_id=
            thread.project_id,
    )

    _check_project_access(
        project=project,
        current_user=current_user,
    )

    try:
        message = (
            send_collaboration_message(
                db=db,
                thread=thread,
                sender_type="project",
                receiver_type="r00",
                message_type="client_response",
                content=payload.content,
                priority=
                    payload.priority,
                requires_ack=True,
                reply_to_message_id=(
                    payload
                    .reply_to_message_id
                ),
            )
        )

        db.commit()

        return (
            get_collaboration_message_public(
                db=db,
                message_id=message.id,
            )
        )

    except Exception as exc:
        db.rollback()
        _handle_collaboration_error(
            exc
        )


@router.post(
    "/messages/{message_id}/acknowledge",
    response_model=
        CollaborationActionResponse,
)
def acknowledge_client_message(
    message_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    message = db.get(
        AgentMessage,
        message_id,
    )

    if message is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Mensaje no encontrado."
            ),
        )

    project = _project_or_404(
        db=db,
        project_id=
            message.project_id,
    )

    _check_project_access(
        project=project,
        current_user=current_user,
    )

    if message.receiver_type not in {
        "project",
        "client",
    }:
        raise HTTPException(
            status_code=403,
            detail=(
                "El cliente no es el "
                "receptor de este mensaje."
            ),
        )

    try:
        acknowledge_collaboration_message(
            db=db,
            message_id=message.id,
            actor_type="project",
        )

        db.commit()

        return (
            CollaborationActionResponse(
                success=True,
                message=(
                    "Mensaje confirmado."
                ),
            )
        )

    except Exception as exc:
        db.rollback()
        _handle_collaboration_error(
            exc
        )


@router.post(
    "/threads/{thread_id}/resolve",
    response_model=
        CollaborationActionResponse,
)
def resolve_client_thread(
    thread_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    thread = db.get(
        CollaborationThread,
        thread_id,
    )

    if thread is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Conversacion no encontrada."
            ),
        )

    project = _project_or_404(
        db=db,
        project_id=
            thread.project_id,
    )

    _check_project_access(
        project=project,
        current_user=current_user,
    )

    if (
        thread.kind
        != "client_coordination"
        and current_user.role
        != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Los canales operativos "
                "de tareas son cerrados "
                "por R00."
            ),
        )

    try:
        resolve_collaboration_thread(
            db=db,
            thread=thread,
            resolver_type="project",
        )

        db.commit()

        return (
            CollaborationActionResponse(
                success=True,
                message=(
                    "Conversacion resuelta."
                ),
            )
        )

    except Exception as exc:
        db.rollback()
        _handle_collaboration_error(
            exc
        )
