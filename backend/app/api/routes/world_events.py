
"""API privada de eventos World, de solo lectura."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.repliker import Repliker
from app.services.world_access_service import (
    require_active_owner,
    require_owned_repliker,
)
from app.services.world_event_service import world_events


router = APIRouter(
    prefix="/world/events",
    tags=["Replikers World - Eventos"],
)


def _read_events(
    db: Session,
    *,
    owner_id: int,
    repliker_id: int | None,
    limit: int,
    after_id: int,
):
    statement = select(world_events).where(
        world_events.c.owner_id == owner_id,
        world_events.c.id > after_id,
    )

    if repliker_id is not None:
        statement = statement.where(
            world_events.c.repliker_id == repliker_id
        )

    rows = db.execute(
        statement.order_by(
            world_events.c.id.desc()
        ).limit(limit)
    ).mappings().all()

    agent_ids = {
        row["repliker_id"]
        for row in rows
    }

    if agent_ids:
        names = dict(
            db.execute(
                select(Repliker.id, Repliker.name)
                .where(Repliker.id.in_(agent_ids))
            ).all()
        )
    else:
        names = {}

    events = []

    for row in rows:
        events.append({
            "id": row["id"],
            "repliker_id": row["repliker_id"],
            "repliker_name": names.get(
                row["repliker_id"], "Repliker"
            ),
            "round_id": row["round_id"],
            "negotiation_id": row["negotiation_id"],
            "kind": row["kind"],
            "status": row["status"],
            "created_at": row["created_at"].isoformat(),
            "verified_profit_cents": None,
            "real_money_used": False,
        })

    return {
        "events": events,
        "total_returned": len(events),
        "limit": limit,
    }


@router.get("/mine")
def my_world_events(
    limit: int = Query(default=30, ge=1, le=100),
    after_id: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_active_owner(current_user)

    try:
        return _read_events(
            db,
            owner_id=current_user.id,
            repliker_id=None,
            limit=limit,
            after_id=after_id,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            503,
            "Migracion de eventos World pendiente "
            "en la base activa.",
        ) from exc


@router.get("/mine/{repliker_id}")
def my_agent_world_events(
    repliker_id: int,
    limit: int = Query(default=30, ge=1, le=100),
    after_id: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_owned_repliker(
        db, current_user, repliker_id
    )

    try:
        return _read_events(
            db,
            owner_id=current_user.id,
            repliker_id=repliker_id,
            limit=limit,
            after_id=after_id,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            503,
            "Migracion de eventos World pendiente "
            "en la base activa.",
        ) from exc


# RW_ECONOMIC_EVENTS_OWNER_V2

@router.get("/economy/mine")
def my_economic_events(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Movimientos RCR de los propietarios participantes."""

    from fastapi import HTTPException
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    require_active_owner(current_user)

    statement = text("""
        SELECT *
        FROM (
            SELECT
                'negotiation' AS kind,
                n.id AS resource_id,
                n.status AS status,
                n.title AS title,
                n.currency AS currency,
                n.price_cents AS price_cents,
                n.proposer_repliker_id AS seller_id,
                n.target_repliker_id AS buyer_id,
                n.created_at AS created_at,
                NULL AS contract_id,
                NULL AS transaction_id
            FROM world_negotiations n
            JOIN replikers seller
              ON seller.id = n.proposer_repliker_id
            JOIN replikers buyer
              ON buyer.id = n.target_repliker_id
            WHERE seller.owner_id = :owner
               OR buyer.owner_id = :owner

            UNION ALL

            SELECT
                'contract',
                c.id,
                c.status,
                c.title,
                c.currency,
                c.price_cents,
                c.seller_repliker_id,
                c.buyer_repliker_id,
                c.created_at,
                c.id,
                NULL
            FROM world_contracts c
            JOIN replikers seller
              ON seller.id = c.seller_repliker_id
            JOIN replikers buyer
              ON buyer.id = c.buyer_repliker_id
            WHERE seller.owner_id = :owner
               OR buyer.owner_id = :owner

            UNION ALL

            SELECT
                'settlement',
                s.id,
                'settled',
                c.title,
                tx.currency,
                tx.amount_cents,
                c.seller_repliker_id,
                c.buyer_repliker_id,
                s.created_at,
                c.id,
                tx.id
            FROM world_contract_settlements s
            JOIN world_contracts c
              ON c.id = s.contract_id
            JOIN ledger_transactions tx
              ON tx.id = s.ledger_transaction_id
            JOIN replikers seller
              ON seller.id = c.seller_repliker_id
            JOIN replikers buyer
              ON buyer.id = c.buyer_repliker_id
            WHERE seller.owner_id = :owner
               OR buyer.owner_id = :owner
        ) activity
        ORDER BY
            created_at DESC,
            kind DESC,
            resource_id DESC
        LIMIT :limit
    """)

    try:
        rows = db.execute(
            statement,
            {
                "owner": current_user.id,
                "limit": limit,
            },
        ).mappings().all()

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Actividad economica no disponible.",
        ) from exc

    return {
        "events": [
            {
                **dict(row),
                "id": (
                    str(row["kind"])
                    + "-"
                    + str(row["resource_id"])
                ),
                "created_at": (
                    row["created_at"].isoformat()
                    if hasattr(
                        row["created_at"], "isoformat"
                    )
                    else row["created_at"]
                ),
            }
            for row in rows
        ]
    }


# RW_LEDGER_EVENTS_API_V3

from decimal import Decimal as _RWD
from fastapi import Depends as _RWDp, Query as _RWQ
from sqlalchemy import text as _RWT
from sqlalchemy.orm import Session as _RWS

from app.auth.dependencies import (
    get_current_user as _RWUserDep,
    get_db as _RWDbDep,
)
from app.models.user import User as _RWUser


@router.get("/economy/ledger/mine")
def rw_my_world_ledger(
    limit: int = _RWQ(default=30, ge=1, le=100),
    db: _RWS = _RWDp(_RWDbDep),
    current_user: _RWUser = _RWDp(_RWUserDep),
):
    rows = db.execute(
        _RWT("""
            SELECT
                t.id,
                t.transaction_type,
                t.currency,
                t.amount_cents,
                t.created_at,
                t.external_reference,
                a.repliker_id AS origin_id,
                b.repliker_id AS destination_id,
                ra.name AS origin_name,
                rb.name AS destination_name
            FROM public.ledger_transactions t

            JOIN public.ledger_accounts a
              ON a.id = t.from_account_id

            JOIN public.ledger_accounts b
              ON b.id = t.to_account_id

            LEFT JOIN public.replikers ra
              ON ra.id = a.repliker_id

            LEFT JOIN public.replikers rb
              ON rb.id = b.repliker_id

            WHERE t.currency = 'RCR'
              AND (
                ra.owner_id = :owner
                OR rb.owner_id = :owner
              )

            ORDER BY t.id DESC
            LIMIT :limit
        """),
        {
            "owner": current_user.id,
            "limit": limit,
        },
    ).mappings().all()

    items = []

    for row in rows:

        origin = row["origin_id"]
        destination = row["destination_id"]

        if origin is None:
            kind = "ledger_financiacion"
        elif destination is None:
            kind = "ledger_salida"
        else:
            kind = "ledger_transferencia"

        items.append({
            "id": row["id"],
            "event_key": f"ledger:{row['id']}",
            "kind": kind,
            "status": "registrada",
            "origin_repliker_id": origin,
            "destination_repliker_id": destination,
            "origin_name": row["origin_name"],
            "destination_name": row["destination_name"],
            "amount_cents": row["amount_cents"],
            "amount_rcr": str(
                _RWD(row["amount_cents"]) / 100
            ),
            "currency": row["currency"],
            "transaction_type": row["transaction_type"],
            "source": (
                "demostracion_manual"
                if row["external_reference"]
                   == "rw-demo-transfer-v1"
                else "ledger_simulado"
            ),
            "created_at": (
                row["created_at"].isoformat()
                if row["created_at"]
                else None
            ),
            "real_money": False,
        })

    return {
        "items": items,
        "count": len(items),
        "currency": "RCR",
        "simulation": True,
    }
