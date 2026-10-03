from app.agentic.model import (
    AgenticConfigurationError,
)
from app.agentic.repliker_runtime import (
    run_specialist_offer_agent,
)
from app.schemas.market import (
    SpecialistOfferDecisionAI,
)
from app.services.gemini_client import (
    GeminiConfigurationError,
    GeminiResponseError,
)


def evaluate_repliker_for_specialist_role(
    *,
    repliker_data: dict,
    requirement_data: dict,
    project_data: dict,
) -> SpecialistOfferDecisionAI:
    """
    Permite que un Repliker decida de forma
    autónoma si acepta o rechaza un puesto
    dentro de un proyecto.
    """

    try:
        return run_specialist_offer_agent(
            repliker_data=repliker_data,
            requirement_data=
                requirement_data,
            project_data=project_data,
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
            "El Repliker no pudo evaluar "
            "la propuesta mediante LangChain. "
            f"Detalle: {exc}"
        ) from exc
