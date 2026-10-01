from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.models.ecosystem import (
    AgentActivityEvent,
    AgentMessage,
    ReplikerAppearance,
)
from app.models.project import Project
from app.models.repliker import Repliker
from app.models.task import Task
from app.models.user import User
from app.schemas.ecosystem import (
    ActivityEventPublic,
    AgentMessagePublic,
    AppearancePublic,
    EcosystemAgent,
    EcosystemProject,
    EcosystemSkill,
    EcosystemSnapshot,
)


ACTIVE_WORK_EVENT_TYPES = {
    "task_started",
    "work_started",
    "task_executing",
    "execution_started",
    "revision_started",
    "qa_started",
    "delegated_task_started",
}


def default_appearance() -> AppearancePublic:
    return AppearancePublic(
        avatar_style="synthetic",
        primary_color="#2563eb",
        secondary_color="#06b6d4",
        face_type="core",
        eye_style="glow",
        accessory="none",
        background_style="grid",
        avatar_url=None,
    )


def serialize_appearance(
    appearance:
        ReplikerAppearance | None,
) -> AppearancePublic:
    if appearance is None:
        return default_appearance()

    return AppearancePublic(
        avatar_style=
            appearance.avatar_style,
        primary_color=
            appearance.primary_color,
        secondary_color=
            appearance.secondary_color,
        face_type=
            appearance.face_type,
        eye_style=
            appearance.eye_style,
        accessory=
            appearance.accessory,
        background_style=
            appearance.background_style,
        avatar_url=
            appearance.avatar_url,
    )


def get_visible_projects(
    *,
    db: Session,
    current_user: User,
) -> list[Project]:
    statement = (
        select(Project)
        .where(
            Project.status.notin_(
                [
                    "completed",
                    "cancelled",
                ]
            )
        )
    )

    if (
        current_user.role
        != "admin"
    ):
        statement = (
            statement.where(
                Project.client_id
                == current_user.id
            )
        )

    statement = (
        statement.order_by(
            Project.created_at.desc()
        )
    )

    return list(
        db.scalars(
            statement
        ).all()
    )


def build_ecosystem_snapshot(
    *,
    db: Session,
    current_user: User,
) -> EcosystemSnapshot:
    replikers = list(
        db.scalars(
            select(Repliker)
            .options(
                selectinload(
                    Repliker.skills
                )
            )
            .where(
                Repliker.is_active
                .is_(True)
            )
            .order_by(
                Repliker
                .reputation_score
                .desc(),
                Repliker
                .jobs_completed
                .desc(),
                Repliker.id.asc(),
            )
        ).all()
    )

    appearances = list(
        db.scalars(
            select(
                ReplikerAppearance
            )
        ).all()
    )

    appearance_map = {
        appearance.repliker_id:
            appearance
        for appearance
        in appearances
    }

    projects = (
        get_visible_projects(
            db=db,
            current_user=
                current_user,
        )
    )

    project_ids = [
        project.id
        for project
        in projects
    ]

    if project_ids:
        events = list(
            db.scalars(
                select(
                    AgentActivityEvent
                )
                .where(
                    AgentActivityEvent
                    .project_id
                    .in_(
                        project_ids
                    )
                )
                .order_by(
                    AgentActivityEvent
                    .created_at
                    .desc(),
                    AgentActivityEvent
                    .id
                    .desc(),
                )
                .limit(
                    150
                )
            ).all()
        )

        messages = list(
            db.scalars(
                select(
                    AgentMessage
                )
                .where(
                    AgentMessage
                    .project_id
                    .in_(
                        project_ids
                    )
                )
                .order_by(
                    AgentMessage
                    .created_at
                    .desc(),
                    AgentMessage
                    .id
                    .desc(),
                )
                .limit(
                    150
                )
            ).all()
        )

    else:
        events = []
        messages = []

    active_activity_by_repliker: dict[
        int,
        AgentActivityEvent,
    ] = {}

    for event in events:
        if (
            event.repliker_id
            is None
        ):
            continue

        if (
            event.event_type
            not in
            ACTIVE_WORK_EVENT_TYPES
        ):
            continue

        if (
            event.repliker_id
            not in
            active_activity_by_repliker
        ):
            active_activity_by_repliker[
                event.repliker_id
            ] = event

    agents: list[
        EcosystemAgent
    ] = []

    for repliker in replikers:
        active_event = (
            active_activity_by_repliker
            .get(
                repliker.id
            )
        )

        agents.append(
            EcosystemAgent(
                id=
                    repliker.id,
                owner_id=
                    repliker.owner_id,
                name=
                    repliker.name,
                specialty=
                    repliker.specialty,
                description=
                    repliker.description,
                status=
                    repliker.status,
                reputation_score=(
                    repliker
                    .reputation_score
                ),
                jobs_completed=(
                    repliker
                    .jobs_completed
                ),
                is_active=
                    repliker.is_active,
                skills=[
                    EcosystemSkill(
                        name=
                            skill.name,
                        level=
                            skill.level,
                    )
                    for skill
                    in repliker.skills
                ],
                appearance=(
                    serialize_appearance(
                        appearance_map
                        .get(
                            repliker.id
                        )
                    )
                ),
                current_project_id=(
                    active_event
                    .project_id
                    if active_event
                    else None
                ),
                current_task_id=(
                    active_event
                    .task_id
                    if active_event
                    else None
                ),
                current_activity=(
                    active_event
                    .title
                    if active_event
                    else None
                ),
            )
        )

    ecosystem_projects: list[
        EcosystemProject
    ] = []

    for project in projects:
        task_count = (
            db.scalar(
                select(
                    func.count(
                        Task.id
                    )
                )
                .where(
                    Task.project_id
                    == project.id
                )
            )
            or 0
        )

        involved_ids = {
            event.repliker_id
            for event
            in events
            if (
                event.project_id
                == project.id
                and
                event.repliker_id
                is not None
            )
        }

        ecosystem_projects.append(
            EcosystemProject(
                id=
                    project.id,
                title=
                    project.title,
                status=
                    project.status,
                task_count=
                    task_count,
                agents_involved=
                    len(
                        involved_ids
                    ),
            )
        )

    serialized_events = [
        ActivityEventPublic(
            id=
                event.id,
            project_id=
                event.project_id,
            task_id=
                event.task_id,
            repliker_id=
                event.repliker_id,
            actor_type=
                event.actor_type,
            event_type=
                event.event_type,
            title=
                event.title,
            description=
                event.description,
            created_at=
                event.created_at,
        )
        for event
        in events
    ]

    serialized_messages = [
        AgentMessagePublic(
            id=
                message.id,
            project_id=
                message.project_id,
            task_id=
                message.task_id,
            sender_type=
                message.sender_type,
            sender_repliker_id=(
                message
                .sender_repliker_id
            ),
            receiver_type=(
                message.receiver_type
            ),
            receiver_repliker_id=(
                message
                .receiver_repliker_id
            ),
            message_type=(
                message.message_type
            ),
            content=
                message.content,
            created_at=
                message.created_at,
        )
        for message
        in messages
    ]

    return EcosystemSnapshot(
        agents=
            agents,
        projects=
            ecosystem_projects,
        events=
            serialized_events,
        messages=
            serialized_messages,
    )
