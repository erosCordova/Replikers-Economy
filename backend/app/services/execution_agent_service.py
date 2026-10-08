from __future__ import annotations

import json

from langchain_core.messages import (
    HumanMessage,
)
from sqlalchemy import (
    select,
)
from sqlalchemy.orm import Session

from app.agentic.execution_graph import (
    run_execution_graph,
)
from app.agentic.execution_runtime import (
    build_execution_repliker_agent,
)
from app.agentic.execution_state import (
    ContractExecutionState,
)
from app.agentic.provider_retry import (
    invoke_with_transient_retry,
)
from app.models.contract import (
    ACTIVE_CONTRACT_STATUSES,
    TaskContract,
)
from app.models.delegation import (
    Subcontract,
)
from app.models.execution import (
    ExecutionArtifact,
    ToolExecutionLog,
)
from app.models.repliker import (
    Repliker,
)
from app.models.task import (
    Task,
)
from app.services.repliker_behavior_service import (
    load_repliker_behavior_context,
)
from app.services.repliker_developer_service import (
    materialize_developer_module,
)
from app.services.workspace_service import (
    get_or_create_workspace,
    log_tool_execution,
)


class ContractExecutionError(
    ValueError
):
    pass


def _message_content_to_text(
    value,
) -> str:
    if isinstance(
        value,
        str,
    ):
        return value

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )

    except Exception:
        return str(
            value
        )


def _final_response_text(
    result,
) -> str:
    if not isinstance(
        result,
        dict,
    ):
        return str(
            result
        )[:8000]

    messages = result.get(
        "messages",
        [],
    )

    if not messages:
        return ""

    last = messages[-1]

    content = getattr(
        last,
        "content",
        "",
    )

    return (
        _message_content_to_text(
            content
        )[:8000]
    )


def _artifact_snapshot(
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
                ExecutionArtifact
                .workspace_id
                == workspace_id
            )
        ).all()
    )

    return {
        row.id:
            row.sha256
        for row
        in rows
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
                ExecutionArtifact
                .workspace_id
                == workspace_id
            )
            .order_by(
                ExecutionArtifact.id
            )
        ).all()
    )

    changed = []

    for row in rows:
        previous_hash = (
            before.get(
                row.id
            )
        )

        if (
            previous_hash
            == row.sha256
        ):
            continue

        changed.append(
            {
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
        )

    return changed



def _delegated_integration_verified(
    *,
    db: Session,
    contract_id: int,
    workspace_id: int,
    baseline_artifact_count: int,
    principal_running_log_id: int,
    principal_repliker_id: int,
) -> bool:
    """
    Permite completar una integracion sin
    reescritura solamente cuando:

    1. existen artifacts reales;
    2. existe un subcontrato completado;
    3. existe una ejecucion delegada completada
       anterior al intento principal actual;
    4. el ID recibido corresponde exactamente
       al intento principal actual;
    5. el Repliker principal leyo artifacts
       dentro de ese intento.

    Si existe otro intento principal posterior,
    sus lecturas no pueden validar este intento.
    """
    if baseline_artifact_count <= 0:
        return False

    if principal_running_log_id <= 0:
        return False

    completed_subcontract_id = db.scalar(
        select(
            Subcontract.id
        )
        .where(
            Subcontract.root_contract_id
            == contract_id,
            Subcontract.status
            == "completed",
        )
        .order_by(
            Subcontract.id.desc()
        )
        .limit(1)
    )

    if completed_subcontract_id is None:
        return False

    delegated_completed_log_id = db.scalar(
        select(
            ToolExecutionLog.id
        )
        .where(
            ToolExecutionLog.workspace_id
            == workspace_id,
            ToolExecutionLog.tool_name
            == "subcontract_execution_agent_run",
            ToolExecutionLog.status
            == "completed",
            ToolExecutionLog.id
            < principal_running_log_id,
        )
        .order_by(
            ToolExecutionLog.id.desc()
        )
        .limit(1)
    )

    if delegated_completed_log_id is None:
        return False

    principal_log_id = db.scalar(
        select(
            ToolExecutionLog.id
        )
        .where(
            ToolExecutionLog.id
            == principal_running_log_id,
            ToolExecutionLog.workspace_id
            == workspace_id,
            ToolExecutionLog.repliker_id
            == principal_repliker_id,
            ToolExecutionLog.tool_name
            == "execution_agent_run",
            ToolExecutionLog.status
            == "running",
        )
        .limit(1)
    )

    if principal_log_id is None:
        return False

    next_principal_running_log_id = db.scalar(
        select(
            ToolExecutionLog.id
        )
        .where(
            ToolExecutionLog.workspace_id
            == workspace_id,
            ToolExecutionLog.repliker_id
            == principal_repliker_id,
            ToolExecutionLog.tool_name
            == "execution_agent_run",
            ToolExecutionLog.status
            == "running",
            ToolExecutionLog.id
            > principal_running_log_id,
        )
        .order_by(
            ToolExecutionLog.id
        )
        .limit(1)
    )

    read_filters = [
        ToolExecutionLog.workspace_id
        == workspace_id,

        ToolExecutionLog.repliker_id
        == principal_repliker_id,

        ToolExecutionLog.tool_name
        == "workspace_read_text",

        ToolExecutionLog.status
        == "success",

        ToolExecutionLog.id
        > principal_running_log_id,
    ]

    if next_principal_running_log_id is not None:
        read_filters.append(
            ToolExecutionLog.id
            < next_principal_running_log_id
        )

    principal_read_log_id = db.scalar(
        select(
            ToolExecutionLog.id
        )
        .where(
            *read_filters
        )
        .order_by(
            ToolExecutionLog.id.desc()
        )
        .limit(1)
    )

    return (
        principal_read_log_id
        is not None
    )

def execute_contract_once(
    *,
    db: Session,
    state: ContractExecutionState,
) -> dict:
    contract_id = int(
        state[
            "contract_id"
        ]
    )

    contract = db.get(
        TaskContract,
        contract_id,
    )

    if contract is None:
        raise ContractExecutionError(
            "Contrato no encontrado."
        )

    if (
        contract.status
        not in ACTIVE_CONTRACT_STATUSES
    ):
        raise ContractExecutionError(
            "El contrato no esta activo "
            "ni adjudicado."
        )

    task = db.get(
        Task,
        contract.task_id,
    )

    if task is None:
        raise ContractExecutionError(
            "La tarea del contrato "
            "no existe."
        )

    repliker = db.get(
        Repliker,
        contract.repliker_id,
    )

    if repliker is None:
        raise ContractExecutionError(
            "El Repliker contratado "
            "no existe."
        )

    if not repliker.is_active:
        raise ContractExecutionError(
            "El Repliker contratado "
            "esta inactivo."
        )

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

    developer_context = (
        materialize_developer_module(
            db=db,
            workspace=workspace,
            repliker_id=
                repliker.id,
        )
    )

    # El modulo queda incorporado antes
    # de tomar la linea base, por lo que
    # no cuenta como entregable de la tarea.
    db.commit()

    baseline = (
        _artifact_snapshot(
            db=db,
            workspace_id=
                workspace.id,
        )
    )

    instruction = str(
        state.get(
            "instruction",
            "",
        )
    ).strip()

    if not instruction:
        instruction = (
            task.description
            or task.title
        )

    behavior_context = (
        load_repliker_behavior_context(
            db=db,
            repliker_id=
                repliker.id,
        )
    )

    trace = [
        *state.get(
            "trace",
            [],
        ),
        (
            f"Workspace {workspace.root_ref} "
            "asignado al Repliker "
            f"{repliker.name}."
        ),
        (
            "LangChain preparo el agente "
            "con tools restringidas "
            "al workspace."
        ),
    ]

    principal_run_log = log_tool_execution(
        db=db,
        workspace=
            workspace,
        actor_repliker_id=
            repliker.id,
        tool_name=
            "execution_agent_run",
        status=
            "running",
        input_summary=(
            instruction[:2000]
        ),
        output_summary=(
            "LangGraph entrego la tarea "
            "al Repliker contratado."
        ),
    )

    db.flush()

    if principal_run_log.id is None:
        raise ContractExecutionError(
            "No se pudo identificar "
            "el intento principal actual."
        )

    principal_running_log_id = int(
        principal_run_log.id
    )

    db.commit()

    try:
        runtime = (
            build_execution_repliker_agent(
                db=db,
                contract=contract,
                repliker=repliker,
                task=task,
                workspace=workspace,
                behavior_context=
                    behavior_context,
                developer_context=
                    developer_context,
            )
        )

        # El contexto del Studio ya esta
        # materializado como datos simples.
        # Cerramos cualquier transaccion que
        # pudiera haberse abierto al preparar
        # el runtime antes de esperar a la IA.
        if db.in_transaction():
            db.commit()

        result = (
            invoke_with_transient_retry(
                lambda: runtime.agent.invoke(
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
        )

        response_text = (
            _final_response_text(
                result
            )
        )

    except Exception as exc:
        log_tool_execution(
            db=db,
            workspace=
                workspace,
            tool_name=
                "execution_agent_run",
            status=
                "failed",
            input_summary=(
                instruction[:2000]
            ),
            error_summary=(
                str(exc)[:4000]
            ),
        )

        db.commit()

        return {
            "project_id":
                contract.project_id,
            "task_id":
                task.id,
            "repliker_id":
                repliker.id,
            "workspace_id":
                workspace.id,
            "status":
                "failed",
            "response_text":
                "",
            "error":
                str(exc)[:4000],
            "artifact_count":
                0,
            "artifacts":
                [],
            "trace": [
                *trace,
                (
                    "El agente LangChain "
                    "no completo la ejecucion."
                ),
            ],
        }

    artifacts = (
        _changed_artifacts(
            db=db,
            workspace_id=
                workspace.id,
            before=
                baseline,
        )
    )

    artifact_count = len(
        artifacts
    )

    integration_verified = False

    if artifact_count <= 0:
        integration_verified = (
            _delegated_integration_verified(
                db=db,
                contract_id=contract.id,
                workspace_id=workspace.id,
                baseline_artifact_count=
                    len(baseline),
                principal_running_log_id=
                    principal_running_log_id,
                principal_repliker_id=
                    repliker.id,
            )
        )

    status = (
        "completed"
        if (
            artifact_count > 0
            or integration_verified
        )
        else "needs_artifact"
    )

    log_tool_execution(
        db=db,
        workspace=
            workspace,
        tool_name=
            "execution_agent_run",
        status=
            status,
        input_summary=(
            instruction[:2000]
        ),
        output_summary=(
            (
                f"{artifact_count} "
                "artifact(s) producidos "
                "o modificados. "
            )
            + response_text[:3000]
        ),
    )

    db.commit()

    return {
        "project_id":
            contract.project_id,
        "task_id":
            task.id,
        "repliker_id":
            repliker.id,
        "workspace_id":
            workspace.id,
        "status":
            status,
        "response_text":
            response_text,
        "error":
            "",
        "artifact_count":
            artifact_count,
        "artifacts":
            artifacts,
        "integration_verified":
            integration_verified,
        "trace": [
            *trace,
            (
                "El agente LangChain "
                "finalizo su turno."
            ),
        ],
    }


def run_contract_execution(
    *,
    db: Session,
    contract_id: int,
    instruction: str = "",
) -> ContractExecutionState:
    def executor(
        state:
            ContractExecutionState,
    ) -> dict:
        return execute_contract_once(
            db=db,
            state=state,
        )

    return run_execution_graph(
        contract_id=
            contract_id,
        instruction=
            instruction,
        executor=
            executor,
    )
