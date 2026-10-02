from __future__ import annotations

from collections.abc import Callable

from dataclasses import dataclass

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
from app.services.realtime_service import (
    record_workflow_event,
)


StageHandler = Callable[..., dict]


def _noop_workflow_event(
    **kwargs,
):
    _ = kwargs

    return None


@dataclass(frozen=True)
class ProjectLifecycleHandlers:
    get_project: Callable
    is_funded: Callable
    plan: StageHandler
    market: StageHandler
    contract: StageHandler
    delegation: StageHandler
    execution: Callable
    qa: Callable
    integration: StageHandler
    active_contracts: Callable
    emit: Callable = _noop_workflow_event


DEFAULT_HANDLERS = (
    ProjectLifecycleHandlers(
        get_project=get_project,
    is_funded=project_is_funded,
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
        emit=
            record_workflow_event,
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

    workflow_actors = {
        "inspect": "langgraph",
        "planning": "r00",
        "market": "market",
        "funding": "economy",
        "contracting": "r00",
        "delegation": "repliker",
        "execution": "repliker",
        "qa": "qa",
        "retry": "repliker",
        "integration": "system",
        "economy": "economy",
        "awaiting_funding": "economy",
        "already_completed": "system",
        "failed": "system",
    }

    def emit_stage_event(
        *,
        state: AgenticProjectState,
        stage: str,
        status: str,
        title: str,
        payload: dict | None = None,
        kind: str = "workflow",
    ):
        emitted = runtime.emit(
            db=db,
            project_id=
                state["project_id"],
            stage=stage,
            status=status,
            title=title,
            actor_type=
                workflow_actors.get(
                    stage,
                    "langgraph",
                ),
            kind=kind,
            payload=payload or {},
        )

        # El emitter real devuelve un modelo.
        # Los emitters inyectados de tests
        # pueden devolver None y no requieren
        # una Session SQLAlchemy real.
        if (
            emitted is not None
            and hasattr(
                db,
                "commit",
            )
        ):
            db.commit()

        return emitted

    def instrument_node(
        stage: str,
        node: Callable,
    ):
        def wrapped(
            state: AgenticProjectState,
        ):
            emit_stage_event(
                state=state,
                stage=stage,
                status="started",
                title=(
                    f"Etapa {stage} iniciada"
                ),
                payload={
                    "previous_stage":
                        state.get(
                            "current_stage"
                        ),
                    "next_action":
                        state.get(
                            "next_action"
                        ),
                },
            )

            try:
                result = node(
                    state
                )

            except Exception as exc:
                if hasattr(
                    db,
                    "rollback",
                ):
                    db.rollback()

                emit_stage_event(
                    state=state,
                    stage=stage,
                    status="failed",
                    title=(
                        f"Etapa {stage} fallo"
                    ),
                    payload={
                        "error":
                            str(exc)[:1000],
                    },
                )

                raise

            compact_payload = {
                key:
                    value
                for key, value
                in result.items()
                if key != "history"
            }

            emit_stage_event(
                state=state,
                stage=stage,
                status="completed",
                title=(
                    f"Etapa {stage} completada"
                ),
                payload=
                    compact_payload,
            )

            # QA puede ejecutar automaticamente
            # uno o mas retries.
            if stage == "qa":
                before_attempts = int(
                    state.get(
                        "execution_attempts",
                        0,
                    )
                )

                after_attempts = int(
                    result.get(
                        "execution_attempts",
                        before_attempts,
                    )
                )

                retry_attempts = max(
                    0,
                    after_attempts
                    - before_attempts,
                )

                if retry_attempts > 0:
                    emit_stage_event(
                        state=state,
                        stage="retry",
                        status="completed",
                        title=(
                            "Retry de ejecucion "
                            "completado"
                        ),
                        payload={
                            "retry_attempts":
                                retry_attempts,
                        },
                    )

            # La economia se liquida durante
            # la integracion final de Fase 10.
            if (
                stage == "integration"
                and result.get(
                    "current_stage"
                )
                == "completed"
            ):
                project = load_project(
                    state
                )

                if (
                    project.payment_status
                    == "settled"
                ):
                    emit_stage_event(
                        state=state,
                        stage="economy",
                        status="settled",
                        kind="economy",
                        title=(
                            "Economia simulada "
                            "liquidada"
                        ),
                        payload={
                            "payment_status":
                                project
                                .payment_status,
                            "project_status":
                                project.status,
                        },
                    )

            return result

        return wrapped

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

        funded = runtime.is_funded(
            db=db,
            project=project,
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
        instrument_node(
            "inspect",
            inspect_node,
        ),
    )

    graph.add_node(
        "planning",
        instrument_node(
            "planning",
            planning_node,
        ),
    )

    graph.add_node(
        "market",
        instrument_node(
            "market",
            market_node,
        ),
    )

    graph.add_node(
        "funding",
        instrument_node(
            "funding",
            funding_node,
        ),
    )

    graph.add_node(
        "contracting",
        instrument_node(
            "contracting",
            contracting_node,
        ),
    )

    graph.add_node(
        "delegation",
        instrument_node(
            "delegation",
            delegation_node,
        ),
    )

    graph.add_node(
        "execution",
        instrument_node(
            "execution",
            execution_node,
        ),
    )

    graph.add_node(
        "qa",
        instrument_node(
            "qa",
            qa_node,
        ),
    )

    graph.add_node(
        "integration",
        instrument_node(
            "integration",
            integration_node,
        ),
    )

    graph.add_node(
        "awaiting_funding",
        instrument_node(
            "awaiting_funding",
            waiting_funding_node,
        ),
    )

    graph.add_node(
        "already_completed",
        instrument_node(
            "already_completed",
            already_completed_node,
        ),
    )

    graph.add_node(
        "failed",
        instrument_node(
            "failed",
            failed_node,
        ),
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
