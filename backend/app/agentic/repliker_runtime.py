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
from app.services.repliker_behavior_service import (
    behavior_prompt_section,
)

from app.schemas.market import (
    AgentDecisionAI,
    SpecialistOfferDecisionAI,
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
11. No asumas que otro agente corregira posteriormente
    un trabajo defectuoso que hayas entregado.
12. Si la tarea indica delegation_available=true y tu
    cobertura tecnica alcanza minimum_lead_coverage,
    la plataforma puede asignar capacidades faltantes
    concretas a especialistas despues de la contratacion.
13. En ese caso puedes considerar bid si eres un
    contratista principal razonable para dirigir e integrar
    el trabajo. No debes inventar la habilidad faltante:
    reconocela claramente en reasoning.
14. Una brecha puntual delegable no es por si sola motivo
    obligatorio de pass cuando cumples el umbral de
    contratista principal.
15. Elige pass si tu cobertura esta por debajo del umbral,
    tu especialidad principal es incompatible, el
    presupuesto es inviable o la brecha te impide dirigir
    e integrar el trabajo incluso usando delegacion.
16. No expongas razonamiento privado paso a paso.
17. reasoning debe ser una explicacion operativa breve.

Si eliges pass:

- amount_cents = null
- estimated_minutes = null

Si eliges bid:

- amount_cents debe contener un valor valido
- estimated_minutes debe contener un valor valido
""".strip()



def _personalized_system_prompt(
    *,
    base_prompt: str,
    repliker_data: dict,
) -> str:
    return (
        base_prompt
        + behavior_prompt_section(
            repliker_data.get(
                "studio_behavior"
            )
        )
    )


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
        system_prompt=(
            _personalized_system_prompt(
                base_prompt=
                    MARKET_AGENT_SYSTEM_PROMPT,
                repliker_data=
                    repliker_data,
            )
        ),
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


SPECIALIST_OFFER_SYSTEM_PROMPT = """
Eres un Repliker autónomo dentro de Repliker Economy.

Has recibido una propuesta de Iris para ocupar una
especialidad necesaria dentro de un proyecto.

Debes evaluar la propuesta de forma independiente.

Tu decisión final solo puede ser:

- accept
- reject

REGLAS:

1. Decide según tu identidad, especialidad,
   experiencia, habilidades y disponibilidad.
2. No aceptes un puesto que no corresponda
   realmente con tu perfil.
3. No estás obligado a aceptar.
4. Esta decisión no es una oferta económica
   de una tarea y no debes inventar precios.
5. confidence_score representa tu confianza
   real para asumir el puesto.
6. message es un mensaje operativo que podrá
   mostrarse al resto del proyecto.
7. Todo texto visible debe estar escrito
   completamente en español.
8. La palabra Repliker puede conservarse.
9. No expongas razonamiento privado paso a paso.
10. reasoning debe ser únicamente una explicación
    operativa breve para uso interno.
""".strip()


def run_specialist_offer_agent(
    *,
    repliker_data: dict,
    requirement_data: dict,
    project_data: dict,
) -> SpecialistOfferDecisionAI:
    repliker_id = (
        repliker_data.get(
            "id",
            "unknown",
        )
    )

    agent = create_agent(
        model=get_chat_model(
            temperature=0.1
        ),
        tools=[],
        system_prompt=(
            _personalized_system_prompt(
                base_prompt=
                    SPECIALIST_OFFER_SYSTEM_PROMPT,
                repliker_data=
                    repliker_data,
            )
        ),
        response_format=(
            ToolStrategy(
                SpecialistOfferDecisionAI
            )
        ),
        name=(
            f"repliker_{repliker_id}_"
            "specialist_offer"
        ),
    )

    context = {
        "repliker":
            repliker_data,
        "puesto":
            requirement_data,
        "proyecto":
            project_data,
    }

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Iris te ha enviado una "
                        "propuesta para participar "
                        "en este proyecto.\n\n"
                        "Evalúa de forma autónoma "
                        "si deseas aceptar el puesto.\n\n"
                        "Contexto:\n"
                        + json.dumps(
                            context,
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
            "El Repliker terminó sin generar "
            "una decisión de puesto."
        )

    if isinstance(
        structured,
        SpecialistOfferDecisionAI,
    ):
        return structured

    return (
        SpecialistOfferDecisionAI
        .model_validate(
            structured
        )
    )
