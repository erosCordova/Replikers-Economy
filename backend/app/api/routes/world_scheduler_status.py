"""Endpoint autenticado de supervision Replikers World."""

from fastapi import APIRouter, Depends, Response

from app.auth.dependencies import get_current_user
from app.agentic.world_scheduler_status import (
    owner_scheduler_snapshot,
)

router = APIRouter(
    prefix="/world/scheduler",
    tags=["Replikers World - Supervisor"],
)


@router.get("/mine")
def my_world_scheduler_status(
    response: Response,
    current_user=Depends(get_current_user),
):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"

    return owner_scheduler_snapshot(int(current_user.id))


# RW_LIVE_SUPERVISOR_STATUS_V1
# Solo lectura. No registra ni inicia un controlador.

import os as _rw_live_os
from fastapi import HTTPException as _RWLiveHTTPException
from app.services.world_access_service import (
    require_active_owner as _rw_require_active_owner,
)
from app.agentic.world_live_supervisor import (
    LiveSupervisorConfig as _RWLiveConfig,
    LiveSupervisorError as _RWLiveError,
    verify_environment as _rw_verify_live_environment,
)


@router.get("/live/mine")
def my_live_world_supervisor_status(
    response: Response,
    current_user=Depends(get_current_user),
):
    _rw_require_active_owner(current_user)

    config = _RWLiveConfig()

    if current_user.id != config.owner_id:
        raise _RWLiveHTTPException(
            status_code=403,
            detail="Supervisor no configurado para este propietario.",
        )

    opt_in = (
        _rw_live_os.getenv(
            "RW_LIVE_SUPERVISOR_OPT_IN"
        ) == "1"
    )

    ready = False

    if opt_in:
        try:
            _rw_verify_live_environment()
            ready = True
        except _RWLiveError:
            ready = False

    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"

    return {
        "status": (
            "configured_inactive"
            if ready
            else "blocked"
        ),
        "running": False,
        "can_start_from_interface": False,
        "start_endpoint_available": False,
        "model_name": config.model_name,
        "max_rounds": config.max_rounds,
        "interval_seconds": config.interval_seconds,
        "agent_ids": list(config.agent_ids),
        "external_ai_active": False,
        "real_payments_active": False,
        "scope": "current_process",
        "note": (
            "Estado de configuracion. El control HTTP "
            "de inicio y parada aun no esta habilitado."
        ),
    }
