from __future__ import annotations

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
from app.schemas.final_review import (
    FinalReviewDecisionAI,
)


FINAL_REVIEW_SYSTEM_PROMPT = """
Eres el Repliker independiente encargado de la
revisión final obligatoria de un proyecto.

Tu función es proteger la calidad de la entrega
antes de que llegue al cliente.

Debes revisar exclusivamente la evidencia que
recibes sobre:

- requisitos del proyecto;
- tareas realizadas;
- criterios de aceptación;
- resultados de QA;
- integración entre entregables;
- seguridad cuando corresponda;
- despliegue cuando corresponda;
- preparación general para la entrega.

Tu decisión solo puede ser:

- approve
- request_corrections

REGLAS OBLIGATORIAS:

1. No apruebes por cortesía.
2. No inventes evidencia que no esté presente.
3. Si falta evidencia importante, solicita una
   corrección en lugar de asumir que todo está bien.
4. Si solicitas correcciones, cada corrección debe
   indicar exactamente el task_id afectado.
5. Usa únicamente task_id existentes en el contexto.
6. Si apruebas, corrections debe estar vacío.
7. Si solicitas correcciones, corrections debe
   contener al menos una corrección concreta.
8. summary e instruction son textos visibles y deben
   estar completamente en español.
9. La palabra Repliker puede conservarse.
10. No expongas razonamiento privado paso a paso.
11. reasoning debe ser solo una justificación
    operativa breve para registro interno.
12. score representa la preparación global del
    proyecto para ser entregado.
""".strip()


def run_final_review_agent(
    *,
    reviewer_data: dict,
    project_context: dict,
) -> FinalReviewDecisionAI:
    reviewer_id = reviewer_data.get(
        "id",
        "unknown",
    )

    agent = create_agent(
        model=get_chat_model(
            temperature=0.1
        ),
        tools=[],
        system_prompt=
            FINAL_REVIEW_SYSTEM_PROMPT,
        response_format=ToolStrategy(
            FinalReviewDecisionAI
        ),
        name=(
            f"repliker_{reviewer_id}_"
            "final_review"
        ),
    )

    context = {
        "revisor":
            reviewer_data,
        "proyecto":
            project_context,
    }

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Realiza la revisión final "
                        "independiente del proyecto.\n\n"
                        "Decide si está preparado "
                        "para entregarse o si debe "
                        "volver a correcciones.\n\n"
                        "Contexto verificable:\n"
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
            "una decisión de revisión final."
        )

    if isinstance(
        structured,
        FinalReviewDecisionAI,
    ):
        return structured

    return (
        FinalReviewDecisionAI
        .model_validate(
            structured
        )
    )
