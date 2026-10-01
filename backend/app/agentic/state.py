import operator

from typing import (
    Annotated,
    Literal,
)

from typing_extensions import (
    TypedDict,
)


ProjectStage = Literal[
    "planning",
    "market",
    "contracting",
    "delegation_check",
    "delegating",
    "execution_pending",
    "executing",
    "qa",
    "retry",
    "integration",
    "completed",
    "failed",
]


class AgenticProjectState(
    TypedDict,
    total=False,
):
    """
    Estado compartido por el supervisor LangGraph.

    Este estado NO contiene objetos SQLAlchemy.
    Solo contiene identificadores y datos simples
    para que el grafo sea serializable y pueda
    persistirse mediante checkpoints posteriormente.
    """

    project_id: int

    task_id: int | None

    contract_id: int | None

    subcontract_id: int | None

    repliker_id: int | None

    current_stage: ProjectStage

    needs_delegation: bool

    execution_attempts: int

    qa_attempts: int

    qa_status: Literal[
        "pending",
        "approved",
        "retry",
        "failed",
    ]

    error: str | None

    history: Annotated[
        list[str],
        operator.add,
    ]
