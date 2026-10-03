import json

from langchain.agents import (
    create_agent,
)
from langchain.agents.structured_output import (
    ToolStrategy,
)

from app.agentic.model import (
    get_chat_model,
)
from app.agentic.tool_catalog import (
    build_market_tools,
    resolve_market_tool_names,
)
from app.schemas.market import (
    AgentDecisionAI,
)


MARKET_AGENT_SYSTEM_PROMPT = """
Eres un Repliker autonomo dentro de Repliker Economy.

Funcionas como un agente LangChain independiente.

Todos los textos que puedan mostrarse al usuario,
especialmente message, deben estar escritos en español.
La palabra Repliker puede conservarse tal cual.

NO eres R00.

Tu identidad, especialidad, habilidades, reputacion,
experiencia y herramientas son exclusivamente las que
el sistema te proporciona.

No puedes inventar:

- habilidades,
- experiencia,
- herramientas,
- permisos,
- informacion del proyecto.

Antes de decidir si competir por una tarea debes utilizar
las herramientas LangChain disponibles para consultar:

1. tu perfil real,
2. la tarea,
3. el proyecto,
4. tus permisos,
5. tu cobertura real de habilidades.

Tu decision final solo puede ser:

- bid
- pass

REGLAS ECONOMICAS:

1. No debes ofertar por todas las tareas.
2. Evalua honestamente si puedes completar el trabajo.
3. Considera requisitos, complejidad, criterios de aceptacion
   y presupuesto.
4. Si tus capacidades son claramente insuficientes,
   debes elegir pass.
5. Si eliges bid, propone un precio razonable.
6. No estas obligado a utilizar todo el presupuesto.
7. Tu precio nunca puede superar el presupuesto maximo.
8. confidence_score representa confianza real.
9. No infles artificialmente confidence_score.
10. estimated_minutes debe representar esfuerzo razonable.
11. No asumas que posteriormente otro agente arreglara
    un trabajo que no puedes realizar.
12. La posibilidad futura de delegar no justifica aceptar
    una tarea para la que eres un contratista principal
    inadecuado.
13. No expongas razonamiento privado paso a paso.
14. reasoning debe ser una explicacion operativa breve.

Si eliges pass:

- amount_cents = null
- estimated_minutes = null

Si eliges bid:

- amount_cents debe contener un valor valido
- estimated_minutes debe contener un valor valido
""".strip()


def build_market_agent(
    *,
    repliker_data: dict,
    task_data: dict,
    project_data: dict,
    allowed_tool_names:
        tuple[str, ...]
        | None = None,
):
    if allowed_tool_names is None:
        allowed_tool_names = (
            resolve_market_tool_names(
                repliker_data
            )
        )

    tools = build_market_tools(
        repliker_data=
            repliker_data,
        task_data=
            task_data,
        project_data=
            project_data,
        allowed_tool_names=
            allowed_tool_names,
    )

    repliker_id = (
        repliker_data.get(
            "id",
            "unknown",
        )
    )

    return create_agent(
        model=get_chat_model(
            temperature=0.1
        ),
        tools=tools,
        system_prompt=
            MARKET_AGENT_SYSTEM_PROMPT,
        response_format=
            ToolStrategy(
                AgentDecisionAI
            ),
        name=(
            f"repliker_{repliker_id}_market"
        ),
    )


def run_market_agent(
    *,
    repliker_data: dict,
    task_data: dict,
    project_data: dict,
    allowed_tool_names:
        tuple[str, ...]
        | None = None,
) -> AgentDecisionAI:
    agent = build_market_agent(
        repliker_data=
            repliker_data,
        task_data=
            task_data,
        project_data=
            project_data,
        allowed_tool_names=
            allowed_tool_names,
    )

    context_summary = {
        "repliker_id":
            repliker_data.get(
                "id"
            ),
        "repliker_name":
            repliker_data.get(
                "name"
            ),
        "task_id":
            task_data.get(
                "id"
            ),
        "project_id":
            project_data.get(
                "id"
            ),
    }

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Evalua autonomamente esta "
                        "oportunidad economica.\n\n"
                        "Antes de decidir debes "
                        "utilizar las herramientas "
                        "disponibles para consultar "
                        "los datos reales.\n\n"
                        "Contexto minimo:\n"
                        + json.dumps(
                            context_summary,
                            ensure_ascii=False,
                            indent=2,
                        )
                    ),
                }
            ]
        }
    )

    structured = result.get(
        "structured_response"
    )

    if structured is None:
        raise RuntimeError(
            "El agente LangChain termino "
            "sin generar AgentDecisionAI."
        )

    if isinstance(
        structured,
        AgentDecisionAI,
    ):
        return structured

    return (
        AgentDecisionAI
        .model_validate(
            structured
        )
    )
