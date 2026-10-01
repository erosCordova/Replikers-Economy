from __future__ import annotations

from collections.abc import (
    Callable,
)

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from app.agentic.execution_state import (
    ContractExecutionState,
)


ExecutionNode = Callable[
    [ContractExecutionState],
    dict,
]


def build_contract_execution_graph(
    *,
    executor: ExecutionNode,
):
    """
    Subgrafo profesional para una ejecucion
    contractual.

    LangGraph controla el ciclo:

        prepare
           ↓
        execute
           ↓
        finalize
           ↓
          END

    La implementacion real de execute se
    inyecta para mantener el grafo testeable
    sin invocar un LLM durante las pruebas.
    """

    graph = StateGraph(
        ContractExecutionState
    )

    def prepare_node(
        state: ContractExecutionState,
    ) -> dict:
        contract_id = int(
            state.get(
                "contract_id",
                0,
            )
        )

        if contract_id <= 0:
            raise ValueError(
                "contract_id invalido."
            )

        instruction = str(
            state.get(
                "instruction",
                "",
            )
        ).strip()

        return {
            "contract_id":
                contract_id,
            "instruction":
                instruction,
            "current_node":
                "prepare",
            "status":
                "prepared",
            "response_text":
                "",
            "error":
                "",
            "artifact_count":
                0,
            "artifacts":
                [],
            "trace": [
                *state.get(
                    "trace",
                    [],
                ),
                (
                    "LangGraph preparo "
                    f"el contrato #{contract_id} "
                    "para ejecucion."
                ),
            ],
        }

    def execute_node(
        state: ContractExecutionState,
    ) -> dict:
        result = executor(
            state
        )

        return {
            **result,
            "current_node":
                "execute",
        }

    def finalize_node(
        state: ContractExecutionState,
    ) -> dict:
        status = str(
            state.get(
                "status",
                "failed",
            )
        )

        artifact_count = int(
            state.get(
                "artifact_count",
                0,
            )
        )

        trace = list(
            state.get(
                "trace",
                [],
            )
        )

        if (
            status == "completed"
            and artifact_count == 0
        ):
            status = (
                "needs_artifact"
            )

            trace.append(
                (
                    "La ejecucion termino "
                    "sin producir ni modificar "
                    "artifacts verificables."
                )
            )

        elif status == "completed":
            trace.append(
                (
                    "LangGraph confirmo "
                    f"{artifact_count} artifact(s) "
                    "producidos o modificados."
                )
            )

        elif status == "failed":
            trace.append(
                "La ejecucion termino con error."
            )

        return {
            "current_node":
                "finalize",
            "status":
                status,
            "trace":
                trace,
        }

    graph.add_node(
        "prepare",
        prepare_node,
    )

    graph.add_node(
        "execute",
        execute_node,
    )

    graph.add_node(
        "finalize",
        finalize_node,
    )

    graph.add_edge(
        START,
        "prepare",
    )

    graph.add_edge(
        "prepare",
        "execute",
    )

    graph.add_edge(
        "execute",
        "finalize",
    )

    graph.add_edge(
        "finalize",
        END,
    )

    return graph.compile()


def run_execution_graph(
    *,
    contract_id: int,
    instruction: str,
    executor: ExecutionNode,
) -> ContractExecutionState:
    graph = (
        build_contract_execution_graph(
            executor=executor,
        )
    )

    initial: ContractExecutionState = {
        "contract_id":
            contract_id,
        "instruction":
            instruction,
        "current_node":
            "start",
        "status":
            "pending",
        "response_text":
            "",
        "error":
            "",
        "artifact_count":
            0,
        "artifacts":
            [],
        "trace":
            [],
    }

    return graph.invoke(
        initial
    )
