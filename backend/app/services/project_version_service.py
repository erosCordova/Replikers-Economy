from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ecosystem import AgentMessage
from app.models.project_specialist import (
    ProjectFinalReview,
)
from app.services.project_delivery_service import (
    DELIVERY_MESSAGE_PREFIX,
    parse_delivery_message,
)


def _version_label(
    index: int,
) -> str:
    return f"v1.{index}"


def build_delivery_version_history(
    *,
    db: Session,
    project_id: int,
) -> dict:
    approved_reviews = list(
        db.scalars(
            select(
                ProjectFinalReview
            )
            .where(
                ProjectFinalReview.project_id
                == project_id,
                ProjectFinalReview.status
                == "approved",
            )
            .order_by(
                ProjectFinalReview.attempt_number,
                ProjectFinalReview.id,
            )
        ).all()
    )

    messages = list(
        db.scalars(
            select(
                AgentMessage
            )
            .where(
                AgentMessage.project_id
                == project_id,
                AgentMessage.message_type
                == "client_response",
                AgentMessage.content.like(
                    f"{DELIVERY_MESSAGE_PREFIX}%"
                ),
            )
            .order_by(
                AgentMessage.created_at,
                AgentMessage.id,
            )
        ).all()
    )

    decisions: dict[
        int,
        tuple[dict, AgentMessage],
    ] = {}

    for message in messages:
        parsed = (
            parse_delivery_message(
                message
            )
        )

        review_attempt = (
            parsed.get(
                "review_attempt"
            )
        )

        if review_attempt is None:
            continue

        decisions[
            int(review_attempt)
        ] = (
            parsed,
            message,
        )

    history: list[dict] = []

    total = len(
        approved_reviews
    )

    for index, review in enumerate(
        approved_reviews
    ):
        decision_data = (
            decisions.get(
                review.attempt_number
            )
        )

        if decision_data is None:
            parsed = {
                "decision":
                    "pending",

                "comment":
                    "",
            }

            message = None

        else:
            parsed, message = (
                decision_data
            )

        decision = str(
            parsed.get(
                "decision",
                "pending",
            )
        )

        if decision == "accepted":
            delivery_status = (
                "accepted"
            )

        elif (
            decision
            == "corrections_requested"
        ):
            delivery_status = (
                "corrections_requested"
            )

        else:
            delivery_status = "ready"

        history.append(
            {
                "version":
                    _version_label(
                        index
                    ),

                "review_id":
                    review.id,

                "review_attempt":
                    review.attempt_number,

                "score":
                    review.score,

                "summary":
                    review.summary
                    or "",

                "vera_completed_at":
                    review.completed_at,

                "client_decision":
                    decision,

                "client_comment":
                    str(
                        parsed.get(
                            "comment",
                            "",
                        )
                    ),

                "client_decided_at":
                    (
                        message.created_at
                        if message
                        is not None
                        else None
                    ),

                "status":
                    delivery_status,

                "is_current":
                    index
                    == total - 1,
            }
        )

    return {
        "current_version":
            (
                history[-1][
                    "version"
                ]
                if history
                else "v1.0"
            ),

        "versions_total":
            len(history),

        "items":
            history,
    }
