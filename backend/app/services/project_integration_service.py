from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentic.execution_tools import (
    build_execution_workspace_tools,
)
from app.agentic.model import get_chat_model
from app.agentic.provider_retry import (
    invoke_with_transient_retry,
)
from app.execution.policy import (
    resolve_inside_workspace,
)
from app.models.execution import (
    ExecutionArtifact,
    ExecutionArtifactBlob,
    ExecutionWorkspace,
)
from app.models.project import (
    Project,
    ProjectRequirement,
)
from app.models.task import Task
from app.services.activity_service import (
    record_activity,
)
from app.services.workspace_service import (
    log_tool_execution,
    read_durable_artifact_bytes,
    workspace_root,
    write_text_file,
)


SOURCE_PREFIX = "__integration_sources__/"
DELIVERY_PREFIX = "__project_delivery__/"

INTEGRATION_MARKER_PATH = (
    DELIVERY_PREFIX
    + "REPLIKERS_INTEGRATION.json"
)

README_PATH = (
    DELIVERY_PREFIX
    + "README.md"
)

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".sql",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".csv",
    ".env",
}


class ProjectIntegrationError(
    ValueError
):
    pass


def _normalize(
    path: str,
) -> str:
    return (
        str(path)
        .replace("\\", "/")
        .lstrip("/")
    )


def _is_text_artifact(
    artifact: ExecutionArtifact,
) -> bool:
    media_type = (
        artifact.media_type
        or ""
    ).lower()

    if (
        media_type.startswith(
            "text/"
        )
        or media_type
        in {
            "application/json",
            "application/javascript",
            "application/xml",
        }
    ):
        return True

    path = (
        artifact.relative_path
        .lower()
    )

    return any(
        path.endswith(extension)
        for extension
        in TEXT_EXTENSIONS
    )


def validate_delivery_paths(
    paths: list[str],
) -> list[str]:
    normalized = sorted(
        {
            _normalize(path)
            for path in paths
        }
    )

    if (
        INTEGRATION_MARKER_PATH
        not in normalized
    ):
        raise ProjectIntegrationError(
            "La entrega no contiene "
            "el manifiesto de integración."
        )

    lower_paths = {
        path.lower()
        for path in normalized
    }

    if (
        README_PATH.lower()
        not in lower_paths
    ):
        raise ProjectIntegrationError(
            "La entrega integrada debe "
            "contener README.md."
        )

    deliverables = [
        path
        for path in normalized
        if path
        != INTEGRATION_MARKER_PATH
    ]

    if len(deliverables) < 2:
        raise ProjectIntegrationError(
            "La entrega integrada contiene "
            "muy pocos archivos para "
            "considerarse un proyecto."
        )

    forbidden_prefix = (
        DELIVERY_PREFIX
        + "tarea-"
    ).lower()

    if any(
        path.lower().startswith(
            forbidden_prefix
        )
        for path in deliverables
    ):
        raise ProjectIntegrationError(
            "La entrega final no puede "
            "estar separada por tareas."
        )

    return normalized


def _project_workspaces(
    *,
    db: Session,
    project_id: int,
) -> list[ExecutionWorkspace]:
    return list(
        db.scalars(
            select(
                ExecutionWorkspace
            )
            .where(
                ExecutionWorkspace
                .project_id
                == project_id
            )
            .order_by(
                ExecutionWorkspace.id
            )
        ).all()
    )


def _source_rows(
    *,
    db: Session,
    workspaces:
        list[ExecutionWorkspace],
) -> list[
    tuple[
        ExecutionWorkspace,
        ExecutionArtifact,
    ]
]:
    workspace_map = {
        workspace.id:
            workspace
        for workspace
        in workspaces
    }

    workspace_ids = list(
        workspace_map
    )

    if not workspace_ids:
        return []

    artifacts = list(
        db.scalars(
            select(
                ExecutionArtifact
            )
            .where(
                ExecutionArtifact
                .workspace_id
                .in_(
                    workspace_ids
                )
            )
            .order_by(
                ExecutionArtifact.id
            )
        ).all()
    )

    rows = []

    for artifact in artifacts:
        path = _normalize(
            artifact.relative_path
        )

        if (
            path.startswith(
                SOURCE_PREFIX
            )
            or path.startswith(
                DELIVERY_PREFIX
            )
        ):
            continue

        workspace = (
            workspace_map.get(
                artifact.workspace_id
            )
        )

        if workspace is None:
            continue

        rows.append(
            (
                workspace,
                artifact,
            )
        )

    return rows


def _source_signature(
    rows: list[
        tuple[
            ExecutionWorkspace,
            ExecutionArtifact,
        ]
    ],
) -> str:
    digest = hashlib.sha256()

    for workspace, artifact in rows:
        line = (
            f"{workspace.id}|"
            f"{workspace.task_id}|"
            f"{artifact.id}|"
            f"{_normalize(artifact.relative_path)}|"
            f"{artifact.sha256}\n"
        )

        digest.update(
            line.encode("utf-8")
        )

    return digest.hexdigest()


def _delivery_signature(
    artifacts:
        list[ExecutionArtifact],
) -> str:
    digest = hashlib.sha256()

    for artifact in sorted(
        artifacts,
        key=lambda item: (
            _normalize(
                item.relative_path
            ),
            item.id,
        ),
    ):
        if (
            artifact.relative_path
            == INTEGRATION_MARKER_PATH
        ):
            continue

        line = (
            f"{_normalize(artifact.relative_path)}|"
            f"{artifact.sha256}|"
            f"{artifact.size_bytes}\n"
        )

        digest.update(
            line.encode("utf-8")
        )

    return digest.hexdigest()


def _write_bytes(
    *,
    db: Session,
    workspace: ExecutionWorkspace,
    relative_path: str,
    payload: bytes,
    media_type: str,
) -> ExecutionArtifact:
    relative_path = _normalize(
        relative_path
    )

    root = workspace_root(
        workspace
    )

    target = resolve_inside_workspace(
        workspace_root=root,
        relative_path=
            relative_path,
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.write_bytes(
        payload
    )

    digest = (
        hashlib.sha256(
            payload
        )
        .hexdigest()
    )

    artifact = db.scalar(
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

    if artifact is None:
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
        db.flush()

    else:
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
        blob = (
            ExecutionArtifactBlob(
                artifact_id=
                    artifact.id,
                content=
                    payload,
                size_bytes=
                    len(payload),
                sha256=
                    digest,
            )
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


def _clear_generated(
    *,
    db: Session,
    workspace: ExecutionWorkspace,
):
    artifacts = list(
        db.scalars(
            select(
                ExecutionArtifact
            )
            .where(
                ExecutionArtifact
                .workspace_id
                == workspace.id
            )
        ).all()
    )

    generated = [
        artifact
        for artifact
        in artifacts
        if (
            _normalize(
                artifact.relative_path
            )
            .startswith(
                SOURCE_PREFIX
            )
            or
            _normalize(
                artifact.relative_path
            )
            .startswith(
                DELIVERY_PREFIX
            )
        )
    ]

    root = workspace_root(
        workspace
    )

    for directory in (
        SOURCE_PREFIX.rstrip("/"),
        DELIVERY_PREFIX.rstrip("/"),
    ):
        target = (
            root
            / directory
        )

        if target.exists():
            shutil.rmtree(
                target
            )

    for artifact in generated:
        blob = db.get(
            ExecutionArtifactBlob,
            artifact.id,
        )

        if blob is not None:
            db.delete(
                blob
            )

        db.delete(
            artifact
        )

    db.flush()


def _seed_sources(
    *,
    db: Session,
    target:
        ExecutionWorkspace,
    rows: list[
        tuple[
            ExecutionWorkspace,
            ExecutionArtifact,
        ]
    ],
) -> int:
    total_size = sum(
        int(artifact.size_bytes)
        for _, artifact
        in rows
    )

    largest = max(
        (
            int(
                artifact.size_bytes
            )
            for _, artifact
            in rows
        ),
        default=0,
    )

    target.max_files = max(
        target.max_files,
        len(rows) * 3 + 100,
    )

    target.max_file_bytes = max(
        target.max_file_bytes,
        largest + 1024,
    )

    target.max_total_bytes = max(
        target.max_total_bytes,
        total_size * 3
        + 10_000_000,
    )

    db.flush()

    copied = 0
    binary_sources = []

    for workspace, artifact in rows:
        payload = (
            read_durable_artifact_bytes(
                db=db,
                workspace=
                    workspace,
                artifact=
                    artifact,
            )
        )

        source_path = (
            f"{SOURCE_PREFIX}"
            f"tarea-{workspace.task_id}/"
            f"workspace-{workspace.id}/"
            f"{_normalize(artifact.relative_path)}"
        )

        if _is_text_artifact(
            artifact
        ):
            try:
                content = (
                    payload.decode(
                        "utf-8"
                    )
                )

                write_text_file(
                    db=db,
                    workspace=
                        target,
                    relative_path=
                        source_path,
                    content=
                        content,
                )

            except UnicodeDecodeError:
                _write_bytes(
                    db=db,
                    workspace=
                        target,
                    relative_path=
                        source_path,
                    payload=
                        payload,
                    media_type=
                        artifact.media_type,
                )

                binary_sources.append(
                    source_path
                )

        else:
            _write_bytes(
                db=db,
                workspace=
                    target,
                relative_path=
                    source_path,
                payload=
                    payload,
                media_type=
                    artifact.media_type,
            )

            binary_sources.append(
                source_path
            )

        copied += 1

    write_text_file(
        db=db,
        workspace=target,
        relative_path=(
            SOURCE_PREFIX
            + "FUENTES.json"
        ),
        content=json.dumps(
            {
                "source_count":
                    copied,
                "binary_sources":
                    binary_sources,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    db.flush()

    return copied


def _project_context(
    *,
    db: Session,
    project: Project,
) -> dict:
    requirements = list(
        db.scalars(
            select(
                ProjectRequirement
            )
            .where(
                ProjectRequirement
                .project_id
                == project.id
            )
            .order_by(
                ProjectRequirement.id
            )
        ).all()
    )

    tasks = list(
        db.scalars(
            select(
                Task
            )
            .where(
                Task.project_id
                == project.id
            )
            .order_by(
                Task.id
            )
        ).all()
    )

    return {
        "project_id":
            project.id,
        "title":
            project.title,
        "description":
            project.description,
        "requirements": [
            {
                "id":
                    item.id,
                "title":
                    item.title,
                "description":
                    item.description,
                "mandatory":
                    item.is_mandatory,
            }
            for item
            in requirements
        ],
        "tasks": [
            {
                "id":
                    task.id,
                "title":
                    task.title,
                "description":
                    task.description,
                "status":
                    task.status,
                "specialty":
                    task.required_specialty,
            }
            for task
            in tasks
        ],
    }


INTEGRATION_SYSTEM_PROMPT = f"""
Eres el Integrador Final de Repliker Economy.

Tu responsabilidad NO es crear otra tarea independiente.
Debes tomar los entregables reales producidos por todos
los Replikers y convertirlos en UN SOLO PROYECTO
coherente, ejecutable y listo para entregar.

Las fuentes originales están dentro de:

{SOURCE_PREFIX}

La única entrega final válida debe quedar dentro de:

{DELIVERY_PREFIX}

REGLAS OBLIGATORIAS:

1. Inspecciona primero los archivos disponibles.

2. No copies simplemente carpetas tarea-N a la entrega.

3. Debes integrar los componentes en una arquitectura
   única y coherente.

4. Si existen frontend, backend y base de datos:
   - deben usar el mismo modelo de datos;
   - deben usar nombres de campos compatibles;
   - el frontend debe consumir endpoints reales;
   - los endpoints deben existir en el backend;
   - la persistencia debe coincidir con la API.

5. Corrige incompatibilidades entre entregables.

6. Incluye todas las dependencias necesarias:
   requirements.txt, pyproject.toml, package.json,
   configuración u otros archivos equivalentes
   cuando corresponda.

7. Si frontend y backend usan orígenes distintos,
   configura CORS cuando sea necesario.

8. Incluye configuración de entorno mediante
   .env.example cuando corresponda. Nunca escribas
   secretos reales.

9. Crea obligatoriamente:
   {README_PATH}

   Debe explicar exactamente cómo instalar,
   configurar, ejecutar y probar el proyecto.

10. Las pruebas deben probar LA IMPLEMENTACIÓN REAL.
    Está prohibido crear dentro de los tests una API,
    base de datos, clase o interfaz ficticia que
    reimplemente el sistema únicamente para que
    la prueba pase.

11. Los tests deben importar o ejercitar los archivos
    reales producidos en la entrega.

12. Cuando haya Python, usa run_python para validar
    scripts o pruebas cuando sea posible.

13. Si run_python indica sandbox_available=false,
    no ejecutes nada en el host ni intentes evadir
    el aislamiento.

14. Nunca declares que algo funciona solamente porque
    el código parece correcto. Deja evidencia real en
    los archivos y realiza las comprobaciones que las
    herramientas permitan.

15. No escribas el resultado final fuera de
    {DELIVERY_PREFIX}.

16. El usuario debe recibir un proyecto normal.
    Dentro de {DELIVERY_PREFIX} NO deben existir
    carpetas tarea-10, tarea-11, tarea-12, etc.

17. Para una aplicación web típica, una estructura
    apropiada puede ser:

    {DELIVERY_PREFIX}backend/
    {DELIVERY_PREFIX}frontend/
    {DELIVERY_PREFIX}README.md
    {DELIVERY_PREFIX}.env.example

    pero debes adaptarla al proyecto real.

18. No crees {INTEGRATION_MARKER_PATH}.
    Ese archivo lo genera el sistema después de
    verificar tu trabajo.
""".strip()


def _delivery_artifacts(
    *,
    db: Session,
    workspace_id: int,
) -> list[ExecutionArtifact]:
    rows = list(
        db.scalars(
            select(
                ExecutionArtifact
            )
            .where(
                ExecutionArtifact
                .workspace_id
                == workspace_id
            )
            .order_by(
                ExecutionArtifact.id
            )
        ).all()
    )

    return [
        row
        for row in rows
        if _normalize(
            row.relative_path
        ).startswith(
            DELIVERY_PREFIX
        )
    ]


def _existing_integration(
    *,
    db: Session,
    workspaces:
        list[ExecutionWorkspace],
    source_signature: str,
) -> dict | None:
    for workspace in reversed(
        workspaces
    ):
        marker = db.scalar(
            select(
                ExecutionArtifact
            )
            .where(
                ExecutionArtifact
                .workspace_id
                == workspace.id,
                ExecutionArtifact
                .relative_path
                == INTEGRATION_MARKER_PATH,
            )
        )

        if marker is None:
            continue

        try:
            payload = (
                read_durable_artifact_bytes(
                    db=db,
                    workspace=
                        workspace,
                    artifact=
                        marker,
                )
            )

            data = json.loads(
                payload.decode(
                    "utf-8"
                )
            )

            if (
                data.get(
                    "source_signature"
                )
                != source_signature
            ):
                continue

            delivery = (
                _delivery_artifacts(
                    db=db,
                    workspace_id=
                        workspace.id,
                )
            )

            paths = (
                validate_delivery_paths(
                    [
                        row.relative_path
                        for row
                        in delivery
                    ]
                )
            )

            actual_signature = (
                _delivery_signature(
                    delivery
                )
            )

            if (
                data.get(
                    "delivery_signature"
                )
                != actual_signature
            ):
                continue

            return {
                "integration_ready":
                    True,
                "reused":
                    True,
                "integration_workspace_id":
                    workspace.id,
                "source_signature":
                    source_signature,
                "files_count":
                    len(paths),
                "files":
                    paths,
            }

        except Exception:
            continue

    return None


def run_project_integration(
    *,
    db: Session,
    project_id: int,
) -> dict:
    project = db.get(
        Project,
        project_id,
    )

    if project is None:
        raise ProjectIntegrationError(
            "Proyecto no encontrado."
        )

    tasks = list(
        db.scalars(
            select(
                Task
            )
            .where(
                Task.project_id
                == project.id
            )
            .order_by(
                Task.id
            )
        ).all()
    )

    if not tasks:
        raise ProjectIntegrationError(
            "El proyecto no contiene tareas."
        )

    if any(
        task.status
        != "completed"
        for task in tasks
    ):
        raise ProjectIntegrationError(
            "No se puede integrar el proyecto "
            "hasta completar todas las tareas."
        )

    workspaces = (
        _project_workspaces(
            db=db,
            project_id=
                project.id,
        )
    )

    if not workspaces:
        raise ProjectIntegrationError(
            "El proyecto no tiene workspaces "
            "de ejecución."
        )

    rows = _source_rows(
        db=db,
        workspaces=workspaces,
    )

    if not rows:
        raise ProjectIntegrationError(
            "No existen artefactos reales "
            "para integrar."
        )

    source_signature = (
        _source_signature(
            rows
        )
    )

    existing = (
        _existing_integration(
            db=db,
            workspaces=
                workspaces,
            source_signature=
                source_signature,
        )
    )

    if existing is not None:
        return existing

    target = workspaces[-1]

    _clear_generated(
        db=db,
        workspace=
            target,
    )

    copied = _seed_sources(
        db=db,
        target=
            target,
        rows=rows,
    )

    project_context = (
        _project_context(
            db=db,
            project=project,
        )
    )

    tools = (
        build_execution_workspace_tools(
            db=db,
            workspace=
                target,
            actor_repliker_id=
                target.repliker_id,
        )
    )

    agent = create_agent(
        model=get_chat_model(
            temperature=0.1
        ),
        tools=tools,
        system_prompt=
            INTEGRATION_SYSTEM_PROMPT,
        name=(
            f"project_{project.id}_"
            "final_integrator"
        ),
    )

    log_tool_execution(
        db=db,
        workspace=target,
        actor_repliker_id=
            target.repliker_id,
        tool_name=(
            "project_integration_agent_run"
        ),
        status="running",
        input_summary=(
            f"Proyecto #{project.id}; "
            f"fuentes={copied}"
        ),
        output_summary=(
            "Iniciando integración "
            "final del proyecto."
        ),
    )

    record_activity(
        db=db,
        actor_type="repliker",
        event_type=(
            "project_integration_started"
        ),
        project_id=
            project.id,
        repliker_id=
            target.repliker_id,
        title=(
            "Integración final iniciada"
        ),
        description=(
            "Los entregables de todas "
            "las tareas se están "
            "convirtiendo en un único "
            "proyecto final."
        ),
    )

    db.commit()

    instruction = (
        "Integra este proyecto completo.\n\n"
        "CONTEXTO DEL PROYECTO:\n"
        + json.dumps(
            project_context,
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        + (
            f"Firma de fuentes: "
            f"{source_signature}\n"
        )
        + (
            f"Fuentes copiadas: "
            f"{copied}\n"
        )
        + (
            "Inspecciona los archivos de "
            f"{SOURCE_PREFIX} y construye "
            "la entrega final dentro de "
            f"{DELIVERY_PREFIX}."
        )
    )

    try:
        invoke_with_transient_retry(
            lambda: agent.invoke(
                {
                    "messages": [
                        HumanMessage(
                            content=
                                instruction
                        )
                    ]
                }
            ),
            max_attempts=3,
            base_delay_seconds=1.0,
        )

    except Exception as exc:
        log_tool_execution(
            db=db,
            workspace=target,
            actor_repliker_id=
                target.repliker_id,
            tool_name=(
                "project_integration_agent_run"
            ),
            status="failed",
            input_summary=
                instruction[:2000],
            error_summary=
                str(exc)[:4000],
        )

        db.commit()

        raise ProjectIntegrationError(
            "La integración final falló: "
            + str(exc)
        ) from exc

    delivery = (
        _delivery_artifacts(
            db=db,
            workspace_id=
                target.id,
        )
    )

    candidate_paths = [
        row.relative_path
        for row in delivery
        if row.relative_path
        != INTEGRATION_MARKER_PATH
    ]

    lower_paths = {
        path.lower()
        for path in candidate_paths
    }

    if (
        README_PATH.lower()
        not in lower_paths
    ):
        raise ProjectIntegrationError(
            "El Integrador no creó "
            "README.md en la entrega final."
        )

    if len(candidate_paths) < 2:
        raise ProjectIntegrationError(
            "El Integrador no produjo "
            "un proyecto suficientemente "
            "completo."
        )

    if any(
        path.lower().startswith(
            (
                DELIVERY_PREFIX
                + "tarea-"
            ).lower()
        )
        for path
        in candidate_paths
    ):
        raise ProjectIntegrationError(
            "El Integrador intentó entregar "
            "carpetas separadas por tarea."
        )

    delivery_signature = (
        _delivery_signature(
            delivery
        )
    )

    marker_payload = {
        "status":
            "integrated",
        "project_id":
            project.id,
        "integration_workspace_id":
            target.id,
        "source_signature":
            source_signature,
        "delivery_signature":
            delivery_signature,
        "source_artifacts_count":
            len(rows),
        "delivery_files": [
            path[
                len(
                    DELIVERY_PREFIX
                ):
            ]
            for path
            in sorted(
                candidate_paths
            )
        ],
    }

    write_text_file(
        db=db,
        workspace=target,
        relative_path=
            INTEGRATION_MARKER_PATH,
        content=json.dumps(
            marker_payload,
            ensure_ascii=False,
            indent=2,
        ),
    )

    delivery = (
        _delivery_artifacts(
            db=db,
            workspace_id=
                target.id,
        )
    )

    paths = validate_delivery_paths(
        [
            row.relative_path
            for row
            in delivery
        ]
    )

    log_tool_execution(
        db=db,
        workspace=target,
        actor_repliker_id=
            target.repliker_id,
        tool_name=(
            "project_integration_agent_run"
        ),
        status="completed",
        output_summary=(
            f"Entrega integrada: "
            f"{len(paths)} archivos."
        ),
    )

    record_activity(
        db=db,
        actor_type="repliker",
        event_type=(
            "project_integration_completed"
        ),
        project_id=
            project.id,
        repliker_id=
            target.repliker_id,
        title=(
            "Integración final completada"
        ),
        description=(
            f"Se generó un proyecto "
            f"integrado con "
            f"{len(paths)} archivos."
        ),
    )

    db.commit()

    return {
        "integration_ready":
            True,
        "reused":
            False,
        "integration_workspace_id":
            target.id,
        "source_signature":
            source_signature,
        "files_count":
            len(paths),
        "files":
            paths,
    }


def build_project_integration_context(
    *,
    db: Session,
    project_id: int,
) -> dict:
    workspaces = (
        _project_workspaces(
            db=db,
            project_id=
                project_id,
        )
    )

    if not workspaces:
        return {
            "status":
                "missing",
            "reason":
                "No existen workspaces.",
            "files":
                [],
        }

    marker = None
    marker_workspace = None

    for workspace in reversed(
        workspaces
    ):
        candidate = db.scalar(
            select(
                ExecutionArtifact
            )
            .where(
                ExecutionArtifact
                .workspace_id
                == workspace.id,
                ExecutionArtifact
                .relative_path
                == INTEGRATION_MARKER_PATH,
            )
        )

        if candidate is not None:
            marker = candidate
            marker_workspace = (
                workspace
            )
            break

    if (
        marker is None
        or marker_workspace is None
    ):
        return {
            "status":
                "missing",
            "reason":
                "No existe una entrega "
                "integrada verificable.",
            "files":
                [],
        }

    delivery = (
        _delivery_artifacts(
            db=db,
            workspace_id=
                marker_workspace.id,
        )
    )

    try:
        validate_delivery_paths(
            [
                row.relative_path
                for row
                in delivery
            ]
        )

        marker_data = json.loads(
            read_durable_artifact_bytes(
                db=db,
                workspace=
                    marker_workspace,
                artifact=
                    marker,
            ).decode(
                "utf-8"
            )
        )

        if (
            marker_data.get(
                "delivery_signature"
            )
            != _delivery_signature(
                delivery
            )
        ):
            raise (
                ProjectIntegrationError(
                    "La entrega cambió "
                    "después de integrarse."
                )
            )

    except Exception as exc:
        return {
            "status":
                "invalid",
            "reason":
                str(exc),
            "files":
                [],
        }

    files = []
    consumed = 0
    max_total = 30_000

    for artifact in delivery:
        visible_path = (
            _normalize(
                artifact.relative_path
            )[
                len(
                    DELIVERY_PREFIX
                ):
            ]
        )

        item = {
            "path":
                visible_path,
            "sha256":
                artifact.sha256,
            "size_bytes":
                artifact.size_bytes,
            "text_content":
                None,
        }

        if (
            artifact.relative_path
            != INTEGRATION_MARKER_PATH
            and _is_text_artifact(
                artifact
            )
            and consumed
            < max_total
        ):
            try:
                payload = (
                    read_durable_artifact_bytes(
                        db=db,
                        workspace=
                            marker_workspace,
                        artifact=
                            artifact,
                    )
                )

                text = payload.decode(
                    "utf-8"
                )

                remaining = (
                    max_total
                    - consumed
                )

                clipped = text[
                    :min(
                        6000,
                        remaining,
                    )
                ]

                consumed += len(
                    clipped
                )

                item[
                    "text_content"
                ] = clipped

            except Exception:
                pass

        files.append(
            item
        )

    return {
        "status":
            "ready",
        "workspace_id":
            marker_workspace.id,
        "files_count":
            len(files),
        "files":
            files,
    }


def run_project_integration_stage(
    *,
    db: Session,
    project_id: int,
) -> dict:
    integration = (
        run_project_integration(
            db=db,
            project_id=
                project_id,
        )
    )

    from app.services.project_lifecycle_service import (
        finalize_project_if_ready,
    )

    gate = (
        finalize_project_if_ready(
            db=db,
            project_id=
                project_id,
        )
    )

    return {
        **gate,
        **integration,
    }
