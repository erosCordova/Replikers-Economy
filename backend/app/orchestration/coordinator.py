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
    PlannedSpecialist,
)
from app.services.gemini_client import (
    GeminiConfigurationError,
    GeminiResponseError,
)


SYSTEM_INSTRUCTION = """
Eres Iris, el Repliker Product / Requirements oficial de
Repliker Economy.

R00 sigue siendo el motor interno de orquestacion del sistema.
Tu eres el Repliker visible encargado de comprender el proyecto
del cliente y preparar el trabajo para el mercado.

REGLAS:

1. Analiza primero lo que realmente pidio el cliente.
2. No utilices una plantilla fija de especialistas.
3. Cubre todos los requisitos obligatorios.
4. No inventes funcionalidades que el cliente no pidio.
5. Agrega trabajo adicional solamente cuando sea tecnicamente
   necesario para entregar correctamente lo solicitado.
6. Determina las especialidades profesionales necesarias.
7. required_specialists contiene especialidades, nunca nombres
   concretos de Replikers.
8. No selecciones Replikers concretos.
9. Cada Repliker decidira posteriormente si desea competir.
10. Cada tarea debe declarar una required_specialty principal.
11. Define las skills y nivel minimo necesarios para cada tarea.
12. Divide el proyecto en el menor numero razonable de tareas.
13. Cada tarea debe producir un entregable concreto.
14. Evita trabajo redundante.
15. Define criterios verificables de aceptacion.
16. Product / Requirements no necesita una tarea para contratarse
    a si mismo.
17. Final Reviewer siempre debe formar parte de
    required_specialists.
18. Final Reviewer debe tener mandatory=true y final_gate=true.
19. Final Reviewer no debe ser una tarea normal de desarrollo.
20. Los demas especialistas deben tener final_gate=false.
21. No incluyas Security, SEO, Accessibility, Content u otros
    especialistas solamente porque existan en el mercado.
22. Incluyelos cuando sean realmente necesarios para ese proyecto.
23. El presupuesto del cliente es un limite maximo.
24. No intentes gastar todo el presupuesto.
25. La suma de las tareas nunca debe superar ese limite.
26. market_gaps contiene solamente capacidades necesarias que el
    mercado actual no cubre suficientemente.
27. Si todo esta cubierto, market_gaps debe ser una lista vacia.
28. No adaptes artificialmente el proyecto para utilizar agentes
    existentes.
29. No expongas razonamiento privado paso a paso.
30. summary y strategy contienen solamente conclusiones operativas.
""".strip()


def normalize_budgets(
    plan: AIProjectPlan,
    budget_limit_cents: int | None,
) -> AIProjectPlan:
    if not plan.tasks:
        raise ValueError(
            "Iris no genero ninguna tarea."
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

    minimum_total = (
        100 * len(plan.tasks)
    )

    if minimum_total > budget_limit_cents:
        raise ValueError(
            "El presupuesto limite es demasiado "
            "bajo para las tareas necesarias."
        )

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

    amounts[-1] += difference

    if amounts[-1] < 100:
        deficit = 100 - amounts[-1]
        amounts[-1] = 100

        for index in range(
            len(amounts) - 2,
            -1,
            -1,
        ):
            available = max(
                0,
                amounts[index] - 100,
            )

            transfer = min(
                available,
                deficit,
            )

            amounts[index] -= transfer
            deficit -= transfer

            if deficit == 0:
                break

        if deficit > 0:
            raise ValueError(
                "No fue posible normalizar "
                "el presupuesto de Iris."
            )

    for task, amount in zip(
        plan.tasks,
        amounts,
    ):
        task.max_budget_cents = amount

    if (
        sum(
            task.max_budget_cents
            for task in plan.tasks
        )
        > budget_limit_cents
    ):
        raise ValueError(
            "No fue posible normalizar "
            "el presupuesto generado por Iris."
        )

    return plan


def normalize_specialists(
    plan: AIProjectPlan,
) -> AIProjectPlan:
    specialists: dict[
        str,
        PlannedSpecialist,
    ] = {}

    for specialist in plan.required_specialists:
        name = specialist.specialty.strip()

        if not name:
            continue

        normalized = name.lower()

        if normalized == "product / requirements":
            continue

        specialist.specialty = name

        if normalized == "final reviewer":
            specialist.mandatory = True
            specialist.final_gate = True
        else:
            specialist.final_gate = False

        specialists[normalized] = specialist

    for task in plan.tasks:
        specialty = (
            task.required_specialty
            .strip()
        )

        if not specialty:
            specialty = "Generalist"
            task.required_specialty = specialty

        normalized = specialty.lower()

        if normalized == "final reviewer":
            raise GeminiResponseError(
                "Final Reviewer no debe aparecer "
                "como una tarea normal."
            )

        if normalized == "product / requirements":
            raise GeminiResponseError(
                "Product / Requirements no debe "
                "crearse como una tarea normal."
            )

        if normalized not in specialists:
            specialists[normalized] = (
                PlannedSpecialist(
                    specialty=specialty,
                    reason=(
                        "Especialidad principal "
                        "requerida por una tarea "
                        "del proyecto."
                    ),
                    mandatory=True,
                    final_gate=False,
                )
            )

    final_key = "final reviewer"

    if final_key not in specialists:
        specialists[final_key] = (
            PlannedSpecialist(
                specialty="Final Reviewer",
                reason=(
                    "Revision integral obligatoria "
                    "antes de entregar el proyecto."
                ),
                mandatory=True,
                final_gate=True,
            )
        )

    plan.required_specialists = list(
        specialists.values()
    )

    return plan


def _build_iris_chain():
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
                    "Determina primero lo que "
                    "necesita el proyecto."
                ),
                (
                    "No selecciones candidatos "
                    "por nombre."
                ),
                (
                    "No adaptes el proyecto para "
                    "usar agentes existentes."
                ),
                (
                    "Usa market_gaps solo para "
                    "capacidades realmente "
                    "necesarias y no cubiertas."
                ),
            ],
        },
    }

    prompt = (
        "Analiza los requisitos y genera "
        "el plan de trabajo.\n\n"
        + json.dumps(
            context,
            ensure_ascii=False,
            indent=2,
        )
    )

    try:
        chain = _build_iris_chain()

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
            "Iris no pudo generar un plan "
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

    plan = normalize_specialists(
        plan
    )

    return normalize_budgets(
        plan=plan,
        budget_limit_cents=(
            project_data.get(
                "budget_limit_cents"
            )
        ),
    )
