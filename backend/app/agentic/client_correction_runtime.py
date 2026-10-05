from __future__ import annotations

import json

from typing import Literal

from langchain.agents import (
    create_agent,
)
from langchain.agents.structured_output import (
    ToolStrategy,
)
from pydantic import (
    BaseModel,
    Field,
)

from app.agentic.model import (
    get_chat_model,
)


class ClientCorrectionItem(BaseModel):
    task_id: int = Field(
        ge=1,
    )

    instruction: str = Field(
        min_length=5,
        max_length=4000,
    )

    severity: Literal[
        "low",
        "medium",
        "high",
    ] = "medium"


class ClientCorrectionPlan(BaseModel):
    summary: str = Field(
        min_length=5,
        max_length=2000,
    )

    corrections: list[
        ClientCorrectionItem
    ] = Field(
        min_length=1,
        max_length=50,
    )


CLIENT_CORRECTION_SYSTEM_PROMPT = """
Eres R00, coordinador de proyectos de Replikers.

Tu tarea es interpretar una solicitud de corrección
realizada por el cliente después de revisar una
entrega que ya fue aprobada técnicamente por Vera.

Debes convertir la solicitud del cliente en
instrucciones concretas para las tareas existentes
del proyecto.

REGLAS OBLIGATORIAS:

1. Usa exclusivamente task_id existentes en el
   contexto recibido.
2. No inventes tareas.
3. No añadas cambios que el cliente no haya pedido.
4. Selecciona únicamente las tareas realmente
   relacionadas con la solicitud.
5. Si el cambio afecta varias tareas, genera una
   corrección para cada tarea necesaria.
6. Cada instrucción debe ser clara y ejecutable
   por el Repliker responsable.
7. severity solo puede ser:
   low, medium o high.
8. Todo texto visible debe estar en español.
9. La palabra Repliker puede mantenerse.
10. No expongas razonamiento privado paso a paso.
11. corrections debe contener al menos una
    corrección.
""".strip()


def run_client_correction_planner(
    *,
    project_data: dict,
    tasks: list[dict],
    client_request: str,
) -> ClientCorrectionPlan:
    agent = create_agent(
        model=get_chat_model(
            temperature=0.1
        ),
        tools=[],
        system_prompt=(
            CLIENT_CORRECTION_SYSTEM_PROMPT
        ),
        response_format=ToolStrategy(
            ClientCorrectionPlan
        ),
        name=(
            "r00_client_correction_planner"
        ),
    )

    context = {
        "proyecto":
            project_data,

        "solicitud_cliente":
            client_request,

        "tareas_disponibles":
            tasks,
    }

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Analiza la solicitud "
                        "del cliente y prepara "
                        "el plan exacto de "
                        "correcciones.\n\n"
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
            "R00 no devolvió un plan "
            "estructurado de correcciones."
        )

    if isinstance(
        structured,
        ClientCorrectionPlan,
    ):
        return structured

    return (
        ClientCorrectionPlan
        .model_validate(
            structured
        )
    )
