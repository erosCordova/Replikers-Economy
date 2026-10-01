from __future__ import annotations

from dataclasses import dataclass

from langchain.agents import (
    create_agent,
)
from langchain_core.tools import (
    BaseTool,
)
from sqlalchemy.orm import Session

from app.agentic.execution_tools import (
    build_execution_workspace_tools,
)
from app.agentic.model import (
    get_chat_model,
)
from app.models.contract import (
    TaskContract,
)
from app.models.execution import (
    ExecutionWorkspace,
)
from app.models.repliker import (
    Repliker,
)
from app.models.task import (
    Task,
)


@dataclass
class ExecutionAgentRuntime:
    contract_id: int

    project_id: int

    task_id: int

    repliker_id: int

    workspace_id: int

    tools: list[BaseTool]

    agent: object


def execution_system_prompt(
    *,
    contract: TaskContract,
    repliker: Repliker,
    task: Task,
) -> str:
    return f"""
Eres {repliker.name}, un Repliker autonomo
especializado en {repliker.specialty}.

Estas ejecutando una tarea real dentro de
Repliker Economy.

CONTRATO
- contract_id: {contract.id}
- project_id: {contract.project_id}
- task_id: {task.id}
- repliker_id: {repliker.id}

TAREA
Titulo: {task.title}

Descripcion:
{task.description}

REGLAS DE EJECUCION

1. Trabaja exclusivamente dentro del workspace
   que te fue asignado.

2. Nunca inventes que creaste o modificaste
   archivos. Usa siempre las tools disponibles.

3. Antes de modificar un proyecto existente,
   inspecciona primero sus archivos.

4. Lee los archivos relevantes antes de
   reemplazarlos.

5. Cada escritura debe contener el archivo
   completo que deseas dejar como resultado.

6. No tienes permiso para acceder al filesystem
   externo, secretos, variables de entorno,
   procesos del sistema ni comandos arbitrarios.

7. No tienes shell, Python, npm ni acceso de red
   en esta etapa.

8. Si una operacion es rechazada por el Policy
   Engine, no intentes evadir la restriccion.

9. Mantiene los cambios limitados al objetivo
   concreto de la tarea.

10. La existencia de una respuesta del modelo
    no significa que el trabajo este terminado:
    los entregables reales son los artifacts
    escritos mediante tools.
""".strip()


def build_execution_repliker_agent(
    *,
    db: Session,
    contract: TaskContract,
    repliker: Repliker,
    task: Task,
    workspace: ExecutionWorkspace,
) -> ExecutionAgentRuntime:
    if (
        contract.repliker_id
        != repliker.id
    ):
        raise ValueError(
            "El Repliker no corresponde "
            "al contrato."
        )

    if (
        contract.task_id
        != task.id
    ):
        raise ValueError(
            "La tarea no corresponde "
            "al contrato."
        )

    if (
        workspace.contract_id
        != contract.id
    ):
        raise ValueError(
            "El workspace no corresponde "
            "al contrato."
        )

    if (
        workspace.repliker_id
        != repliker.id
    ):
        raise ValueError(
            "El workspace no pertenece "
            "al Repliker contratado."
        )

    tools = (
        build_execution_workspace_tools(
            db=db,
            workspace=workspace,
        )
    )

    model = get_chat_model()

    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=(
            execution_system_prompt(
                contract=contract,
                repliker=repliker,
                task=task,
            )
        ),
    )

    return ExecutionAgentRuntime(
        contract_id=
            contract.id,
        project_id=
            contract.project_id,
        task_id=
            task.id,
        repliker_id=
            repliker.id,
        workspace_id=
            workspace.id,
        tools=
            tools,
        agent=
            agent,
    )
