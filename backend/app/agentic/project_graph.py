from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from app.agentic.state import (
    AgenticProjectState,
)


def planning_node(
    state: AgenticProjectState,
) -> dict:
    _ = state

    return {
        "current_stage": "planning",
        "history": [
            "R00: planning",
        ],
    }


def market_node(
    state: AgenticProjectState,
) -> dict:
    _ = state

    return {
        "current_stage": "market",
        "history": [
            "Replikers: market",
        ],
    }


def contracting_node(
    state: AgenticProjectState,
) -> dict:
    _ = state

    return {
        "current_stage":
            "contracting",
        "history": [
            "R00: contracting",
        ],
    }


def delegation_check_node(
    state: AgenticProjectState,
) -> dict:
    _ = state

    return {
        "current_stage":
            "delegation_check",
        "history": [
            "Repliker: delegation_check",
        ],
    }


def delegation_router(
    state: AgenticProjectState,
) -> str:
    if state.get(
        "needs_delegation",
        False,
    ):
        return "delegate"

    return "self"


def delegation_node(
    state: AgenticProjectState,
) -> dict:
    _ = state

    return {
        "current_stage":
            "delegating",
        "history": [
            "Repliker: delegating",
        ],
    }


def execution_pending_node(
    state: AgenticProjectState,
) -> dict:
    _ = state

    return {
        "current_stage":
            "execution_pending",
        "history": [
            "System: execution_pending",
        ],
    }


def build_project_lifecycle_graph():
    """
    Grafo supervisor inicial.

    En los siguientes bloques sustituiremos
    progresivamente estos nodos de transicion por
    nodos conectados a los servicios reales de
    R00, mercado, contratos y delegacion.

    Fase 7 agregara execution.
    Fase 8 agregara QA/retry/integration.
    """

    graph = StateGraph(
        AgenticProjectState
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
        "contracting",
        contracting_node,
    )

    graph.add_node(
        "delegation_check",
        delegation_check_node,
    )

    graph.add_node(
        "delegation",
        delegation_node,
    )

    graph.add_node(
        "execution_pending",
        execution_pending_node,
    )

    graph.add_edge(
        START,
        "planning",
    )

    graph.add_edge(
        "planning",
        "market",
    )

    graph.add_edge(
        "market",
        "contracting",
    )

    graph.add_edge(
        "contracting",
        "delegation_check",
    )

    graph.add_conditional_edges(
        "delegation_check",
        delegation_router,
        {
            "delegate":
                "delegation",
            "self":
                "execution_pending",
        },
    )

    graph.add_edge(
        "delegation",
        "execution_pending",
    )

    graph.add_edge(
        "execution_pending",
        END,
    )

    return graph.compile()


project_lifecycle_graph = (
    build_project_lifecycle_graph()
)
