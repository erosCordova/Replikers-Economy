from app.agentic.model import (
    AgenticConfigurationError,
)
from app.agentic.repliker_runtime import (
    run_market_agent,
)
from app.schemas.market import (
    AgentDecisionAI,
)
from app.services.gemini_client import (
    GeminiConfigurationError,
    GeminiResponseError,
)


def evaluate_repliker_for_task(
    *,
    repliker_data: dict,
    task_data: dict,
    project_data: dict,
    allowed_tool_names:
        tuple[str, ...]
        | None = None,
) -> AgentDecisionAI:
    try:
        decision = run_market_agent(
            repliker_data=
                repliker_data,
            task_data=
                task_data,
            project_data=
                project_data,
            allowed_tool_names=
                allowed_tool_names,
        )

    except AgenticConfigurationError as exc:
        raise GeminiConfigurationError(
            str(exc)
        ) from exc

    except GeminiConfigurationError:
        raise

    except GeminiResponseError:
        raise

    except Exception as exc:
        raise GeminiResponseError(
            "El Repliker no pudo completar "
            "su evaluacion mediante LangChain. "
            f"Detalle: {exc}"
        ) from exc

    if decision.decision == "pass":
        decision.amount_cents = None
        decision.estimated_minutes = None

        return decision

    max_budget = task_data.get(
        "max_budget_cents"
    )

    if decision.amount_cents is None:
        decision.decision = "pass"

        decision.reasoning += (
            " La decision fue convertida a PASS "
            "porque el agente no proporciono "
            "un precio valido."
        )

        decision.estimated_minutes = None

        return decision

    if decision.estimated_minutes is None:
        decision.decision = "pass"

        decision.amount_cents = None

        decision.reasoning += (
            " La decision fue convertida a PASS "
            "porque el agente no proporciono "
            "una estimacion de tiempo."
        )

        return decision

    if decision.amount_cents <= 0:
        decision.decision = "pass"

        decision.amount_cents = None
        decision.estimated_minutes = None

        decision.reasoning += (
            " La decision fue convertida a PASS "
            "porque el precio era invalido."
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
