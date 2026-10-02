from __future__ import annotations

from typing import TypedDict

from langgraph.graph import (
    END,
    START,
    StateGraph,
)


class QAFollowupState(
    TypedDict,
    total=False,
):
    review_status: str
    attempt_number: int
    max_attempts: int
    action: str
    trace: list[str]


def build_qa_followup_graph():
    graph = StateGraph(
        QAFollowupState
    )

    def inspect_node(
        state: QAFollowupState,
    ) -> dict:
        status = str(
            state.get(
                "review_status",
                "",
            )
        )

        attempt = int(
            state.get(
                "attempt_number",
                0,
            )
        )

        maximum = int(
            state.get(
                "max_attempts",
                0,
            )
        )

        if attempt <= 0:
            raise ValueError(
                "attempt_number invalido."
            )

        if maximum <= 0:
            raise ValueError(
                "max_attempts invalido."
            )

        if status == "passed":
            action = "complete"

        elif status in {
            "failed",
            "needs_review",
        }:
            if attempt < maximum:
                action = "retry"
            else:
                action = "exhausted"

        else:
            action = "manual_review"

        return {
            "action":
                action,
            "trace": [
                *state.get(
                    "trace",
                    [],
                ),
                (
                    "LangGraph evaluo "
                    f"QA={status}, "
                    f"attempt={attempt}/"
                    f"{maximum}: "
                    f"{action}."
                ),
            ],
        }

    graph.add_node(
        "inspect",
        inspect_node,
    )

    graph.add_edge(
        START,
        "inspect",
    )

    graph.add_edge(
        "inspect",
        END,
    )

    return graph.compile()


def decide_qa_followup(
    *,
    review_status: str,
    attempt_number: int,
    max_attempts: int,
) -> QAFollowupState:
    graph = (
        build_qa_followup_graph()
    )

    return graph.invoke(
        {
            "review_status":
                review_status,
            "attempt_number":
                attempt_number,
            "max_attempts":
                max_attempts,
            "action":
                "pending",
            "trace":
                [],
        }
    )
