from importlib.metadata import (
    version,
)

from sqlalchemy import (
    delete,
    select,
)
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.agentic.tool_catalog import (
    MARKET_CORE_TOOLS,
    TOOL_DEFINITIONS,
    list_tool_catalog,
    resolve_market_tool_names,
)
from app.core.config import settings
from app.models.agentic import (
    ReplikerToolAssignment,
)
from app.models.contract import (
    TaskContract,
)
from app.models.delegation import (
    Subcontract,
)
from app.models.ecosystem import (
    AgentActivityEvent,
)
from app.models.market import (
    ReplikerTaskDecision,
)
from app.models.project import (
    Project,
)
from app.models.repliker import (
    Repliker,
)
from app.models.task import (
    Task,
)
from app.services.activity_service import (
    record_activity,
)


GRAPH_NODES = (
    "planning",
    "market",
    "contracting",
    "delegation_check",
    "delegation",
    "execution_pending",
)


NODE_LABELS = {
    "planning":
        "Planificacion R00",

    "market":
        "Mercado autonomo",

    "contracting":
        "Contratacion",

    "delegation_check":
        "Evaluacion de delegacion",

    "delegation":
        "Delegacion",

    "execution_pending":
        "Ejecucion",
}


NEXT_ACTIONS = {
    "planning":
        "R00 debe generar el plan del proyecto.",

    "market":
        "Los Replikers deben evaluar las tareas.",

    "contracting":
        "R00 debe seleccionar contratistas.",

    "delegation_check":
        (
            "El contratista debe decidir si ejecuta "
            "o delega parte del trabajo."
        ),

    "delegation":
        (
            "El ecosistema esta resolviendo "
            "subcontrataciones."
        ),

    "execution_pending":
        (
            "La ejecucion real se habilitara "
            "en la Fase 7."
        ),
}


def _version(
    package: str,
) -> str:
    try:
        return version(
            package
        )
    except Exception:
        return "unknown"


def runtime_info() -> dict:
    return {
        "framework":
            "LangChain + LangGraph",

        "langchain_version":
            _version(
                "langchain"
            ),

        "langgraph_version":
            _version(
                "langgraph"
            ),

        "provider":
            "Google Gemini",

        "model":
            settings.GEMINI_MODEL,

        "tool_count":
            len(
                TOOL_DEFINITIONS
            ),

        "default_tools":
            list(
                MARKET_CORE_TOOLS
            ),

        "graph_nodes":
            list(
                GRAPH_NODES
            ),
    }


def tool_catalog() -> list[dict]:
    return list_tool_catalog()


def _repliker_data(
    repliker: Repliker,
) -> dict:
    return {
        "id":
            repliker.id,

        "name":
            repliker.name,

        "specialty":
            repliker.specialty,

        "description":
            repliker.description,

        "reputation_score":
            repliker
            .reputation_score,

        "jobs_completed":
            repliker
            .jobs_completed,

        "status":
            repliker.status,

        "skills": [
            {
                "name":
                    skill.name,
                "level":
                    skill.level,
            }
            for skill
            in repliker.skills
        ],
    }


def _assignment_rows(
    *,
    db: Session,
    repliker_id: int,
) -> list[
    ReplikerToolAssignment
]:
    return list(
        db.scalars(
            select(
                ReplikerToolAssignment
            )
            .where(
                ReplikerToolAssignment
                .repliker_id
                == repliker_id
            )
            .order_by(
                ReplikerToolAssignment
                .id
            )
        ).all()
    )


def resolve_repliker_tool_names(
    *,
    db: Session,
    repliker: Repliker,
) -> tuple[str, ...]:
    rows = _assignment_rows(
        db=db,
        repliker_id=
            repliker.id,
    )

    if not rows:
        return (
            resolve_market_tool_names(
                _repliker_data(
                    repliker
                )
            )
        )

    result = []

    for row in rows:
        if not row.enabled:
            continue

        if (
            row.tool_name
            not in TOOL_DEFINITIONS
        ):
            continue

        if (
            row.tool_name
            not in result
        ):
            result.append(
                row.tool_name
            )

    return tuple(
        result
    )


def repliker_tool_profile(
    *,
    db: Session,
    repliker: Repliker,
) -> dict:
    rows = _assignment_rows(
        db=db,
        repliker_id=
            repliker.id,
    )

    names = (
        resolve_repliker_tool_names(
            db=db,
            repliker=repliker,
        )
    )

    tools = [
        {
            "name":
                name,

            **TOOL_DEFINITIONS[
                name
            ],
        }
        for name
        in names
        if name in TOOL_DEFINITIONS
    ]

    return {
        "repliker_id":
            repliker.id,

        "repliker_name":
            repliker.name,

        "owner_id":
            repliker.owner_id,

        "specialty":
            repliker.specialty,

        "explicit_configuration":
            bool(rows),

        "tools":
            tools,
    }


def replace_repliker_tools(
    *,
    db: Session,
    repliker: Repliker,
    tool_names: list[str],
) -> dict:
    unique_names = []

    for tool_name in tool_names:
        clean_name = (
            tool_name.strip()
        )

        if (
            clean_name
            not in TOOL_DEFINITIONS
        ):
            raise ValueError(
                "Herramienta desconocida: "
                f"{clean_name}"
            )

        if (
            clean_name
            not in unique_names
        ):
            unique_names.append(
                clean_name
            )

    if not unique_names:
        raise ValueError(
            "Un Repliker debe conservar "
            "al menos una herramienta."
        )

    db.execute(
        delete(
            ReplikerToolAssignment
        )
        .where(
            ReplikerToolAssignment
            .repliker_id
            == repliker.id
        )
    )

    for tool_name in unique_names:
        db.add(
            ReplikerToolAssignment(
                repliker_id=
                    repliker.id,
                tool_name=
                    tool_name,
                enabled=True,
                source="owner",
            )
        )

    record_activity(
        db=db,
        actor_type="system",
        event_type=(
            "agent_tools_updated"
        ),
        repliker_id=
            repliker.id,
        title=(
            f"Herramientas actualizadas para "
            f"{repliker.name}"
        ),
        description=(
            "Herramientas asignadas: "
            + ", ".join(
                unique_names
            )
        ),
    )

    db.flush()

    return repliker_tool_profile(
        db=db,
        repliker=repliker,
    )


def _current_node(
    *,
    project: Project,
    has_delegations: bool,
) -> str:
    if project.status == "draft":
        return "planning"

    if project.status in {
        "planned",
        "market_open",
    }:
        return "market"

    if project.status == (
        "partially_contracted"
    ):
        return "contracting"

    if project.status == "contracted":
        if has_delegations:
            return "delegation"

        return "delegation_check"

    return "execution_pending"


def _graph_nodes(
    *,
    current_node: str,
    has_delegations: bool,
) -> list[dict]:
    result = []

    current_index = (
        GRAPH_NODES.index(
            current_node
        )
        if current_node
        in GRAPH_NODES
        else len(
            GRAPH_NODES
        ) - 1
    )

    for index, node in enumerate(
        GRAPH_NODES
    ):
        if (
            node == "delegation"
            and not has_delegations
            and current_node
            == "execution_pending"
        ):
            status = "skipped"

        elif node == current_node:
            status = "active"

        elif index < current_index:
            status = "complete"

        else:
            status = "pending"

        result.append(
            {
                "name":
                    node,

                "label":
                    NODE_LABELS[
                        node
                    ],

                "status":
                    status,
            }
        )

    return result


def build_project_snapshot(
    *,
    db: Session,
    project: Project,
) -> dict:
    subcontract_count = len(
        db.scalars(
            select(
                Subcontract.id
            )
            .where(
                Subcontract.project_id
                == project.id
            )
        ).all()
    )

    has_delegations = (
        subcontract_count > 0
    )

    agent_ids = set()

    decision_ids = db.scalars(
        select(
            ReplikerTaskDecision
            .repliker_id
        )
        .join(
            Task,
            Task.id
            ==
            ReplikerTaskDecision
            .task_id,
        )
        .where(
            Task.project_id
            == project.id
        )
    ).all()

    agent_ids.update(
        decision_ids
    )

    contract_ids = db.scalars(
        select(
            TaskContract
            .repliker_id
        )
        .where(
            TaskContract.project_id
            == project.id
        )
    ).all()

    agent_ids.update(
        contract_ids
    )

    subcontract_rows = db.execute(
        select(
            Subcontract
            .delegator_repliker_id,
            Subcontract
            .subcontractor_repliker_id,
        )
        .where(
            Subcontract.project_id
            == project.id
        )
    ).all()

    for (
        delegator_id,
        subcontractor_id,
    ) in subcontract_rows:
        agent_ids.add(
            delegator_id
        )
        agent_ids.add(
            subcontractor_id
        )

    if agent_ids:
        agents = list(
            db.scalars(
                select(
                    Repliker
                )
                .options(
                    selectinload(
                        Repliker.skills
                    )
                )
                .where(
                    Repliker.id.in_(
                        agent_ids
                    )
                )
                .order_by(
                    Repliker.id
                )
            ).all()
        )
    else:
        agents = []

    current_node = _current_node(
        project=project,
        has_delegations=
            has_delegations,
    )

    events = list(
        db.scalars(
            select(
                AgentActivityEvent
            )
            .where(
                AgentActivityEvent
                .project_id
                == project.id
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
                40
            )
        ).all()
    )

    runtime = runtime_info()

    return {
        "project_id":
            project.id,

        "project_title":
            project.title,

        "project_status":
            project.status,

        "payment_status":
            project.payment_status,

        "framework":
            runtime[
                "framework"
            ],

        "langchain_version":
            runtime[
                "langchain_version"
            ],

        "langgraph_version":
            runtime[
                "langgraph_version"
            ],

        "provider":
            runtime[
                "provider"
            ],

        "model":
            runtime[
                "model"
            ],

        "current_node":
            current_node,

        "next_action":
            NEXT_ACTIONS[
                current_node
            ],

        "has_delegations":
            has_delegations,

        "nodes":
            _graph_nodes(
                current_node=
                    current_node,
                has_delegations=
                    has_delegations,
            ),

        "agents": [
            repliker_tool_profile(
                db=db,
                repliker=repliker,
            )
            for repliker
            in agents
        ],

        "recent_activity": [
            {
                "id":
                    event.id,

                "project_id":
                    event.project_id,

                "task_id":
                    event.task_id,

                "repliker_id":
                    event.repliker_id,

                "actor_type":
                    event.actor_type,

                "event_type":
                    event.event_type,

                "title":
                    event.title,

                "description":
                    event.description,

                "created_at":
                    event.created_at,
            }
            for event
            in events
        ],
    }
