
"""Ejecutor gobernado con registro de eventos."""

from sqlalchemy.orm import Session

from app.services.world_event_service import (
    record_round_events,
)
from app.agentic.world_governed_runtime import (
    run_governed_social_round,
)


def run_logged_governed_round(
    db: Session,
    *,
    round_id: str,
    idea_engine,
    response_engine,
    max_agents: int = 3,
    initiator_owner_id: int | None = None,
):
    """Negociar y registrar, sin liquidar contratos."""

    results = run_governed_social_round(
        db,
        round_id=round_id,
        idea_engine=idea_engine,
        response_engine=response_engine,
        max_agents=max_agents,
        **({'initiator_owner_id': initiator_owner_id} if initiator_owner_id is not None else {}),
    )

    inserted = record_round_events(
        db,
        round_id=round_id,
        results=results,
    )

    db.commit()

    return {
        "results": results,
        "events_inserted": inserted,
        "real_money_used": False,
        "payments_executed": False,
    }
