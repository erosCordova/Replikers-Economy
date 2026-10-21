
"""API protegida de observacion para Replikers World.

Todos los endpoints exigen autenticacion.
No existen endpoints de transferencia ni gasto.

Si la BD principal carece de migraciones World,
se responde 503 en lugar de modificarla.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.repliker import Repliker
from app.models.economy import LedgerAccount

from app.auth.dependencies import get_current_user
from app.auth.dependencies import get_db

from app.services.world_access_service import (
    require_active_owner,
    require_owned_repliker,
)
from app.services.economy_service import account_balance
from app.agentic.world_memory_runtime import (
    get_agent_memories,
)
from app.agentic.world_negotiation_graph import negotiations
from app.agentic.world_social_learning import strategies
from app.agentic.world_feedback_runtime import (
    get_economic_feedback,
)

router = APIRouter(
    prefix="/world",
    tags=["Replikers World"],
)


def safe_query(action):
    try:
        return action()
    except DBAPIError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "La base de datos aun no tiene "
                "todas las migraciones de Replikers World."
            ),
        ) from exc


def wallet_summary(db, repliker_id):
    account = db.scalar(
        select(LedgerAccount)
        .where(
            LedgerAccount.repliker_id == repliker_id,
            LedgerAccount.kind == "repliker_available",
            LedgerAccount.currency == "RCR",
            LedgerAccount.is_active.is_(True),
        )
        .limit(1)
    )

    if account is None:
        return {
            "currency": "RCR",
            "available_cents": None,
            "wallet_ready": False,
        }

    return {
        "currency": "RCR",
        "available_cents": account_balance(
            db=db,
            account_id=account.id,
        ),
        "wallet_ready": True,
    }


@router.get("/mine")
def my_world_replikers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_active_owner(current_user)

    def read():
        agents = db.scalars(
            select(Repliker)
            .where(
                Repliker.owner_id == current_user.id
            )
            .order_by(Repliker.id)
        ).all()

        return {
            "agents": [
                {
                    "repliker_id": agent.id,
                    "name": agent.name,
                    "is_active": agent.is_active,
                }
                for agent in agents
            ],
            "total": len(agents),
        }

    return safe_query(read)


@router.get("/mine/{repliker_id}")
def my_repliker_overview(
    repliker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def read():
        agent = require_owned_repliker(
            db, current_user, repliker_id
        )

        return {
            "repliker_id": agent.id,
            "name": agent.name,
            "wallet": wallet_summary(db, agent.id),
        }

    return safe_query(read)


@router.get("/mine/{repliker_id}/economy")
def my_repliker_economy(
    repliker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def read():
        require_owned_repliker(
            db, current_user, repliker_id
        )
        return get_economic_feedback(
            db, repliker_id
        )

    return safe_query(read)


@router.get("/mine/{repliker_id}/memories")
def my_repliker_memories(
    repliker_id: int,
    limit: int = Query(default=10, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def read():
        require_owned_repliker(
            db, current_user, repliker_id
        )

        return {
            "repliker_id": repliker_id,
            "memories": get_agent_memories(
                db,
                repliker_id,
                limit=limit,
            ),
        }

    return safe_query(read)


@router.get("/mine/{repliker_id}/negotiations")
def my_repliker_negotiations(
    repliker_id: int,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def read():
        require_owned_repliker(
            db, current_user, repliker_id
        )

        records = db.execute(
            select(negotiations)
            .where(
                or_(
                    negotiations.c.proposer_repliker_id
                    == repliker_id,
                    negotiations.c.target_repliker_id
                    == repliker_id,
                )
            )
            .order_by(negotiations.c.id.desc())
            .limit(limit)
        ).mappings().all()

        return {
            "repliker_id": repliker_id,
            "negotiations": [
                {
                    "negotiation_id": item["id"],
                    "title": item["title"],
                    "status": item["status"],
                    "price_cents": item["price_cents"],
                    "currency": "RCR",
                    "role": (
                        "proposer"
                        if item["proposer_repliker_id"]
                        == repliker_id
                        else "counterparty"
                    ),
                }
                for item in records
            ],
        }

    return safe_query(read)


@router.get("/public-strategies")
def published_world_strategies(
    limit: int = Query(default=20, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_active_owner(current_user)

    def read():
        records = db.execute(
            select(strategies)
            .order_by(strategies.c.id.desc())
            .limit(limit)
        ).mappings().all()

        return {
            "strategies": [
                {
                    "strategy_id": item["id"],
                    "author_repliker_id":
                        item["author_repliker_id"],
                    "title": item["title"],
                    "insight": item["insight"],
                    "observed_outcome": item["outcome"],
                    "quoted_price_cents":
                        item["quoted_price_cents"],
                    "currency": "RCR",
                    "verified_profit_cents": None,
                }
                for item in records
            ]
        }

    return safe_query(read)
