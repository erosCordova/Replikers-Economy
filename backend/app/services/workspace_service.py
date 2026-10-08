from __future__ import annotations

import hashlib
import mimetypes
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

from app.execution.policy import (
    ExecutionPolicyError,
    ensure_workspace_ready,
    resolve_inside_workspace,
    validate_text_payload,
)
from app.models.contract import (
    ACTIVE_CONTRACT_STATUSES,
    TaskContract,
)
from app.models.execution import (
    ExecutionArtifact,
    ExecutionArtifactBlob,
    ExecutionWorkspace,
    ToolExecutionLog,
)


BACKEND_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

WORKSPACES_ROOT = (
    BACKEND_ROOT
    / ".runtime"
    / "workspaces"
)


def workspace_root(
    workspace: ExecutionWorkspace,
) -> Path:
    root = (
        WORKSPACES_ROOT
        / workspace.root_ref
    )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    resolved_base = (
        WORKSPACES_ROOT
        .resolve()
    )

    resolved_root = (
        root.resolve()
    )

    if (
        resolved_root
        != resolved_base
        and resolved_base
        not in resolved_root.parents
    ):
        raise ExecutionPolicyError(
            "Referencia de workspace invalida."
        )

    return resolved_root


def get_or_create_workspace(
    *,
    db: Session,
    contract: TaskContract,
) -> ExecutionWorkspace:
    if (
        contract.status
        not in ACTIVE_CONTRACT_STATUSES
    ):
        raise ExecutionPolicyError(
            "El contrato debe estar activo "
            "o adjudicado para tener workspace."
        )

    existing = db.scalar(
        select(
            ExecutionWorkspace
        )
        .where(
            ExecutionWorkspace
            .contract_id
            == contract.id
        )
    )

    if existing is not None:
        workspace_root(
            existing
        )

        return existing

    workspace = ExecutionWorkspace(
        contract_id=
            contract.id,
        project_id=
            contract.project_id,
        task_id=
            contract.task_id,
        repliker_id=
            contract.repliker_id,
        status="ready",
        storage_driver="local",
        root_ref=(
            f"contract-{contract.id:08d}"
        ),
        max_files=250,
        max_file_bytes=
            2_000_000,
        max_total_bytes=
            25_000_000,
    )

    db.add(
        workspace
    )

    db.flush()

    root = workspace_root(
        workspace
    )

    (
        root
        / ".replikers-workspace"
    ).write_text(
        (
            "managed-by=replikers-economy\n"
            f"workspace-id={workspace.id}\n"
            f"contract-id={contract.id}\n"
            f"project-id={contract.project_id}\n"
            f"task-id={contract.task_id}\n"
            f"repliker-id={contract.repliker_id}\n"
        ),
        encoding="utf-8",
    )

    return workspace


def log_tool_execution(
    *,
    db: Session,
    workspace: ExecutionWorkspace,
    actor_repliker_id: int | None = None,
    tool_name: str,
    status: str,
    target_path: str | None = None,
    input_summary: str = "",
    output_summary: str = "",
    error_summary: str = "",
) -> ToolExecutionLog:
    log = ToolExecutionLog(
        workspace_id=
            workspace.id,
        contract_id=
            workspace.contract_id,
        repliker_id=(
            workspace.repliker_id
            if actor_repliker_id is None
            else int(actor_repliker_id)
        ),
        tool_name=
            tool_name,
        status=
            status,
        target_path=
            target_path,
        input_summary=
            input_summary[:2000],
        output_summary=
            output_summary[:4000],
        error_summary=
            error_summary[:4000],
    )

    db.add(
        log
    )

    return log

def _file_count(
    *,
    db: Session,
    workspace_id: int,
) -> int:
    return int(
        db.scalar(
            select(
                func.count(
                    ExecutionArtifact.id
                )
            )
            .where(
                ExecutionArtifact
                .workspace_id
                == workspace_id
            )
        )
        or 0
    )


def _total_size(
    *,
    db: Session,
    workspace_id: int,
) -> int:
    return int(
        db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        ExecutionArtifact
                        .size_bytes
                    ),
                    0,
                )
            )
            .where(
                ExecutionArtifact
                .workspace_id
                == workspace_id
            )
        )
        or 0
    )


def write_text_file(
    *,
    db: Session,
    workspace: ExecutionWorkspace,
    relative_path: str,
    content: str,
) -> ExecutionArtifact:
    ensure_workspace_ready(
        workspace.status
    )

    root = workspace_root(
        workspace
    )

    target = resolve_inside_workspace(
        workspace_root=root,
        relative_path=
            relative_path,
    )

    payload = validate_text_payload(
        content=content,
        max_file_bytes=
            workspace.max_file_bytes,
    )

    existing = db.scalar(
        select(
            ExecutionArtifact
        )
        .where(
            ExecutionArtifact
            .workspace_id
            == workspace.id,
            ExecutionArtifact
            .relative_path
            == relative_path,
        )
    )

    existing_size = (
        existing.size_bytes
        if existing
        else 0
    )

    if (
        existing is None
        and _file_count(
            db=db,
            workspace_id=
                workspace.id,
        )
        >= workspace.max_files
    ):
        raise ExecutionPolicyError(
            "El workspace alcanzo el "
            "limite de archivos."
        )

    projected_total = (
        _total_size(
            db=db,
            workspace_id=
                workspace.id,
        )
        - existing_size
        + len(payload)
    )

    if (
        projected_total
        > workspace.max_total_bytes
    ):
        raise ExecutionPolicyError(
            "El workspace supera su "
            "limite total de almacenamiento."
        )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with NamedTemporaryFile(
        mode="wb",
        dir=str(
            target.parent
        ),
        delete=False,
    ) as temp:
        temp.write(
            payload
        )

        temporary_name = (
            temp.name
        )

    os.replace(
        temporary_name,
        target,
    )

    digest = (
        hashlib.sha256(
            payload
        )
        .hexdigest()
    )

    media_type = (
        mimetypes.guess_type(
            target.name
        )[0]
        or "text/plain"
    )

    if existing is None:
        artifact = (
            ExecutionArtifact(
                workspace_id=
                    workspace.id,
                relative_path=
                    relative_path,
                media_type=
                    media_type,
                size_bytes=
                    len(payload),
                sha256=
                    digest,
            )
        )

        db.add(
            artifact
        )

    else:
        artifact = existing

        artifact.media_type = (
            media_type
        )

        artifact.size_bytes = (
            len(payload)
        )

        artifact.sha256 = (
            digest
        )

    db.flush()

    blob = db.get(
        ExecutionArtifactBlob,
        artifact.id,
    )

    if blob is None:
        blob = ExecutionArtifactBlob(
            artifact_id=
                artifact.id,
            content=
                payload,
            size_bytes=
                len(payload),
            sha256=
                digest,
        )

        db.add(
            blob
        )

    else:
        blob.content = payload
        blob.size_bytes = len(
            payload
        )
        blob.sha256 = digest

    workspace.storage_driver = (
        "hybrid-db"
    )

    db.flush()

    return artifact


def read_durable_artifact_bytes(
    *,
    db: Session,
    workspace: ExecutionWorkspace,
    artifact: ExecutionArtifact,
) -> bytes:
    if (
        artifact.workspace_id
        != workspace.id
    ):
        raise ExecutionPolicyError(
            "El artefacto no pertenece "
            "a este workspace."
        )

    blob = db.get(
        ExecutionArtifactBlob,
        artifact.id,
    )

    if blob is not None:
        payload = bytes(
            blob.content
        )

    else:
        payload = (
            read_workspace_file_bytes(
                workspace=workspace,
                relative_path=
                    artifact.relative_path,
            )
        )

        digest = (
            hashlib.sha256(
                payload
            )
            .hexdigest()
        )

        if (
            digest
            != artifact.sha256
        ):
            raise ExecutionPolicyError(
                "La integridad del archivo "
                "no coincide con SHA-256."
            )

        blob = ExecutionArtifactBlob(
            artifact_id=
                artifact.id,
            content=
                payload,
            size_bytes=
                len(payload),
            sha256=
                digest,
        )

        db.add(
            blob
        )

        workspace.storage_driver = (
            "hybrid-db"
        )

        db.flush()

    if (
        len(payload)
        != artifact.size_bytes
    ):
        raise ExecutionPolicyError(
            "El tamaño durable del archivo "
            "no coincide con sus metadatos."
        )

    digest = (
        hashlib.sha256(
            payload
        )
        .hexdigest()
    )

    if digest != artifact.sha256:
        raise ExecutionPolicyError(
            "La integridad durable "
            "del archivo es inválida."
        )

    return payload


def read_workspace_file_bytes(
    *,
    workspace: ExecutionWorkspace,
    relative_path: str,
) -> bytes:
    """
    Lee bytes reales de un archivo autorizado.

    Se utiliza para verificaciones criptograficas
    y evita confiar solamente en metadatos de DB.
    """

    root = workspace_root(
        workspace
    )

    target = resolve_inside_workspace(
        workspace_root=root,
        relative_path=relative_path,
    )

    if (
        not target.exists()
        or not target.is_file()
    ):
        raise FileNotFoundError(
            "Archivo no encontrado."
        )

    size = target.stat().st_size

    if (
        size
        > workspace.max_file_bytes
    ):
        raise ExecutionPolicyError(
            "El archivo excede el limite "
            "de lectura permitido."
        )

    payload = target.read_bytes()

    if (
        len(payload)
        > workspace.max_file_bytes
    ):
        raise ExecutionPolicyError(
            "El archivo excede el limite "
            "de lectura permitido."
        )

    return payload


def read_text_file(
    *,
    workspace: ExecutionWorkspace,
    relative_path: str,
) -> str:
    root = workspace_root(
        workspace
    )

    target = resolve_inside_workspace(
        workspace_root=root,
        relative_path=
            relative_path,
    )

    if (
        not target.exists()
        or not target.is_file()
    ):
        raise FileNotFoundError(
            "Archivo no encontrado."
        )

    if (
        target.stat().st_size
        > workspace.max_file_bytes
    ):
        raise ExecutionPolicyError(
            "El archivo excede el limite "
            "de lectura permitido."
        )

    try:
        return target.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError as exc:
        raise ExecutionPolicyError(
            "La herramienta de texto no "
            "puede leer archivos binarios."
        ) from exc


def list_workspace_files(
    *,
    workspace: ExecutionWorkspace,
) -> list[str]:
    root = workspace_root(
        workspace
    )

    files = []

    for path in root.rglob(
        "*"
    ):
        if not path.is_file():
            continue

        relative = (
            path.relative_to(
                root
            )
            .as_posix()
        )

        if relative == (
            ".replikers-workspace"
        ):
            continue

        files.append(
            relative
        )

    files.sort()

    return files
