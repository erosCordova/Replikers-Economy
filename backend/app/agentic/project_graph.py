from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from langgraph.graph import (
    END,
    START,
    StateGraph,
)
from sqlalchemy.orm import Session

from app.agentic.state import (
    AgenticProjectState,
)
from app.services.project_lifecycle_service import (
    active_contract_ids,
    finalize_project_if_ready,
    get_project,
    project_is_funded,
    run_contracting_stage,
    run_delegation_stage,
    run_execution_stage,
    run_market_stage,
    run_planning_stage,
    run_qa_stage,
)


StageHandler = Callable[..., dict]


@dataclass(frozen=True)
class ProjectLifecycleHandlers:
    get_project: Callable
    plan: StageHandler
    market: StageHandler
    contract: StageHandler
    delegation: StageHandler
    execution: Callable
    qa: Callable
    integration: StageHandler
    active_contracts: Callable


DEFAULT_HANDLERS = (
    ProjectLifecycleHandlers(
        get_project=get_project,
        plan=run_planning_stage,
        market=run_market_stage,
        contract=run_contracting_stage,
        delegation=
            run_delegation_stage,
        execution=
            run_execution_stage,
        qa=run_qa_stage,
        integration=
            finalize_project_if_ready,
        active_contracts=
            active_contract_ids,
    )
)


def build_project_lifecycle_graph(
    *,
    db: Session,
    handlers:
        ProjectLifecycleHandlers
        | None = None,
):
    runtime = (
        handlers
        or DEFAULT_HANDLERS
    )

    graph = StateGraph(
        AgenticProjectState
    )

    def load_project(
        state: AgenticProjectState,
    ):
        return runtime.get_project(
            db=db,
            project_id=
                state["project_id"],
        )

    def inspect_node(
        state: AgenticProjectState,
    ) -> dict:
        project = load_project(
            state
        )

        return {
            "project_status":
                project.status,
            "payment_status":
                project.payment_status,
            "current_stage":
                "inspect",
            "next_action":
                "route",
            "history": [
                (
                    "LangGraph inspecciono "
                    f"el proyecto #{project.id} "
                    f"en estado "
                    f"'{project.status}'."
                )
            ],
        }

    def inspect_router(
        state: AgenticProjectState,
    ) -> str:
        status = str(
            state.get(
                "project_status",
                "",
            )
        ).strip().lower()

        if status in {
            "completed",
            "delivered",
        }:
            return "completed"

        if status in {
            "cancelled",
            "failed",
        }:
            return "failed"

        if status == "draft":
            return "planning"

        if status in {
            "planned",
            "market_open",
            "partially_contracted",
        }:
            return "market"

        if status == "contracted":
            return "delegation"

        return "failed"

    def planning_node(
        state: AgenticProjectState,
    ) -> dict:
        result = runtime.plan(
            db=db,
            project_id=
                state["project_id"],
        )

        project = load_project(
            state
        )

        return {
            "current_stage":
                "planning",
            "project_status":
                project.status,
            "next_action":
                "run_market",
            "history": [
                (
                    "R00 completo la etapa "
                    "de planificacion. "
                    f"Tareas nuevas: "
                    f"{result.get('tasks_created', 0)}."
                )
            ],
        }

    def market_node(
        state: AgenticProjectState,
    ) -> dict:
        result = runtime.market(
            db=db,
            project_id=
                state["project_id"],
        )

        project = load_project(
            state
        )

        return {
            "current_stage":
                "market",
            "project_status":
                project.status,
            "payment_status":
                project.payment_status,
            "next_action":
                "check_funding",
            "history": [
                (
                    "El mercado autonomo "
                    "completo su ciclo. "
                    f"Nuevas decisiones: "
                    f"{result.get('new_decisions', 0)}; "
                    f"ofertas: "
                    f"{result.get('bid_count', 0)}."
                )
            ],
        }

    def funding_node(
        state: AgenticProjectState,
    ) -> dict:
        project = load_project(
            state
        )

        funded = project_is_funded(
            project
        )

        return {
            "current_stage": (
                "contracting"
                if funded
                else "awaiting_funding"
            ),
            "project_status":
                project.status,
            "payment_status":
                project.payment_status,
            "next_action": (
                "select_contracts"
                if funded
                else "await_funding"
            ),
            "blocked_reason": (
                ""
                if funded
                else (
                    "El proyecto aun no "
                    "esta financiado."
                )
            ),
            "history": [
                (
                    "El proyecto tiene "
                    "financiacion valida."
                    if funded
                    else (
                        "LangGraph detuvo "
                        "la contratacion hasta "
                        "que exista financiacion."
                    )
                )
            ],
        }

    def funding_router(
        state: AgenticProjectState,
    ) -> str:
        if (
            state.get(
                "current_stage"
            )
            == "awaiting_funding"
        ):
            return "blocked"

        return "funded"

    def contracting_node(
        state: AgenticProjectState,
    ) -> dict:
        result = runtime.contract(
            db=db,
            project_id=
                state["project_id"],
        )

        project = load_project(
            state
        )

        ids = list(
            result.get(
                "contract_ids",
                [],
            )
        )

        return {
            "current_stage":
                "contracting",
            "project_status":
                project.status,
            "contract_ids":
                ids,
            "contracts_created": (
                state.get(
                    "contracts_created",
                    0,
                )
                + int(
                    result.get(
                        "contracts_created",
                        0,
                    )
                )
            ),
            "contracts_processed":
                len(ids),
            "next_action": (
                "evaluate_delegation"
                if ids
                else "integrate"
            ),
            "history": [
                (
                    "R00 completo la "
                    "seleccion contractual. "
                    f"Contratos activos: "
                    f"{len(ids)}."
                )
            ],
        }

    def contract_router(
        state: AgenticProjectState,
    ) -> str:
        if state.get(
            "contract_ids",
            [],
        ):
            return "contracts"

        return "integration"

    def delegation_node(
        state: AgenticProjectState,
    ) -> dict:
        ids = list(
            state.get(
                "contract_ids",
                [],
            )
        )

        # Permite reanudar el workflow despues
        # de un reinicio cuando el proyecto ya
        # estaba contratado y el estado inicial
        # de LangGraph no contiene los IDs.
        if not ids:
            ids = list(
                runtime.active_contracts(
                    db=db,
                    project_id=
                        state["project_id"],
                )
            )

        result = runtime.delegation(
            db=db,
            contract_ids=ids,
        )

        return {
            "current_stage":
                "delegation",
            "delegations_processed": (
                state.get(
                    "delegations_processed",
                    0,
                )
                + int(
                    result.get(
                        "processed",
                        0,
                    )
                )
            ),
            "next_action":
                "execute",
            "history": [
                (
                    "Los Replikers evaluaron "
                    "delegacion. "
                    f"Contratos revisados: "
                    f"{result.get('processed', 0)}; "
                    f"delegaciones activadas: "
                    f"{result.get('delegated', 0)}."
                )
            ],
        }

    def execution_node(
        state: AgenticProjectState,
    ) -> dict:
        ids = list(
            state.get(
                "contract_ids",
                [],
            )
        )

        result = runtime.execution(
            db=db,
            contract_ids=ids,
        )

        failures = list(
            result.failed_contract_ids
        )

        return {
            "current_stage":
                "execution",
            "review_ids":
                list(
                    result.review_ids
                ),
            "execution_attempts": (
                state.get(
                    "execution_attempts",
                    0,
                )
                + result.execution_attempts
            ),
            "failed_contract_ids":
                failures,
            "next_action": (
                "qa"
                if not failures
                else "stop"
            ),
            "history": [
                (
                    "Ejecucion agentica "
                    "completada. "
                    f"Intentos nuevos: "
                    f"{result.execution_attempts}; "
                    f"revisiones QA listas: "
                    f"{len(result.review_ids)}."
                )
            ],
        }

    def execution_router(
        state: AgenticProjectState,
    ) -> str:
        if state.get(
            "failed_contract_ids",
            [],
        ):
            return "failed"

        return "qa"

    def qa_node(
        state: AgenticProjectState,
    ) -> dict:
        ids = list(
            state.get(
                "contract_ids",
                [],
            )
        )

        result = runtime.qa(
            db=db,
            contract_ids=ids,
        )

        execution_attempts = (
            state.get(
                "execution_attempts",
                0,
            )
            + result
            .retry_execution_attempts
        )

        return {
            "current_stage":
                "qa",
            "execution_attempts":
                execution_attempts,
            "qa_attempts": (
                state.get(
                    "qa_attempts",
                    0,
                )
                + result.qa_attempts
            ),
            "qa_passed": (
                state.get(
                    "qa_passed",
                    0,
                )
                + result.qa_passed
            ),
            "qa_failed": (
                state.get(
                    "qa_failed",
                    0,
                )
                + result.qa_failed
            ),
            "contracts_completed": (
                state.get(
                    "contracts_completed",
                    0,
                )
                + len(
                    result
                    .completed_contract_ids
                )
            ),
            "failed_contract_ids":
                list(
                    result
                    .failed_contract_ids
                ),
            "next_action": (
                "integrate"
                if result.qa_failed == 0
                else "manual_review"
            ),
            "history": [
                (
                    "QA completo la "
                    "verificacion. "
                    f"Aprobados: "
                    f"{result.qa_passed}; "
                    f"fallidos: "
                    f"{result.qa_failed}; "
                    f"evaluaciones: "
                    f"{result.qa_attempts}."
                )
            ],
        }

    def qa_router(
        state: AgenticProjectState,
    ) -> str:
        if int(
            state.get(
                "qa_failed",
                0,
            )
        ) > 0:
            return "failed"

        return "integration"

    def integration_node(
        state: AgenticProjectState,
    ) -> dict:
        result = runtime.integration(
            db=db,
            project_id=
                state["project_id"],
        )

        project = load_project(
            state
        )

        completed = bool(
            result.get(
                "completed",
                False,
            )
        )

        return {
            "current_stage": (
                "completed"
                if completed
                else "partial"
            ),
            "project_status":
                project.status,
            "next_action": (
                "none"
                if completed
                else "rerun_market"
            ),
            "history": [
                (
                    "Integracion final "
                    "completada. "
                    f"Tareas aprobadas: "
                    f"{result.get('completed_tasks', 0)}/"
                    f"{result.get('total_tasks', 0)}."
                )
            ],
        }

    def waiting_funding_node(
        state: AgenticProjectState,
    ) -> dict:
        _ = state

        return {
            "current_stage":
                "awaiting_funding",
            "next_action":
                "await_funding",
            "history": [
                (
                    "El ciclo quedo "
                    "correctamente pausado "
                    "por financiacion."
                )
            ],
        }

    def already_completed_node(
        state: AgenticProjectState,
    ) -> dict:
        _ = state

        return {
            "current_stage":
                "completed",
            "next_action":
                "none",
            "history": [
                (
                    "El proyecto ya estaba "
                    "completado."
                )
            ],
        }

    def failed_node(
        state: AgenticProjectState,
    ) -> dict:
        failures = list(
            state.get(
                "failed_contract_ids",
                [],
            )
        )

        message = (
            "El ciclo requiere "
            "intervencion porque una "
            "etapa no pudo completarse."
        )

        if failures:
            message += (
                " Contratos afectados: "
                + ", ".join(
                    str(item)
                    for item in failures
                )
                + "."
            )

        return {
            "current_stage":
                "failed",
            "next_action":
                "inspect_failure",
            "error":
                message,
            "history": [
                message
            ],
        }

    graph.add_node(
        "inspect",
        inspect_node,
    )

    graph.add_node(
        "planning",
        planning_node,
    )

    graph.add_node(
        "market",
        market_node,
    )

    graph.add_node(
        "funding",
        funding_node,
    )

    graph.add_node(
        "contracting",
        contracting_node,
    )

    graph.add_node(
        "delegation",
        delegation_node,
    )

    graph.add_node(
        "execution",
        execution_node,
    )

    graph.add_node(
        "qa",
        qa_node,
    )

    graph.add_node(
        "integration",
        integration_node,
    )

    graph.add_node(
        "awaiting_funding",
        waiting_funding_node,
    )

    graph.add_node(
        "already_completed",
        already_completed_node,
    )

    graph.add_node(
        "failed",
        failed_node,
    )

    graph.add_edge(
        START,
        "inspect",
    )

    graph.add_conditional_edges(
        "inspect",
        inspect_router,
        {
            "planning":
                "planning",
            "market":
                "market",
            "delegation":
                "delegation",
            "completed":
                "already_completed",
            "failed":
                "failed",
        },
    )

    graph.add_edge(
        "planning",
        "market",
    )

    graph.add_edge(
        "market",
        "funding",
    )

    graph.add_conditional_edges(
        "funding",
        funding_router,
        {
            "funded":
                "contracting",
            "blocked":
                "awaiting_funding",
        },
    )

    graph.add_conditional_edges(
        "contracting",
        contract_router,
        {
            "contracts":
                "delegation",
            "integration":
                "integration",
        },
    )

    graph.add_edge(
        "delegation",
        "execution",
    )

    graph.add_conditional_edges(
        "execution",
        execution_router,
        {
            "qa":
                "qa",
            "failed":
                "failed",
        },
    )

    graph.add_conditional_edges(
        "qa",
        qa_router,
        {
            "integration":
                "integration",
            "failed":
                "failed",
        },
    )

    graph.add_edge(
        "integration",
        END,
    )

    graph.add_edge(
        "awaiting_funding",
        END,
    )

    graph.add_edge(
        "already_completed",
        END,
    )

    graph.add_edge(
        "failed",
        END,
    )

    return graph.compile()


def run_project_lifecycle(
    *,
    db: Session,
    project_id: int,
    handlers:
        ProjectLifecycleHandlers
        | None = None,
) -> AgenticProjectState:
    graph = (
        build_project_lifecycle_graph(
            db=db,
            handlers=handlers,
        )
    )

    initial: AgenticProjectState = {
        "project_id":
            project_id,
        "current_stage":
            "inspect",
        "next_action":
            "route",
        "contract_ids":
            [],
        "review_ids":
            [],
        "contracts_created":
            0,
        "contracts_processed":
            0,
        "contracts_completed":
            0,
        "delegations_processed":
            0,
        "execution_attempts":
            0,
        "qa_attempts":
            0,
        "qa_passed":
            0,
        "qa_failed":
            0,
        "failed_contract_ids":
            [],
        "blocked_reason":
            "",
        "error":
            "",
        "history":
            [],
    }

    return graph.invoke(
        initial
    )
