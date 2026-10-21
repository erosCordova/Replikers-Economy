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
