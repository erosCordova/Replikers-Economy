import operator

from typing import (
    Annotated,
    Literal,
)

from typing_extensions import (
    TypedDict,
)


ProjectStage = Literal[
    "inspect",
    "planning",
    "market",
    "awaiting_funding",
    "awaiting_specialists",
    "awaiting_final_review",
    "final_review",
    "corrections_requested",
    "contracting",
    "delegation",
    "execution",
    "qa",
    "retry",
    "integration",
    "partial",
    "completed",
    "failed",
]


class AgenticProjectState(
    TypedDict,
    total=False,
):
    """
    Estado serializable del supervisor maestro
    LangGraph de Repliker Economy.

    No almacena objetos SQLAlchemy.
    Solo IDs, estados, contadores y trazas
    serializables.
    """

    project_id: int

    project_status: str
    payment_status: str

    current_stage: ProjectStage
    next_action: str

    contract_ids: list[int]
    review_ids: list[int]

    contracts_created: int
    contracts_processed: int
    contracts_completed: int

    delegations_processed: int

    execution_attempts: int

    qa_attempts: int
    qa_passed: int
    qa_failed: int

    failed_contract_ids: list[int]

    specialist_coverage_ready: bool
    missing_specialties: list[str]
    final_review_status: str
    final_review_id: int | None

    blocked_reason: str
    error: str

    history: Annotated[
        list[str],
        operator.add,
    ]
