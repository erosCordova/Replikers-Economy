from __future__ import annotations

import asyncio
import json
import time

from collections.abc import Callable

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import (
    StreamingResponse,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.database.session import (
    SessionLocal,
)
from app.models.project import Project
from app.models.realtime import (
    RealtimeEvent,
)
from app.models.user import User
from app.services.realtime_service import (
    event_payload,
    list_project_realtime_events,
)


router = APIRouter(
    prefix="/realtime",
    tags=[
        "Tiempo real",
    ],
)


SSE_POLL_SECONDS = 1.0
SSE_HEARTBEAT_SECONDS = 15.0
SSE_RETRY_MILLISECONDS = 2000
SSE_BATCH_LIMIT = 100


def assert_project_stream_access(
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
                "al stream de este proyecto."
            ),
        )


def resolve_sse_cursor(
    *,
    after_id: int,
    last_event_id: str | None,
) -> int:
    """
    Last-Event-ID tiene prioridad cuando
    el cliente esta reconectando.
    """

    fallback = max(
        0,
        int(after_id),
    )

    if last_event_id is None:
        return fallback

    value = (
        last_event_id.strip()
    )

    if not value:
        return fallback

    try:
        parsed = int(
            value
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Last-Event-ID invalido."
            ),
        ) from exc

    if parsed < 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Last-Event-ID invalido."
            ),
        )

    return parsed


def serialize_sse_event(
    event: RealtimeEvent,
) -> str:
    data = {
        "id":
            event.id,
        "project_id":
            event.project_id,
        "task_id":
            event.task_id,
        "repliker_id":
            event.repliker_id,
        "kind":
            event.kind,
        "event_type":
            event.event_type,
        "actor_type":
            event.actor_type,
        "title":
            event.title,
        "payload":
            event_payload(
                event
            ),
        "created_at": (
            event.created_at.isoformat()
            if event.created_at
            else None
        ),
    }

    encoded = json.dumps(
        data,
        ensure_ascii=False,
        separators=(
            ",",
            ":",
        ),
        default=str,
    )

    return (
        f"id: {event.id}\n"
        f"event: {event.kind}\n"
        f"data: {encoded}\n\n"
    )


def serialize_sse_heartbeat() -> str:
    return (
        ": heartbeat\n\n"
    )


def serialize_sse_retry() -> str:
    return (
        f"retry: "
        f"{SSE_RETRY_MILLISECONDS}"
        "\n\n"
    )


def _read_event_batch(
    *,
    session_factory: Callable,
    project_id: int,
    after_id: int,
) -> list[RealtimeEvent]:
    db = session_factory()

    try:
        return (
            list_project_realtime_events(
                db=db,
                project_id=
                    project_id,
                after_id=
                    after_id,
                limit=
                    SSE_BATCH_LIMIT,
            )
        )

    finally:
        db.close()


async def project_event_stream(
    *,
    request: Request,
    project_id: int,
    start_after_id: int,
    session_factory:
        Callable = SessionLocal,
    poll_seconds: float =
        SSE_POLL_SECONDS,
    heartbeat_seconds: float =
        SSE_HEARTBEAT_SECONDS,
    max_cycles: int | None = None,
):
    """
    Generador SSE durable.

    Abre una sesion DB corta por lectura.
    No mantiene una conexion SQL abierta
    durante toda la vida del stream.

    max_cycles se usa en pruebas para
    poder validar el generador sin dejar
    una conexion infinita.
    """

    cursor = max(
        0,
        int(start_after_id),
    )

    last_heartbeat = (
        time.monotonic()
    )

    cycles = 0

    yield serialize_sse_retry()

    while True:
        if await request.is_disconnected():
            break

        events = await asyncio.to_thread(
            _read_event_batch,
            session_factory=
                session_factory,
            project_id=
                project_id,
            after_id=
                cursor,
        )

        if events:
            for event in events:
                cursor = max(
                    cursor,
                    int(event.id),
                )

                yield serialize_sse_event(
                    event
                )

            last_heartbeat = (
                time.monotonic()
            )

        else:
            now = time.monotonic()

            if (
                now
                - last_heartbeat
                >= heartbeat_seconds
            ):
                yield (
                    serialize_sse_heartbeat()
                )

                last_heartbeat = now

        cycles += 1

        if (
            max_cycles is not None
            and cycles >= max_cycles
        ):
            break

        await asyncio.sleep(
            max(
                0.01,
                poll_seconds,
            )
        )


@router.get(
    "/projects/{project_id}/stream",
)
async def stream_project_events(
    project_id: int,
    request: Request,
    after_id: int = Query(
        default=0,
        ge=0,
    ),
    last_event_id: str | None = Header(
        default=None,
        alias="Last-Event-ID",
    ),
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
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

    assert_project_stream_access(
        project=project,
        current_user=current_user,
    )

    cursor = resolve_sse_cursor(
        after_id=after_id,
        last_event_id=
            last_event_id,
    )

    return StreamingResponse(
        project_event_stream(
            request=request,
            project_id=
                project.id,
            start_after_id=
                cursor,
        ),
        media_type=
            "text/event-stream",
        headers={
            "Cache-Control":
                "no-cache, no-transform",
            "Connection":
                "keep-alive",
            "X-Accel-Buffering":
                "no",
        },
    )


def _read_account_event_batch(
    *,
    session_factory: Callable,
    user_id: int,
    is_admin: bool,
    after_id: int,
) -> list[RealtimeEvent]:
    from app.services.realtime_service import (
        list_account_realtime_events,
    )

    db = session_factory()

    try:
        return (
            list_account_realtime_events(
                db=db,
                user_id=user_id,
                is_admin=is_admin,
                after_id=after_id,
                limit=SSE_BATCH_LIMIT,
            )
        )

    finally:
        db.close()


async def account_event_stream(
    *,
    request: Request,
    user_id: int,
    is_admin: bool,
    start_after_id: int,
    session_factory:
        Callable = SessionLocal,
    poll_seconds: float =
        SSE_POLL_SECONDS,
    heartbeat_seconds: float =
        SSE_HEARTBEAT_SECONDS,
    max_cycles: int | None = None,
):
    cursor = max(
        0,
        int(start_after_id),
    )

    last_heartbeat = (
        time.monotonic()
    )

    cycles = 0

    yield serialize_sse_retry()

    while True:
        if await request.is_disconnected():
            break

        events = await asyncio.to_thread(
            _read_account_event_batch,
            session_factory=
                session_factory,
            user_id=
                user_id,
            is_admin=
                is_admin,
            after_id=
                cursor,
        )

        if events:
            for event in events:
                cursor = max(
                    cursor,
                    int(event.id),
                )

                yield serialize_sse_event(
                    event
                )

            last_heartbeat = (
                time.monotonic()
            )

        else:
            now = time.monotonic()

            if (
                now
                - last_heartbeat
                >= heartbeat_seconds
            ):
                yield (
                    serialize_sse_heartbeat()
                )

                last_heartbeat = now

        cycles += 1

        if (
            max_cycles is not None
            and cycles >= max_cycles
        ):
            break

        await asyncio.sleep(
            max(
                0.01,
                poll_seconds,
            )
        )


@router.get(
    "/mine/stream",
)
async def stream_my_events(
    request: Request,
    after_id: int = Query(
        default=0,
        ge=0,
    ),
    last_event_id: str | None = Header(
        default=None,
        alias="Last-Event-ID",
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    cursor = resolve_sse_cursor(
        after_id=after_id,
        last_event_id=
            last_event_id,
    )

    return StreamingResponse(
        account_event_stream(
            request=request,
            user_id=
                current_user.id,
            is_admin=(
                current_user.role
                == "admin"
            ),
            start_after_id=
                cursor,
        ),
        media_type=
            "text/event-stream",
        headers={
            "Cache-Control":
                "no-cache, no-transform",
            "Connection":
                "keep-alive",
            "X-Accel-Buffering":
                "no",
        },
    )
