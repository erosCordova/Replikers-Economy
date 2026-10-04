from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy import select
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.agentic.project_graph import (
    run_project_lifecycle,
)
from app.auth.dependencies import (
    get_current_user,
    get_db,
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
from app.schemas.agentic import (
    AgenticLifecycleRunResponse,
    AgenticProjectSnapshot,
    AgenticRuntimePublic,
    AgenticToolPublic,
    AgenticToolUpdate,
    AgentToolProfilePublic,
)
from app.services.agentic_service import (
    build_project_snapshot,
    replace_repliker_tools,
    repliker_tool_profile,
    runtime_info,
    tool_catalog,
)


router = APIRouter(
    prefix="/agentic",
    tags=[
        "Agentic Core",
    ],
)


def _project_access(
    *,
    project: Project,
    current_user: User,
):
    if (
        project.client_id
        != current_user.id
        and current_user.role
        != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes acceso "
                "a este proyecto."
            ),
        )


def _repliker_access(
    *,
    repliker: Repliker,
    current_user: User,
    write: bool = False,
):
    if write and repliker.is_system:
        raise HTTPException(
            status_code=403,
            detail=(
                "Los Replikers oficiales "
                "están protegidos y no "
                "pueden modificarse."
            ),
        )

    if (
        repliker.owner_id
        != current_user.id
        and current_user.role
        != "admin"
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Solo el propietario "
                "del Repliker o un "
                "administrador puede "
                "modificar sus herramientas."
            ),
        )


@router.get(
    "/runtime",
    response_model=
        AgenticRuntimePublic,
)
def get_runtime(
    current_user: User = Depends(
        get_current_user
    ),
):
    _ = current_user

    return runtime_info()


@router.get(
    "/tools",
    response_model=
        list[
            AgenticToolPublic
        ],
)
def get_tools(
    current_user: User = Depends(
        get_current_user
    ),
):
    _ = current_user

    return tool_catalog()


@router.get(
    "/replikers/{repliker_id}/tools",
    response_model=
        AgentToolProfilePublic,
)
def get_repliker_tools(
    repliker_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    repliker = db.scalar(
        select(
            Repliker
        )
        .options(
            selectinload(
                Repliker.skills
            )
        )
        .where(
            Repliker.id
            == repliker_id
        )
    )

    if repliker is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Repliker no encontrado."
            ),
        )

    _repliker_access(
        repliker=repliker,
        current_user=current_user,
    )

    return repliker_tool_profile(
        db=db,
        repliker=repliker,
    )


@router.put(
    "/replikers/{repliker_id}/tools",
    response_model=
        AgentToolProfilePublic,
)
def update_repliker_tools(
    repliker_id: int,
    payload: AgenticToolUpdate,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    repliker = db.scalar(
        select(
            Repliker
        )
        .options(
            selectinload(
                Repliker.skills
            )
        )
        .where(
            Repliker.id
            == repliker_id
        )
        .with_for_update()
    )

    if repliker is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Repliker no encontrado."
            ),
        )

    _repliker_access(
        repliker=repliker,
        current_user=current_user,
        write=True,
    )

    try:
        result = (
            replace_repliker_tools(
                db=db,
                repliker=repliker,
                tool_names=
                    payload.tool_names,
            )
        )

        db.commit()

        return result

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/projects/{project_id}",
    response_model=
        AgenticProjectSnapshot,
)
def get_project_agentic_snapshot(
    project_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Proyecto no encontrado."
            ),
        )

    _project_access(
        project=project,
        current_user=current_user,
    )

    return build_project_snapshot(
        db=db,
        project=project,
    )


@router.post(
    "/projects/{project_id}/run",
    response_model=
        AgenticLifecycleRunResponse,
)
def run_agentic_project_lifecycle(
    project_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Proyecto no encontrado."
            ),
        )

    _project_access(
        project=project,
        current_user=current_user,
    )

    try:
        state = (
            run_project_lifecycle(
                db=db,
                project_id=project.id,
            )
        )

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Proyecto desaparecio "
                "durante la ejecucion."
            ),
        )

    return AgenticLifecycleRunResponse(
        project_id=
            project.id,
        project_status=
            project.status,
        payment_status=
            project.payment_status,
        final_stage=str(
            state.get(
                "current_stage",
                "failed",
            )
        ),
        next_action=str(
            state.get(
                "next_action",
                "inspect_failure",
            )
        ),
        contracts_created=int(
            state.get(
                "contracts_created",
                0,
            )
        ),
        contracts_processed=int(
            state.get(
                "contracts_processed",
                0,
            )
        ),
        contracts_completed=int(
            state.get(
                "contracts_completed",
                0,
            )
        ),
        delegations_processed=int(
            state.get(
                "delegations_processed",
                0,
            )
        ),
        execution_attempts=int(
            state.get(
                "execution_attempts",
                0,
            )
        ),
        qa_attempts=int(
            state.get(
                "qa_attempts",
                0,
            )
        ),
        qa_passed=int(
            state.get(
                "qa_passed",
                0,
            )
        ),
        qa_failed=int(
            state.get(
                "qa_failed",
                0,
            )
        ),
        failed_contract_ids=[
            int(item)
            for item
            in state.get(
                "failed_contract_ids",
                [],
            )
        ],
        blocked_reason=str(
            state.get(
                "blocked_reason",
                "",
            )
        ),
        error=str(
            state.get(
                "error",
                "",
            )
        ),
        history=[
            str(item)
            for item
            in state.get(
                "history",
                [],
            )
        ],
    )
