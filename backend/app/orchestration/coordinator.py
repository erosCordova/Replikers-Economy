import json

from app.schemas.coordinator import AIProjectPlan
from app.services.gemini_client import generate_structured


SYSTEM_INSTRUCTION = """
Eres R00, el Coordinador autonomo de Repliker Economy.

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
"""


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

    total = sum(
        task.max_budget_cents
        for task in plan.tasks
    )

    if total <= budget_limit_cents:
        return plan

    factor = budget_limit_cents / total

    amounts = [
        max(
            100,
            round(
                task.max_budget_cents * factor
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

    return plan


def build_project_plan(
    *,
    project_data: dict,
    marketplace_data: list[dict],
) -> AIProjectPlan:

    context = {
        "project": project_data,
        "current_market": {
            "available_replikers": marketplace_data,
            "rules": [
                (
                    "Primero determina lo que necesita "
                    "el proyecto."
                ),
                (
                    "No adaptes artificialmente el proyecto "
                    "para utilizar agentes existentes."
                ),
                (
                    "Usa market_gaps solamente para habilidades "
                    "necesarias que el mercado actual no cubre."
                ),
            ],
        },
    }

    prompt = (
        "Genera el plan autonomo de trabajo para este proyecto.\n\n"
        + json.dumps(
            context,
            ensure_ascii=False,
            indent=2,
        )
    )

    plan = generate_structured(
        system_instruction=SYSTEM_INSTRUCTION,
        prompt=prompt,
        response_model=AIProjectPlan,
    )

    return normalize_budgets(
        plan=plan,
        budget_limit_cents=(
            project_data.get(
                "budget_limit_cents"
            )
        ),
    )
