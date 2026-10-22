"""Control HTTP local y autenticado de Gemini."""

import os
from threading import RLock

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.core.config import settings
from app.services.world_access_service import require_active_owner
from app.agentic.world_live_supervisor import (
    LiveSupervisorConfig,
    LiveSupervisorError,
    verify_agents,
)
from app.agentic.world_live_supervisor_control import (
    LiveSupervisorController,
)

router = APIRouter(
    prefix="/world/scheduler/live/control",
    tags=["Replikers World - Supervisor"],
)

_lock = RLock()
_controller = None
_pilot_used = False


def _owner(user):
    require_active_owner(user)

    config = LiveSupervisorConfig(max_rounds=1)

    if user.id != config.owner_id:
        raise HTTPException(
            status_code=403,
            detail="Propietario no autorizado.",
        )

    return config


def _enabled():
    return (
        os.getenv("RW_LIVE_SUPERVISOR_HTTP_ENABLED") == "1"
        and os.getenv("RW_LIVE_SUPERVISOR_OPT_IN") == "1"
        and str(settings.ENVIRONMENT).lower()
        in ("development", "local")
        and os.getenv("ECONOMY_MODE", "simulation").lower()
        == "simulation"
        and os.getenv("REAL_PAYMENTS_ENABLED", "false").lower()
        == "false"
        and os.getenv("RW_SUPERVISOR_BIND", "0") != "1"
    )


def _headers(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"


def _snapshot(config):
    with _lock:
        current = _controller

        if current is None:
            return {
                "pilot_used": _pilot_used,
                "status": "not_started",
                "running": False,
                "stop_requested": False,
                "executions_completed": 0,
                "executions_failed": 0,
                "last_error_type": None,
                "owner_id": config.owner_id,
                "max_rounds": config.max_rounds,
                "scope": "current_process",
                "http_enabled": _enabled(),
                "real_payments_active": False,
            }

        state = current.snapshot()

        if state["running"] and state["stop_requested"]:
            state["status"] = "stopping"

        return {
            "pilot_used": _pilot_used,
            **state,
            "http_enabled": _enabled(),
            "real_payments_active": False,
        }


@router.get("/mine")
def my_control_status(
    response: Response,
    user=Depends(get_current_user),
):
    config = _owner(user)
    _headers(response)
    return _snapshot(config)


@router.post("/mine/start")
def start_my_supervisor(
    response: Response,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    global _controller, _pilot_used

    config = _owner(user)
    _headers(response)

    with _lock:
        if _pilot_used:
            raise HTTPException(
                status_code=409,
                detail="Piloto ya utilizado en este proceso.",
            )

        if not _enabled():
            raise HTTPException(
                status_code=403,
                detail="Inicio HTTP deshabilitado.",
            )

        if (
            _controller is not None
            and _controller.snapshot()["running"]
        ):
            raise HTTPException(
                status_code=409,
                detail="Supervisor ocupado.",
            )

        try:
            verify_agents(db, config)
        except LiveSupervisorError as error:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error
        except Exception as error:
            db.rollback()
            raise HTTPException(
                status_code=503,
                detail="No fue posible verificar las politicas.",
            ) from error

        db.rollback()

        if _controller is None:
            _controller = LiveSupervisorController(
                config=config
            )

        try:
            started = _controller.start()
        except LiveSupervisorError as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        if not started:
            raise HTTPException(
                status_code=409,
                detail="Supervisor ocupado.",
            )

        _pilot_used = True

        return {
            **_snapshot(config),
            "started": True,
        }


@router.post("/mine/stop")
def stop_my_supervisor(
    response: Response,
    user=Depends(get_current_user),
):
    config = _owner(user)
    _headers(response)

    with _lock:
        if _controller is None:
            return {
                **_snapshot(config),
                "stopped": True,
            }

        stopped = _controller.stop(timeout=0.2)

        return {
            **_snapshot(config),
            "stop_requested": True,
            "stopped": stopped,
        }
