from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.models.contract import (
    TaskContract,
)
from app.models.project import (
    Project,
)
from app.models.repliker import (
    Repliker,
)
from app.models.user import (
    User,
)
from app.schemas.execution_agent import (
    ExecutionAgentRunRequest,
    ExecutionAgentRunResponse,
    ExecutionGraphArtifactPublic,
)
from app.services.execution_agent_service import (
    ContractExecutionError,
    run_contract_execution,
)


router = APIRouter(
    prefix="/execution",
    tags=[
        "Ejecucion agentica",
    ],
)


def _contract_or_404(
    *,
    db: Session,
    contract_id: int,
) -> TaskContract:
    contract = db.get(
        TaskContract,
        contract_id,
    )

    if contract is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Contrato no encontrado."
            ),
        )

    return contract


def _can_trigger_execution(
    *,
    db: Session,
    contract: TaskContract,
    current_user: User,
) -> bool:
    if (
        current_user.role
        == "admin"
    ):
        return True

    project = db.get(
        Project,
        contract.project_id,
    )

    if (
        project is not None
        and project.client_id
        == current_user.id
    ):
        return True

    repliker = db.get(
        Repliker,
        contract.repliker_id,
    )

    return bool(
        repliker is not None
        and repliker.owner_id
        == current_user.id
    )


@router.post(
    "/contracts/{contract_id}/run",
    response_model=
        ExecutionAgentRunResponse,
)
def run_execution_agent(
    contract_id: int,
    payload:
        ExecutionAgentRunRequest,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    contract = _contract_or_404(
        db=db,
        contract_id=
            contract_id,
    )

    if not _can_trigger_execution(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes permiso "
                "para iniciar esta ejecucion."
            ),
        )

    try:
        state = (
            run_contract_execution(
                db=db,
                contract_id=
                    contract.id,
                instruction=
                    payload.instruction,
            )
        )

    except ContractExecutionError as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    artifacts = [
        ExecutionGraphArtifactPublic(
            id=int(
                artifact["id"]
            ),
            relative_path=str(
                artifact[
                    "relative_path"
                ]
            ),
            media_type=str(
                artifact[
                    "media_type"
                ]
            ),
            size_bytes=int(
                artifact[
                    "size_bytes"
                ]
            ),
            sha256=str(
                artifact[
                    "sha256"
                ]
            ),
        )
        for artifact
        in state.get(
            "artifacts",
            [],
        )
    ]

    return ExecutionAgentRunResponse(
        contract_id=
            contract.id,
        project_id=int(
            state.get(
                "project_id",
                contract.project_id,
            )
        ),
        task_id=int(
            state.get(
                "task_id",
                contract.task_id,
            )
        ),
        repliker_id=int(
            state.get(
                "repliker_id",
                contract.repliker_id,
            )
        ),
        workspace_id=int(
            state.get(
                "workspace_id",
                0,
            )
        ),
        current_node=str(
            state.get(
                "current_node",
                "unknown",
            )
        ),
        status=str(
            state.get(
                "status",
                "unknown",
            )
        ),
        response_text=str(
            state.get(
                "response_text",
                "",
            )
        ),
        error=str(
            state.get(
                "error",
                "",
            )
        ),
        artifact_count=int(
            state.get(
                "artifact_count",
                0,
            )
        ),
        artifacts=
            artifacts,
        trace=[
            str(item)
            for item
            in state.get(
                "trace",
                [],
            )
        ],
    )
