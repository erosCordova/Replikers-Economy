
"""Replikers World: generacion de ideas economicas.

El Repliker observa agentes, consulta sus propios
recursos y propone negocios mediante un motor de IA.

No ejecuta contratos, pagos ni publicaciones.
"""

import json
import os
from typing import Any, Callable, TypedDict

from langgraph.graph import StateGraph, START, END
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.economy import LedgerAccount
from app.services.economy_service import (
    account_balance,
    ensure_simulation_mode,
)


IdeaEngine = Callable[
    [dict[str, Any]],
    dict[str, Any],
]


class WorldIdeaState(TypedDict, total=False):
    repliker_id: int
    balance_cents: int
    peers: list[dict[str, Any]]
    generated_idea: dict[str, Any] | None
    validated_idea: dict[str, Any] | None
    status: str
    payment_executed: bool


def build_world_idea_graph(
    *,
    db: Session,
    idea_engine: IdeaEngine,
):
    """Construye un ciclo inicial de iniciativa propia."""

    def observe(state: WorldIdeaState):
        ensure_simulation_mode()

        actor_id = state.get("repliker_id")

        if type(actor_id) is not int or actor_id <= 0:
            return {
                "status": "agente_invalido",
                "payment_executed": False,
            }

        accounts = list(
            db.scalars(
                select(LedgerAccount)
                .where(
                    LedgerAccount.kind
                    == "repliker_available",
                    LedgerAccount.currency == "RCR",
                    LedgerAccount.is_active.is_(True),
                )
                .order_by(
                    LedgerAccount.repliker_id
                )
                .limit(100)
            )
        )

        actor_account = next(
            (
                account for account in accounts
                if account.repliker_id == actor_id
            ),
            None,
        )

        if actor_account is None:
            return {
                "status": "agente_sin_billetera",
                "payment_executed": False,
            }

        balance = account_balance(
            db=db,
            account_id=actor_account.id,
        )

        if balance < 0:
            return {
                "status": "saldo_invalido",
                "payment_executed": False,
            }

        peers = []

        for account in accounts:
            if account.repliker_id == actor_id:
                continue

            peer_balance = account_balance(
                db=db,
                account_id=account.id,
            )

            if peer_balance < 0:
                continue

            peers.append({
                "repliker_id": account.repliker_id,
                "balance_cents": peer_balance,
            })

        if not peers:
            return {
                "balance_cents": balance,
                "peers": [],
                "status": "sin_contrapartes",
                "payment_executed": False,
            }

        return {
            "balance_cents": balance,
            "peers": peers,
            "generated_idea": None,
            "validated_idea": None,
            "status": "entorno_observado",
            "payment_executed": False,
        }

    def invent(state: WorldIdeaState):
        if state.get("status") != "entorno_observado":
            return {}

        context = {
            "objective": (
                "Proponer una oportunidad economica "
                "original que busque aumentar "
                "el patrimonio del agente."
            ),
            "repliker_id": state["repliker_id"],
            "available_cents": state["balance_cents"],
            "potential_counterparties": state["peers"],
            "currency": "RCR",
            "stage": "simulation",
        }

        try:
            proposal = idea_engine(context)

            if not isinstance(proposal, dict):
                raise ValueError(
                    "La IA no devolvio un objeto."
                )

            return {
                "generated_idea": proposal,
                "status": "idea_generada",
                "payment_executed": False,
            }

        except Exception:
            return {
                "generated_idea": None,
                "status": "error_generacion",
                "payment_executed": False,
            }

    def validate(state: WorldIdeaState):
        if state.get("status") != "idea_generada":
            return {}

        idea = state.get("generated_idea")

        if not isinstance(idea, dict):
            return {
                "status": "idea_invalida",
                "payment_executed": False,
            }

        title = idea.get("title")
        description = idea.get("description")
        target_id = idea.get("target_repliker_id")
        price = idea.get("price_cents")
        cost = idea.get("estimated_cost_cents")

        if not (
            isinstance(title, str)
            and 3 <= len(title.strip()) <= 120
            and isinstance(description, str)
            and 10 <= len(description.strip()) <= 1000
        ):
            return {
                "status": "descripcion_invalida",
                "payment_executed": False,
            }

        if type(target_id) is not int or target_id <= 0:
            return {
                "status": "contraparte_invalida",
                "payment_executed": False,
            }

        if target_id == state["repliker_id"]:
            return {
                "status": "autonegociacion_rechazada",
                "payment_executed": False,
            }

        peer = next(
            (
                item
                for item in state.get("peers", [])
                if item["repliker_id"] == target_id
            ),
            None,
        )

        if peer is None:
            return {
                "status": "contraparte_no_existente",
                "payment_executed": False,
            }

        if (
            type(price) is not int
            or type(cost) is not int
            or price <= 0
            or cost < 0
            or price > 1_000_000_000
            or cost > 1_000_000_000
        ):
            return {
                "status": "importes_invalidos",
                "payment_executed": False,
            }

        if cost > state["balance_cents"]:
            return {
                "status": "capital_insuficiente",
                "payment_executed": False,
            }

        if price > peer["balance_cents"]:
            return {
                "status": "contraparte_sin_capital",
                "payment_executed": False,
            }

        if price <= cost:
            return {
                "status": "margen_estimado_no_positivo",
                "payment_executed": False,
            }

        # La IA estima costos, pero no demuestra
        # que el negocio sea realmente rentable.
        # La contraparte todavia no ha aceptado.
        validated = {
            "proposer_repliker_id":
                state["repliker_id"],
            "target_repliker_id": target_id,
            "title": title.strip(),
            "description": description.strip(),
            "currency": "RCR",
            "price_cents": price,
            "estimated_cost_cents": cost,
            "estimated_gross_margin_cents":
                price - cost,
            "counterparty_accepted": False,
            "contract_executed": False,
            "payment_executed": False,
        }

        return {
            "validated_idea": validated,
            "status": "lista_para_negociar",
            "payment_executed": False,
        }

    graph = StateGraph(WorldIdeaState)

    graph.add_node("observe", observe)
    graph.add_node("invent", invent)
    graph.add_node("validate", validate)

    graph.add_edge(START, "observe")
    graph.add_edge("observe", "invent")
    graph.add_edge("invent", "validate")
    graph.add_edge("validate", END)

    return graph.compile()


def make_gemini_idea_engine(
    model_name: str = 'gemini-3.5-flash-lite',
) -> IdeaEngine:
    """Conectar un modelo Gemini mediante LangChain.

    La clave se obtiene del entorno. Crear el motor
    no realiza una consulta a la API.
    """

    key = (
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )

    if not key:
        raise RuntimeError(
            "No hay una clave de Gemini configurada."
        )

    from langchain_google_genai import (
        ChatGoogleGenerativeAI,
    )

    from langchain_core.messages import (
        HumanMessage,
        SystemMessage,
    )

    model = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0.6,
        google_api_key=key,
        vertexai=False,
    )

    def generate(context: dict[str, Any]):
        instructions = (
            "Eres un agente economico autonomo "
            "dentro de Replikers World. "
            "Tu objetivo continuo es buscar "
            "oportunidades para aumentar tu dinero. "
            "No tienes una profesion impuesta. "
            "Puedes inventar una actividad economica "
            "original, siempre que se pueda proponer "
            "de manera legal dentro de la simulacion. "
            "Solo dispones de la informacion presentada. "
            "No inventes clientes confirmados, "
            "beneficios realizados ni contratos. "
            "La otra parte aun no ha aceptado. "
            "Los costos y beneficios son estimaciones. "
            "Devuelve exclusivamente JSON con: "
            "title, description, target_repliker_id, "
            "price_cents y estimated_cost_cents. "
            "Los importes son enteros en centesimos RCR. "
            "No incluyas texto fuera del JSON."
        )

        response = model.invoke([
            SystemMessage(content=instructions),
            HumanMessage(
                content=json.dumps(
                    context,
                    ensure_ascii=False,
                )
            ),
        ])

        content = response.content

        if isinstance(content, list):
            content = "\n".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
                and isinstance(part.get("text"), str)
            )

        if not isinstance(content, str):
            raise ValueError(
                "Respuesta del modelo invalida."
            )

        content = content.strip()

        if content.startswith("```"):
            lines = content.splitlines()
            if len(lines) >= 3:
                content = "\n".join(
                    lines[1:-1]
                ).strip()

        result = json.loads(content)

        if not isinstance(result, dict):
            raise ValueError(
                "El modelo no devolvio un objeto."
            )

        return result

    return generate
