
"""Integracion Gemini para Replikers World.

Conecta los dos motores LangChain existentes con
el coordinador economico multiagente LangGraph.

Las decisiones proceden de Gemini si se dispone
de credenciales. Este modulo no realiza pagos,
contratos ni transferencias por su cuenta.
"""

import re
from sqlalchemy.orm import Session

from app.agentic.world_idea_graph import (
    make_gemini_idea_engine,
)
from app.agentic.world_negotiation_graph import (
    make_gemini_response_engine,
)
from app.agentic.world_autonomy_runtime import (
    run_world_round,
)
from app.services.economy_service import (
    ensure_simulation_mode,
)


def run_world_with_gemini(
    db: Session,
    *,
    round_id: str,
    max_agents: int = 3,
    model_name: str = 'gemini-3.5-flash-lite',
) -> list[dict]:
    """Ejecutar una ronda de propuestas y negociaciones.

    No transfiere RCR ni crea contratos.
    El coordinador verifica propuestas y estados.
    """

    ensure_simulation_mode()

    if (
        type(max_agents) is not int
        or not 1 <= max_agents <= 3
    ):
        raise ValueError(
            "La prueba permite entre 1 y 3 agentes."
        )

    if (
        not isinstance(model_name, str)
        or not re.fullmatch(
            r"gemini-[A-Za-z0-9._-]{3,80}",
            model_name,
        )
    ):
        raise ValueError(
            "Nombre de modelo Gemini invalido."
        )

    idea_engine = make_gemini_idea_engine(
        model_name=model_name,
    )

    response_engine = make_gemini_response_engine(
        model_name=model_name,
    )

    return run_world_round(
        db,
        round_id=round_id,
        idea_engine=idea_engine,
        response_engine=response_engine,
        max_agents=max_agents,
    )
