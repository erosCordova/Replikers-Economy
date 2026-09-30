import time
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.config import settings


T = TypeVar(
    "T",
    bound=BaseModel,
)


class GeminiConfigurationError(Exception):
    pass


class GeminiResponseError(Exception):
    pass


PRIMARY_MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-3.7-flash"

MAX_ATTEMPTS_PRIMARY = 3

RETRY_DELAYS = [
    2,
    5,
    10,
]


def get_client() -> genai.Client:
    if not settings.GEMINI_API_KEY:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY no esta configurada."
        )

    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=60000,
        ),
    )


def _is_temporary_error(
    exc: Exception,
) -> bool:
    text = str(exc).lower()

    temporary_signals = [
        "503",
        "unavailable",
        "high demand",
        "temporarily",
        "service unavailable",
    ]

    return any(
        signal in text
        for signal in temporary_signals
    )


def _generate_once(
    *,
    client: genai.Client,
    model: str,
    system_instruction: str,
    prompt: str,
    schema: dict,
):
    return client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_json_schema=schema,
        ),
    )


def generate_structured(
    *,
    system_instruction: str,
    prompt: str,
    response_model: type[T],
    response_schema: dict | None = None,
) -> T:

    client = get_client()

    schema = (
        response_schema
        if response_schema is not None
        else response_model.model_json_schema()
    )

    last_error = None

    # ==================================================
    # 1. MODELO PRINCIPAL
    # ==================================================

    for attempt in range(
        MAX_ATTEMPTS_PRIMARY
    ):

        try:
            response = _generate_once(
                client=client,
                model=PRIMARY_MODEL,
                system_instruction=system_instruction,
                prompt=prompt,
                schema=schema,
            )

            return _validate_response(
                response=response,
                response_model=response_model,
            )

        except Exception as exc:
            last_error = exc

            if not _is_temporary_error(exc):
                raise GeminiResponseError(
                    f"Error utilizando "
                    f"{PRIMARY_MODEL}: {exc}"
                ) from exc

            if attempt < (
                MAX_ATTEMPTS_PRIMARY - 1
            ):
                time.sleep(
                    RETRY_DELAYS[attempt]
                )

    # ==================================================
    # 2. FALLBACK
    # ==================================================

    try:
        response = _generate_once(
            client=client,
            model=FALLBACK_MODEL,
            system_instruction=system_instruction,
            prompt=prompt,
            schema=schema,
        )

        return _validate_response(
            response=response,
            response_model=response_model,
        )

    except Exception as exc:
        raise GeminiResponseError(
            "No fue posible obtener respuesta "
            "del motor IA.\n"
            f"Principal: {PRIMARY_MODEL}\n"
            f"Fallback: {FALLBACK_MODEL}\n"
            f"Ultimo error principal: {last_error}\n"
            f"Error fallback: {exc}"
        ) from exc


def _validate_response(
    *,
    response,
    response_model: type[T],
) -> T:

    output_text = getattr(
        response,
        "text",
        None,
    )

    if not output_text:
        raise GeminiResponseError(
            "Gemini no devolvio contenido."
        )

    try:
        return response_model.model_validate_json(
            output_text
        )

    except ValidationError as exc:
        raise GeminiResponseError(
            "Gemini genero JSON, pero no cumple "
            "la estructura requerida por "
            f"Repliker Economy: {exc}"
        ) from exc
