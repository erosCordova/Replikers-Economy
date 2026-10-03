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


from app.services.repliker_behavior_service import (
    behavior_prompt_section,
)
from app.services.repliker_developer_service import (
    developer_prompt_section,
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
    behavior_context:
        dict | None = None,
    developer_context:
        dict | None = None,
) -> str:
    base_prompt = f"""
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

2. Nunca inventes que creaste, modificaste o
   ejecutaste archivos. Usa siempre las tools
   disponibles.

3. Antes de modificar un proyecto existente,
   inspecciona primero sus archivos.

4. Lee los archivos relevantes antes de
   reemplazarlos.

5. Cada escritura debe contener el archivo
   completo que deseas dejar como resultado.

6. No tienes permiso para acceder al filesystem
   externo, secretos, variables de entorno,
   procesos del sistema ni comandos arbitrarios.

7. No tienes shell ni acceso directo a Docker.
   Python solo puede ejecutarse mediante la tool
   run_python sobre un archivo .py previamente
   creado dentro del workspace.

8. run_python se ejecuta en un sandbox aislado
   sin red, con filesystem raiz de solo lectura,
   usuario sin privilegios y limites de recursos.

9. Si una operacion es rechazada por el Policy
   Engine, no intentes evadir la restriccion.

10. Cuando el entregable incluya Python, utiliza
    run_python cuando sea necesario para comprobar
    que el archivo realmente ejecuta.

11. Si run_python devuelve exit_code distinto de
    cero o timed_out=true, no declares la ejecucion
    como satisfactoria. Corrige el archivo y vuelve
    a probar cuando corresponda.

12. Mantiene los cambios limitados al objetivo
    concreto de la tarea.

13. Una respuesta del modelo no significa que el
    trabajo este terminado. Los entregables reales
    son los artifacts escritos mediante tools y
    las ejecuciones registradas son evidencia del
    comportamiento real.

14. La verificacion formal de aceptacion pertenece
    al sistema de QA. No falsifiques ni anticipes
    un resultado de QA.
""".strip()

    return (
        base_prompt
        + behavior_prompt_section(
            behavior_context
        )
        + developer_prompt_section(
            developer_context
        )
    )


def build_execution_repliker_agent(
    *,
    db: Session,
    contract: TaskContract,
    repliker: Repliker,
    task: Task,
    workspace: ExecutionWorkspace,
    behavior_context:
        dict | None = None,
    developer_context:
        dict | None = None,
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
                behavior_context=
                    behavior_context,
                developer_context=
                    developer_context,
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
