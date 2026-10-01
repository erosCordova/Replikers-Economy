from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_db,
)
from app.execution.policy import (
    ExecutionPolicyError,
)
from app.execution.tool_gateway import (
    ToolGateway,
)
from app.models.contract import (
    TaskContract,
)
from app.models.execution import (
    ExecutionArtifact,
    ExecutionWorkspace,
    ToolExecutionLog,
)
from app.models.project import Project
from app.models.repliker import Repliker
from app.models.user import User
from app.schemas.execution import (
    ArtifactPublic,
    ExecutionRuntimePublic,
    ToolExecutionLogPublic,
    WorkspaceFilesPublic,
    WorkspacePublic,
    WorkspaceReadPublic,
    WorkspaceWriteRequest,
)
from app.services.workspace_service import (
    get_or_create_workspace,
)


router = APIRouter(
    prefix="/execution",
    tags=[
        "Ejecucion segura",
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


def _workspace_or_404(
    *,
    db: Session,
    workspace_id: int,
) -> ExecutionWorkspace:
    workspace = db.get(
        ExecutionWorkspace,
        workspace_id,
    )

    if workspace is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Workspace no encontrado."
            ),
        )

    return workspace


def _can_view_contract(
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


def _can_mutate_contract(
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

    repliker = db.get(
        Repliker,
        contract.repliker_id,
    )

    return bool(
        repliker is not None
        and repliker.owner_id
        == current_user.id
    )


def _workspace_public(
    workspace:
        ExecutionWorkspace,
) -> WorkspacePublic:
    return WorkspacePublic(
        id=workspace.id,
        contract_id=
            workspace.contract_id,
        project_id=
            workspace.project_id,
        task_id=
            workspace.task_id,
        repliker_id=
            workspace.repliker_id,
        status=
            workspace.status,
        storage_driver=
            workspace.storage_driver,
        root_ref=
            workspace.root_ref,
        max_files=
            workspace.max_files,
        max_file_bytes=
            workspace.max_file_bytes,
        max_total_bytes=
            workspace.max_total_bytes,
        created_at=
            workspace.created_at,
    )


@router.get(
    "/runtime",
    response_model=
        ExecutionRuntimePublic,
)
def execution_runtime(
    current_user: User = Depends(
        get_current_user
    ),
):
    _ = current_user

    return ExecutionRuntimePublic(
        workspace_driver="local",
        isolation_mode=(
            "filesystem-policy"
        ),
        docker_available=False,
        command_execution_enabled=False,
        allowed_operations=[
            "workspace_list_files",
            "workspace_read_text",
            "workspace_write_text",
        ],
    )


@router.post(
    "/contracts/{contract_id}/workspace",
    response_model=
        WorkspacePublic,
)
def create_contract_workspace(
    contract_id: int,
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

    if not _can_view_contract(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes acceso "
                "a este contrato."
            ),
        )

    try:
        workspace = (
            get_or_create_workspace(
                db=db,
                contract=contract,
            )
        )

        db.commit()

        db.refresh(
            workspace
        )

        return _workspace_public(
            workspace
        )

    except ExecutionPolicyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/contracts/{contract_id}/workspace",
    response_model=
        WorkspacePublic,
)
def get_contract_workspace(
    contract_id: int,
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

    if not _can_view_contract(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes acceso "
                "a este contrato."
            ),
        )

    workspace = db.scalar(
        select(
            ExecutionWorkspace
        )
        .where(
            ExecutionWorkspace
            .contract_id
            == contract.id
        )
    )

    if workspace is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "El contrato todavia "
                "no tiene workspace."
            ),
        )

    return _workspace_public(
        workspace
    )


@router.get(
    "/workspaces/{workspace_id}/files",
    response_model=
        WorkspaceFilesPublic,
)
def list_files(
    workspace_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    workspace = _workspace_or_404(
        db=db,
        workspace_id=
            workspace_id,
    )

    contract = _contract_or_404(
        db=db,
        contract_id=
            workspace.contract_id,
    )

    if not _can_view_contract(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes acceso "
                "a este workspace."
            ),
        )

    gateway = ToolGateway(
        db=db,
        workspace=workspace,
    )

    files = gateway.list_files()

    db.commit()

    return WorkspaceFilesPublic(
        workspace_id=
            workspace.id,
        files=files,
    )


@router.get(
    "/workspaces/{workspace_id}/file",
    response_model=
        WorkspaceReadPublic,
)
def read_file(
    workspace_id: int,
    path: str = Query(
        min_length=1,
        max_length=900,
    ),
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    workspace = _workspace_or_404(
        db=db,
        workspace_id=
            workspace_id,
    )

    contract = _contract_or_404(
        db=db,
        contract_id=
            workspace.contract_id,
    )

    if not _can_view_contract(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes acceso "
                "a este workspace."
            ),
        )

    gateway = ToolGateway(
        db=db,
        workspace=workspace,
    )

    try:
        content = gateway.read_text(
            path=path
        )

        db.commit()

        return WorkspaceReadPublic(
            path=path,
            content=content,
        )

    except (
        ExecutionPolicyError,
        FileNotFoundError,
    ) as exc:
        db.commit()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.put(
    "/workspaces/{workspace_id}/file",
    response_model=
        ArtifactPublic,
)
def write_file(
    workspace_id: int,
    payload:
        WorkspaceWriteRequest,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    workspace = _workspace_or_404(
        db=db,
        workspace_id=
            workspace_id,
    )

    contract = _contract_or_404(
        db=db,
        contract_id=
            workspace.contract_id,
    )

    if not _can_mutate_contract(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Solo el propietario "
                "del Repliker contratado "
                "o un administrador puede "
                "modificar el workspace."
            ),
        )

    gateway = ToolGateway(
        db=db,
        workspace=workspace,
    )

    try:
        artifact = (
            gateway.write_text(
                path=
                    payload.path,
                content=
                    payload.content,
            )
        )

        db.commit()

        db.refresh(
            artifact
        )

        return ArtifactPublic(
            id=artifact.id,
            workspace_id=
                artifact.workspace_id,
            relative_path=
                artifact.relative_path,
            media_type=
                artifact.media_type,
            size_bytes=
                artifact.size_bytes,
            sha256=
                artifact.sha256,
            created_at=
                artifact.created_at,
            updated_at=
                artifact.updated_at,
        )

    except ExecutionPolicyError as exc:
        db.commit()

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/workspaces/{workspace_id}/logs",
    response_model=
        list[
            ToolExecutionLogPublic
        ],
)
def workspace_logs(
    workspace_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    workspace = _workspace_or_404(
        db=db,
        workspace_id=
            workspace_id,
    )

    contract = _contract_or_404(
        db=db,
        contract_id=
            workspace.contract_id,
    )

    if not _can_view_contract(
        db=db,
        contract=contract,
        current_user=
            current_user,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "No tienes acceso "
                "a estos registros."
            ),
        )

    rows = list(
        db.scalars(
            select(
                ToolExecutionLog
            )
            .where(
                ToolExecutionLog
                .workspace_id
                == workspace.id
            )
            .order_by(
                ToolExecutionLog
                .id.desc()
            )
            .limit(
                100
            )
        ).all()
    )

    return [
        ToolExecutionLogPublic(
            id=row.id,
            workspace_id=
                row.workspace_id,
            contract_id=
                row.contract_id,
            repliker_id=
                row.repliker_id,
            tool_name=
                row.tool_name,
            status=
                row.status,
            target_path=
                row.target_path,
            input_summary=
                row.input_summary,
            output_summary=
                row.output_summary,
            error_summary=
                row.error_summary,
            created_at=
                row.created_at,
        )
        for row
        in rows
    ]
