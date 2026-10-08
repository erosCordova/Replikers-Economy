from functools import lru_cache

from langchain_google_genai import (
    ChatGoogleGenerativeAI,
)

from app.core.config import settings


class AgenticConfigurationError(
    RuntimeError
):
    pass


def _supports_sampling_temperature(
    model_name: str,
) -> bool:
    """
    Gemini 3.8 Flash utiliza la nueva
    configuracion de razonamiento y rechaza
    parametros de sampling heredados como
    temperature en ciertas rutas/API.

    Otros modelos mantienen el comportamiento
    anterior.
    """

    normalized = (
        model_name
        .strip()
        .lower()
    )

    return not (
        normalized.startswith(
            "gemini-3.8"
        )
        or normalized.startswith(
            "gemini-3.5-flash-lite"
        )
    )


@lru_cache(maxsize=8)
def get_chat_model(
    temperature: float = 0.1,
) -> ChatGoogleGenerativeAI:
    """
    Modelo oficial utilizado por los agentes
    LangChain de Repliker Economy.

    Centraliza la configuracion del proveedor
    y evita enviar parametros incompatibles
    con Gemini 3.8 Flash.
    """

    api_key = (
        settings.GEMINI_API_KEY
        .strip()
    )

    model_name = (
        settings.GEMINI_MODEL
        .strip()
    )

    if not api_key:
        raise AgenticConfigurationError(
            "GEMINI_API_KEY no esta configurada."
        )

    if not model_name:
        raise AgenticConfigurationError(
            "GEMINI_MODEL no esta configurado."
        )

    model_kwargs = {
        "model":
            model_name,
        "google_api_key":
            api_key,
        "max_retries":
            0,
    }

    if _supports_sampling_temperature(
        model_name
    ):
        model_kwargs[
            "temperature"
        ] = temperature

    return ChatGoogleGenerativeAI(
        **model_kwargs
    )
