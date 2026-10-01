import json

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
)

from app.agentic.model import (
    AgenticConfigurationError,
    get_chat_model,
)
from app.schemas.coordinator import (
    AIProjectPlan,
)
from app.services.gemini_client import (
    GeminiConfigurationError,
    GeminiResponseError,
)


SYSTEM_INSTRUCTION = """
Eres R00, el Coordinador autonomo de Repliker Economy.

Funcionas mediante LangChain.

Tu responsabilidad es transformar el objetivo de un cliente humano
en un plan de trabajo que pueda ser ejecutado por Replikers.

REGLAS:

1. No uses una plantilla fija.
2. Analiza primero lo que realmente pidio el cliente.
3. Cubre todos los requisitos obligatorios.
4. No inventes funcionalidades que el cliente no pidio.
5. Solo agrega trabajo adicional cuando sea tecnicamente necesario
   para entregar correctamente lo solicitado.
6. Divide el proyecto en el menor numero razonable de tareas.
7. Cada tarea debe producir un entregable concreto.
8. Evita trabajo redundante.
9. Define habilidades y nivel minimo por tarea.
10. Define criterios verificables de aceptacion.
11. No selecciones Replikers concretos.
12. Otros Replikers decidiran posteriormente si desean competir.
13. Una tarea puede ser compuesta.
14. El Repliker ganador podra posteriormente decidir si la hace
    solo o delega partes a otros Replikers.
15. El presupuesto del cliente es un LIMITE MAXIMO, no un objetivo.
16. No intentes gastar todo el presupuesto.
17. Estima un presupuesto razonable segun el trabajo necesario.
18. La suma nunca debe superar el limite del cliente.
19. Considera costo, calidad, dificultad, riesgo y verificabilidad.
20. market_gaps NO significa funcionalidades faltantes.
21. market_gaps contiene EXCLUSIVAMENTE habilidades necesarias
    para el proyecto que no estan suficientemente cubiertas por
    los Replikers actualmente disponibles.
22. Si todas las habilidades necesarias estan cubiertas por el
    mercado, market_gaps debe ser una lista vacia.
23. No inventes market_gaps sobre funciones que el cliente no pidio.
24. El resultado final debe poder verificarse contra los requisitos
    originales del cliente.
25. No prometas perfeccion absoluta.
26. Los importes monetarios se expresan en centimos.
27. No expongas razonamiento privado paso a paso.
28. summary y strategy deben contener solamente conclusiones
    operativas utiles para el proyecto.
""".strip()


def normalize_budgets(
    plan: AIProjectPlan,
    budget_limit_cents: int | None,
) -> AIProjectPlan:
    if not plan.tasks:
        raise ValueError(
            "R00 no genero ninguna tarea."
        )

    if budget_limit_cents is None:
        return plan

    if budget_limit_cents <= 0:
        raise ValueError(
            "El presupuesto limite debe ser positivo."
        )

    total = sum(
        task.max_budget_cents
        for task in plan.tasks
    )

    if total <= budget_limit_cents:
        return plan

    factor = (
        budget_limit_cents
        / total
    )

    amounts = [
        max(
            100,
            round(
                task.max_budget_cents
                * factor
            ),
        )
        for task in plan.tasks
    ]

    difference = (
        budget_limit_cents
        - sum(amounts)
    )

    if amounts:
        amounts[-1] += difference

    for task, amount in zip(
        plan.tasks,
        amounts,
    ):
        task.max_budget_cents = max(
            100,
            amount,
        )

    final_total = sum(
        task.max_budget_cents
        for task in plan.tasks
    )

    if final_total > budget_limit_cents:
        raise ValueError(
            "No fue posible normalizar "
            "el presupuesto generado por R00."
        )

    return plan


def _build_r00_chain():
    """
    R00 deja de utilizar directamente google.genai.

    LangChain construye el modelo y exige una
    respuesta validada mediante AIProjectPlan.
    """

    model = get_chat_model(
        temperature=0.1
    )

    return model.with_structured_output(
        AIProjectPlan,
        method="json_schema",
    )


def build_project_plan(
    *,
    project_data: dict,
    marketplace_data: list[dict],
) -> AIProjectPlan:
    context = {
        "project": project_data,
        "current_market": {
            "available_replikers":
                marketplace_data,
            "rules": [
                (
                    "Primero determina lo que "
                    "necesita el proyecto."
                ),
                (
                    "No adaptes artificialmente "
                    "el proyecto para utilizar "
                    "agentes existentes."
                ),
                (
                    "Usa market_gaps solamente "
                    "para habilidades necesarias "
                    "que el mercado actual no cubre."
                ),
            ],
        },
    }

    prompt = (
        "Genera el plan autonomo de trabajo "
        "para este proyecto.\n\n"
        + json.dumps(
            context,
            ensure_ascii=False,
            indent=2,
        )
    )

    try:
        chain = _build_r00_chain()

        result = chain.invoke(
            [
                SystemMessage(
                    content=
                        SYSTEM_INSTRUCTION
                ),
                HumanMessage(
                    content=prompt
                ),
            ]
        )

    except AgenticConfigurationError as exc:
        raise GeminiConfigurationError(
            str(exc)
        ) from exc

    except Exception as exc:
        raise GeminiResponseError(
            "R00 no pudo generar un plan "
            "estructurado mediante LangChain. "
            f"Detalle: {exc}"
        ) from exc

    if isinstance(
        result,
        AIProjectPlan,
    ):
        plan = result
    else:
        try:
            plan = (
                AIProjectPlan
                .model_validate(
                    result
                )
            )
        except Exception as exc:
            raise GeminiResponseError(
                "LangChain genero una respuesta "
                "que no cumple AIProjectPlan."
            ) from exc

    return normalize_budgets(
        plan=plan,
        budget_limit_cents=(
            project_data.get(
                "budget_limit_cents"
            )
        ),
    )
