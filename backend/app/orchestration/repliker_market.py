import json

from app.schemas.market import (
    AgentDecisionAI,
)
from app.services.gemini_client import (
    generate_structured,
)


SYSTEM_INSTRUCTION = """
Eres un Repliker autonomo dentro de Repliker Economy.

NO eres el coordinador R00.

Representas exclusivamente los intereses,
capacidades y limitaciones del Repliker cuyo
perfil recibiras.

Tu tarea es analizar una oportunidad de trabajo
y decidir autonomamente si deseas competir por ella.

Solo existen dos decisiones:

- bid
- pass

REGLAS:

1. No debes ofertar por todas las tareas.

2. Evalua honestamente si tus habilidades son
   suficientes para completar el trabajo.

3. Considera las habilidades requeridas,
   complejidad, criterios de aceptacion y
   presupuesto disponible.

4. Si tus capacidades son claramente insuficientes,
   debes elegir pass.

5. Si eliges bid, propone un precio razonable.

6. No tienes obligacion de utilizar todo el
   presupuesto disponible.

7. El precio ofertado nunca puede superar
   el presupuesto maximo de la tarea.

8. confidence_score representa tu confianza real
   de poder entregar correctamente el trabajo.

9. No infles artificialmente tu confianza.

10. estimated_minutes debe ser una estimacion
    razonable del esfuerzo necesario.

11. reasoning debe explicar por que la tarea
    tiene o no sentido para ti.

12. message es el mensaje comercial breve que
    podria ver el cliente o coordinador.

13. Tu reputacion y trabajos completados son
    contexto, no una orden para aceptar trabajo.

14. Una habilidad similar puede ser relevante,
    pero no debes fingir experiencia inexistente.

15. No asumas que posteriormente otro agente
    arreglara tu trabajo.

16. En etapas futuras podras delegar partes,
    pero para esta decision debes evaluar si eres
    un contratista principal razonable.

17. No inventes capacidades que no aparecen
    en tu perfil.

18. Si el presupuesto es demasiado bajo para
    ejecutar razonablemente el trabajo,
    debes elegir pass.

19. Si eliges pass:
    amount_cents debe ser null.

20. Si eliges bid:
    amount_cents y estimated_minutes deben
    contener valores.
"""


def evaluate_repliker_for_task(
    *,
    repliker_data: dict,
    task_data: dict,
    project_data: dict,
) -> AgentDecisionAI:

    context = {
        "repliker": repliker_data,
        "project": project_data,
        "task": task_data,
    }

    prompt = (
        "Analiza esta oportunidad de trabajo y "
        "toma tu decision economica autonomamente.\n\n"
        + json.dumps(
            context,
            ensure_ascii=False,
            indent=2,
        )
    )

    decision = generate_structured(
        system_instruction=SYSTEM_INSTRUCTION,
        prompt=prompt,
        response_model=AgentDecisionAI,
    )

    # =====================================================
    # PASS
    # =====================================================

    if decision.decision == "pass":

        decision.amount_cents = None
        decision.estimated_minutes = None

        return decision

    # =====================================================
    # BID
    # =====================================================

    max_budget = task_data.get(
        "max_budget_cents"
    )

    if decision.amount_cents is None:
        decision.decision = "pass"

        decision.reasoning += (
            " La decision fue convertida a PASS "
            "porque no se proporciono un precio."
        )

        decision.estimated_minutes = None

        return decision

    if decision.estimated_minutes is None:
        decision.decision = "pass"

        decision.amount_cents = None

        decision.reasoning += (
            " La decision fue convertida a PASS "
            "porque no se estimo el tiempo."
        )

        return decision

    if (
        max_budget is not None
        and decision.amount_cents
        > max_budget
    ):
        original_amount = (
            decision.amount_cents
        )

        decision.decision = "pass"

        decision.amount_cents = None
        decision.estimated_minutes = None

        decision.reasoning += (
            " La oferta calculada era de "
            f"{original_amount} centimos, "
            "superior al presupuesto maximo "
            f"de {max_budget} centimos."
        )

    return decision
