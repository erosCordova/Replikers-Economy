from functools import lru_cache

from langchain_google_genai import (
    ChatGoogleGenerativeAI,
)

from app.core.config import settings


class AgenticConfigurationError(
    RuntimeError
):
    pass


@lru_cache(maxsize=8)
def get_chat_model(
    temperature: float = 0.1,
) -> ChatGoogleGenerativeAI:
    """
    Modelo oficial utilizado por los agentes
    LangChain de Repliker Economy.

    La funcion centraliza la configuracion para
    evitar que cada Repliker construya clientes
    distintos de manera inconsistente.
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

    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=temperature,
        max_retries=2,
    )
