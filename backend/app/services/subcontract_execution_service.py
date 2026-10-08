from __future__ import annotations

import json

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentic.execution_graph import (
    run_execution_graph,
)
from app.agentic.execution_runtime import (
    execution_system_prompt,
)
from app.agentic.execution_tools import (
    build_execution_workspace_tools,
)
from app.agentic.model import get_chat_model
from app.agentic.provider_retry import (
    invoke_with_transient_retry,
    is_transient_provider_error,
)
from app.models.contract import (
    ACTIVE_CONTRACT_STATUSES,
    TaskContract,
)
from app.models.delegation import (
    ACTIVE_SUBCONTRACT_STATUSES,
    DelegatedTask,
    Subcontract,
)
from app.models.execution import (
    ExecutionArtifact,
    ToolExecutionLog,
)
from app.models.repliker import Repliker
from app.services.activity_service import (
    record_activity,
)
from app.services.repliker_behavior_service import (
    load_repliker_behavior_context,
)
from app.services.workspace_service import (
    get_or_create_workspace,
    log_tool_execution,
)


class SubcontractExecutionError(
    ValueError
):
    pass


def _message_to_text(value) -> str:
    if isinstance(value, str):
        return value

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        return str(value)


def _final_response(result) -> str:
    if not isinstance(result, dict):
        return str(result)[:8000]

    messages = result.get(
        "messages",
        [],
    )

    if not messages:
        return ""

    content = getattr(
        messages[-1],
        "content",
        "",
    )

    return _message_to_text(
        content
    )[:8000]


def _snapshot(
    *,
    db: Session,
    workspace_id: int,
) -> dict[int, str]:
    rows = list(
        db.scalars(
            select(
                ExecutionArtifact
            )
            .where(
                ExecutionArtifact.workspace_id
                == workspace_id
            )
        ).all()
    )

    return {
        row.id: row.sha256
        for row in rows
    }


def _changed_artifacts(
    *,
    db: Session,
    workspace_id: int,
    before: dict[int, str],
) -> list[dict]:
    rows = list(
        db.scalars(
            select(
                ExecutionArtifact
            )
            .where(
                ExecutionArtifact.workspace_id
                == workspace_id
            )
            .order_by(
                ExecutionArtifact.id
            )
        ).all()
    )

    changed = []

    for row in rows:
        previous = before.get(
            row.id
        )

        if previous == row.sha256:
            continue

        changed.append(
            {
                "id": row.id,
                "relative_path":
                    row.relative_path,
                "media_type":
                    row.media_type,
                "size_bytes":
                    row.size_bytes,
                "sha256":
                    row.sha256,
            }
        )

    return changed



def _artifact_public(
    row: ExecutionArtifact,
) -> dict:
    return {
        "id":
            row.id,
        "relative_path":
            row.relative_path,
        "media_type":
            row.media_type,
        "size_bytes":
            row.size_bytes,
        "sha256":
            row.sha256,
    }


def _recover_transient_failed_artifacts(
    *,
    db: Session,
    workspace_id: int,
    repliker_id: int,
) -> list[dict]:
    """
    Recupera artifacts producidos por el mismo
    especialista durante un intento delegado
    anterior que termino por un error transitorio
    del proveedor.

    El aislamiento por repliker_id evita que un
    especialista recupere accidentalmente trabajo
    realizado por otro actor dentro del workspace
    compartido.
    """
    failed_logs = list(
        db.scalars(
            select(
                ToolExecutionLog
            )
            .where(
                ToolExecutionLog.workspace_id
                == workspace_id,
                ToolExecutionLog.repliker_id
                == repliker_id,
                ToolExecutionLog.tool_name
                == "subcontract_execution_agent_run",
                ToolExecutionLog.status
                == "failed",
            )
            .order_by(
                ToolExecutionLog.id.desc()
            )
        ).all()
    )

    for failed_log in failed_logs:
        error_text = (
            failed_log.error_summary
            or ""
        )

        if not is_transient_provider_error(
            RuntimeError(
                error_text
            )
        ):
            continue

        running_log_id = db.scalar(
            select(
                ToolExecutionLog.id
            )
            .where(
                ToolExecutionLog.workspace_id
                == workspace_id,
                ToolExecutionLog.repliker_id
                == repliker_id,
                ToolExecutionLog.tool_name
                == "subcontract_execution_agent_run",
                ToolExecutionLog.status
                == "running",
                ToolExecutionLog.id
                < failed_log.id,
            )
            .order_by(
                ToolExecutionLog.id.desc()
            )
            .limit(1)
        )

        if running_log_id is None:
            continue

        written_paths = list(
            db.scalars(
                select(
                    ToolExecutionLog.target_path
                )
                .where(
                    ToolExecutionLog.workspace_id
                    == workspace_id,
                    ToolExecutionLog.repliker_id
                    == repliker_id,
                    ToolExecutionLog.id
                    > running_log_id,
                    ToolExecutionLog.id
                    < failed_log.id,
                    ToolExecutionLog.tool_name
                    == "workspace_write_text",
                    ToolExecutionLog.status
                    == "success",
                    ToolExecutionLog.target_path
                    .is_not(None),
                )
                .order_by(
                    ToolExecutionLog.id
                )
            ).all()
        )

        clean_paths = sorted(
            {
                str(path)
                for path
                in written_paths
                if path
            }
        )

        if not clean_paths:
            continue

        rows = list(
            db.scalars(
                select(
                    ExecutionArtifact
                )
                .where(
                    ExecutionArtifact.workspace_id
                    == workspace_id,
                    ExecutionArtifact.relative_path
                    .in_(clean_paths),
                )
                .order_by(
                    ExecutionArtifact.id
                )
            ).all()
        )

        if rows:
            return [
                _artifact_public(
                    row
                )
                for row
                in rows
            ]

    return []

def _release_subcontractor_if_idle(
    *,
    db: Session,
    repliker_id: int,
) -> None:
    repliker = db.get(
        Repliker,
        repliker_id,
    )

    if repliker is None:
        return

    active_subcontract_id = db.scalar(
        select(Subcontract.id)
        .where(
            Subcontract
            .subcontractor_repliker_id
            == repliker_id,
            Subcontract.status.in_(
                ACTIVE_SUBCONTRACT_STATUSES
            ),
        )
        .order_by(
            Subcontract.id
        )
        .limit(1)
    )

    if active_subcontract_id is not None:
        return

    active_contract_id = db.scalar(
        select(TaskContract.id)
        .where(
            TaskContract.repliker_id
            == repliker_id,
            TaskContract.status.in_(
                ACTIVE_CONTRACT_STATUSES
            ),
        )
        .order_by(
            TaskContract.id
        )
        .limit(1)
    )

    if active_contract_id is not None:
        return

    if repliker.status == "subcontracted":
        repliker.status = "available"
        db.flush()


def _execute_subcontract_once(
    *,
    db: Session,
    subcontract_id: int,
    state: dict,
) -> dict:

    subcontract = db.get(
        Subcontract,
        subcontract_id,
    )

    if subcontract is None:
        raise SubcontractExecutionError(
            "Subcontrato no encontrado."
        )

    if subcontract.status == "completed":
        return {
            "contract_id":
                subcontract.root_contract_id,
            "project_id":
                subcontract.project_id,
            "task_id":
                subcontract.delegated_task_id,
            "repliker_id":
                subcontract
                .subcontractor_repliker_id,
            "status": "completed",
            "artifact_count": 0,
            "artifacts": [],
            "response_text": (
                "El subcontrato ya fue "
                "completado anteriormente."
            ),
            "error": "",
            "trace": [
                *state.get(
                    "trace",
                    [],
                ),
                (
                    f"Subcontrato "
                    f"#{subcontract.id} "
                    "ya completado."
                ),
            ],
        }

    if (
        subcontract.status
        not in ACTIVE_SUBCONTRACT_STATUSES
    ):
        raise SubcontractExecutionError(
            "El subcontrato no está activo "
            "ni adjudicado."
        )

    contract = db.get(
        TaskContract,
        subcontract.root_contract_id,
    )

    if contract is None:
        raise SubcontractExecutionError(
            "Contrato principal no encontrado."
        )

    if (
        contract.status
        not in ACTIVE_CONTRACT_STATUSES
    ):
        raise SubcontractExecutionError(
            "El contrato principal no está "
            "en estado ejecutable."
        )

    delegated_task = db.get(
        DelegatedTask,
        subcontract.delegated_task_id,
    )

    if delegated_task is None:
        raise SubcontractExecutionError(
            "Tarea delegada no encontrada."
        )

    repliker = db.get(
        Repliker,
        subcontract
        .subcontractor_repliker_id,
    )

    if repliker is None:
        raise SubcontractExecutionError(
            "Especialista delegado "
            "no encontrado."
        )

    if not repliker.is_active:
        raise SubcontractExecutionError(
            "El especialista delegado "
            "está inactivo."
        )

    workspace = get_or_create_workspace(
        db=db,
        contract=contract,
    )

    db.commit()
    db.refresh(workspace)

    carryover_artifacts = (
        _recover_transient_failed_artifacts(
            db=db,
            workspace_id=workspace.id,
            repliker_id=repliker.id,
        )
    )

    before = _snapshot(
        db=db,
        workspace_id=workspace.id,
    )

    instruction = str(
        state.get(
            "instruction",
            "",
        )
    ).strip()

    if not instruction:
        instruction = (
            f"Ejecuta la subtarea delegada "
            f"'{delegated_task.title}'. "
            f"{delegated_task.description}\n\n"
            f"Tu especialidad obligatoria es "
            f"{delegated_task.required_skill_name} "
            f"con nivel mínimo "
            f"{delegated_task.minimum_skill_level}. "
            "Inspecciona primero los archivos "
            "existentes del workspace del líder. "
            "Realiza cambios reales y verificables "
            "que el líder pueda integrar."
        )

    behavior_context = (
        load_repliker_behavior_context(
            db=db,
            repliker_id=repliker.id,
        )
    )

    tools = (
        build_execution_workspace_tools(
            db=db,
            workspace=workspace,
            actor_repliker_id=
                repliker.id,
        )
    )

    system_prompt = (
        execution_system_prompt(
            contract=contract,
            repliker=repliker,
            task=delegated_task,
            behavior_context=
                behavior_context,
            developer_context=None,
        )
        + "\n\nAUTORIZACIÓN DE DELEGACIÓN\n"
        + (
            f"Subcontrato #{subcontract.id}. "
            f"Trabajas como especialista "
            f"delegado por el Repliker "
            f"#{subcontract.delegator_repliker_id}. "
            "Tienes autorización para trabajar "
            "dentro del workspace del contrato "
            "principal exclusivamente para la "
            "subtarea delegada."
        )
    )

    agent = create_agent(
        model=get_chat_model(),
        tools=tools,
        system_prompt=system_prompt,
    )

    record_activity(
        db=db,
        actor_type="repliker",
        event_type=
            "delegated_task_started",
        project_id=
            subcontract.project_id,
        task_id=
            subcontract.parent_task_id,
        repliker_id=repliker.id,
        title=(
            "Especialista delegado inició "
            "la ejecución"
        ),
        description=(
            f"{repliker.name} inició "
            f"el subcontrato "
            f"#{subcontract.id}."
        ),
    )

    log_tool_execution(
        db=db,
        workspace=workspace,
        actor_repliker_id=
            repliker.id,
        tool_name=(
            "subcontract_execution_agent_run"
        ),
        status="running",
        input_summary=
            instruction[:2000],
        output_summary=(
            f"Subcontrato "
            f"#{subcontract.id} "
            "entregado al especialista."
        ),
    )

    db.commit()

    try:
        result = invoke_with_transient_retry(
            lambda: agent.invoke(
                {
                    "messages": [
                        HumanMessage(
                            content=instruction
                        )
                    ]
                }
            ),
            max_attempts=3,
            base_delay_seconds=1.0,
        )

    except Exception as exc:
        error = str(exc)

        log_tool_execution(
            db=db,
            workspace=workspace,
            actor_repliker_id=
                repliker.id,
            tool_name=(
                "subcontract_execution_agent_run"
            ),
            status="failed",
            input_summary=
                instruction[:2000],
            output_summary="",
            error_summary=
                error[:4000],
        )

        record_activity(
            db=db,
            actor_type="repliker",
            event_type=(
                "delegated_task_failed"
            ),
            project_id=
                subcontract.project_id,
            task_id=
                subcontract.parent_task_id,
            repliker_id=repliker.id,
            title=(
                "Ejecución delegada fallida"
            ),
            description=
                error[:3000],
        )

        db.commit()

        return {
            "contract_id":
                contract.id,
            "project_id":
                subcontract.project_id,
            "task_id":
                delegated_task.id,
            "repliker_id":
                repliker.id,
            "workspace_id":
                workspace.id,
            "status": "failed",
            "response_text": "",
            "error": error,
            "artifact_count": 0,
            "artifacts": [],
            "trace": [
                *state.get(
                    "trace",
                    [],
                ),
                (
                    f"El subcontrato "
                    f"#{subcontract.id} "
                    "falló durante ejecución."
                ),
            ],
        }

    response_text = (
        _final_response(
            result
        )
    )

    artifacts = (
        _changed_artifacts(
            db=db,
            workspace_id=workspace.id,
            before=before,
        )
    )

    artifact_map = {
        int(artifact["id"]):
            artifact
        for artifact in [
            *carryover_artifacts,
            *artifacts,
        ]
    }

    artifacts = [
        artifact_map[
            artifact_id
        ]
        for artifact_id
        in sorted(
            artifact_map
        )
    ]

    artifact_count = len(
        artifacts
    )

    status = (
        "completed"
        if artifact_count > 0
        else "needs_artifact"
    )

    if status == "completed":
        subcontract.status = "completed"
        delegated_task.status = "completed"

        db.flush()

        _release_subcontractor_if_idle(
            db=db,
            repliker_id=repliker.id,
        )

        record_activity(
            db=db,
            actor_type="repliker",
            event_type=(
                "delegated_task_completed"
            ),
            project_id=
                subcontract.project_id,
            task_id=
                subcontract.parent_task_id,
            repliker_id=repliker.id,
            title=(
                "Especialista delegado "
                "completó su trabajo"
            ),
            description=(
                f"{repliker.name} produjo "
                f"{artifact_count} artefacto(s) "
                "reales dentro del workspace "
                "del contrato principal."
            ),
        )

    log_tool_execution(
        db=db,
        workspace=workspace,
        actor_repliker_id=
            repliker.id,
        tool_name=(
            "subcontract_execution_agent_run"
        ),
        status=status,
        input_summary=
            instruction[:2000],
        output_summary=(
            f"{artifact_count} "
            "artefacto(s) producidos "
            "o modificados. "
            + response_text[:3000]
        ),
    )

    db.commit()

    return {
        "contract_id":
            contract.id,
        "project_id":
            subcontract.project_id,
        "task_id":
            delegated_task.id,
        "repliker_id":
            repliker.id,
        "workspace_id":
            workspace.id,
        "status":
            status,
        "response_text":
            response_text,
        "error": "",
        "artifact_count":
            artifact_count,
        "artifacts":
            artifacts,
        "trace": [
            *state.get(
                "trace",
                [],
            ),
            (
                f"Subcontrato "
                f"#{subcontract.id} ejecutado "
                f"por {repliker.name}."
            ),
        ],
    }


def run_subcontract_execution(
    *,
    db: Session,
    subcontract_id: int,
    instruction: str = "",
) -> dict:

    subcontract = db.get(
        Subcontract,
        subcontract_id,
    )

    if subcontract is None:
        raise SubcontractExecutionError(
            "Subcontrato no encontrado."
        )

    root_contract_id = (
        subcontract.root_contract_id
    )

    def executor(state):
        return _execute_subcontract_once(
            db=db,
            subcontract_id=
                subcontract_id,
            state=state,
        )

    return run_execution_graph(
        contract_id=root_contract_id,
        instruction=instruction,
        executor=executor,
    )
