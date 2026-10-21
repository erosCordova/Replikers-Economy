
"""Panel de observacion economica por propietario.

Lecturas verificables del ledger y la negociacion.
Ningun importe negociado se declara beneficio.
No crea contratos, gastos, pagos ni movimientos.
"""

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.user import User
from app.agentic.world_negotiation_graph import negotiations
from app.agentic.world_social_learning import strategies
from app.api.routes.world_read import wallet_summary
from app.services.world_access_service import (
    require_owned_repliker,
)
from app.services.world_autonomy_policy import get_policy

router = APIRouter(
    prefix="/world",
    tags=["Replikers World - Observabilidad"],
)


def _safe_read(action):
    try:
        return action()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="La base requiere sincronizar migraciones World.",
        ) from exc


def _negotiations_for(
    db: Session,
    repliker_id: int,
    limit: int,
):
    return db.execute(
        select(
            negotiations.c.id,
            negotiations.c.title,
            negotiations.c.status,
            negotiations.c.price_cents,
            negotiations.c.proposer_repliker_id,
            negotiations.c.target_repliker_id,
        )
        .where(
            (
                negotiations.c.proposer_repliker_id
                == repliker_id
            )
            | (
                negotiations.c.target_repliker_id
                == repliker_id
            )
        )
        .order_by(negotiations.c.id.desc())
        .limit(limit)
    ).mappings().all()


def _own_memory_count(db: Session, repliker_id: int):
    """Contar solo recuerdos vinculados al propio agente.

    No extraer ni publicar el texto de memoria.
    """

    fields = {
        column["name"]
        for column in inspect(
            db.get_bind()
        ).get_columns("world_agent_memories")
    }

    if "repliker_id" in fields:
        statement = text(
            "SELECT COUNT(*) FROM world_agent_memories "
            "WHERE repliker_id = :repliker_id"
        )
    elif "agent_repliker_id" in fields:
        statement = text(
            "SELECT COUNT(*) FROM world_agent_memories "
            "WHERE agent_repliker_id = :repliker_id"
        )
    else:
        return None

    return int(
        db.execute(
            statement,
            {"repliker_id": repliker_id},
        ).scalar_one()
    )


@router.get("/mine/{repliker_id}/dashboard")
def world_agent_dashboard(
    repliker_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def read():
        agent = require_owned_repliker(
            db, user, repliker_id
        )

        rows = _negotiations_for(
            db, repliker_id, 10000
        )

        statuses = Counter(
            str(row["status"])
            for row in rows
        )

        public_strategies = db.scalar(
            select(func.count())
            .select_from(strategies)
            .where(
                strategies.c.author_repliker_id
                == repliker_id
            )
        )

        wallet = wallet_summary(
            db, repliker_id
        )

        policy = get_policy(
            db,
            owner_id=user.id,
            repliker_id=repliker_id,
        )

        return {
            "repliker_id": agent.id,
            "name": agent.name,
            "currency": "RCR",
            "wallet": wallet,
            "autonomy": {
                "enabled": policy["enabled"],
                "version": policy["version"],
                "max_price_cents":
                    policy["max_price_cents"],
                "max_cost_cents":
                    policy["max_cost_cents"],
                "max_proposals_per_round":
                    policy["max_proposals_per_round"],
            },
            "activity": {
                "negotiations_total": len(rows),
                "accepted": statuses.get("accepted", 0),
                "rejected": statuses.get("rejected", 0),
                "other_statuses": (
                    len(rows)
                    - statuses.get("accepted", 0)
                    - statuses.get("rejected", 0)
                ),
                "private_memories_count":
                    _own_memory_count(db, repliker_id),
                "public_strategies_count":
                    int(public_strategies or 0),
            },
            "financial_disclosure": {
                "negotiated_values_are_profit": False,
                "real_money_used": False,
                "profit_verified_cents": None,
            },
        }

    return _safe_read(read)


@router.get("/mine/{repliker_id}/timeline")
def world_agent_timeline(
    repliker_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    def read():
        require_owned_repliker(
            db, user, repliker_id
        )

        records = _negotiations_for(
            db, repliker_id, limit
        )

        events = []

        for record in records:
            proposer = record["proposer_repliker_id"]
            target = record["target_repliker_id"]

            role = (
                "proposer"
                if proposer == repliker_id
                else "counterparty"
            )

            events.append({
                "event_type": "negotiation",
                "negotiation_id": record["id"],
                "title": record["title"],
                "status": record["status"],
                "role": role,
                "counterparty_repliker_id": (
                    target if role == "proposer"
                    else proposer
                ),
                "proposed_price_cents":
                    record["price_cents"],
                "currency": "RCR",
                "payment_confirmed": False,
                "verified_profit_cents": None,
            })

        return {
            "repliker_id": repliker_id,
            "events": events,
            "returned": len(events),
            "limit": limit,
            "contains_private_memory_text": False,
            "real_money_used": False,
        }

    return _safe_read(read)
