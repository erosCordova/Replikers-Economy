import time
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import (
    BaseModel,
    ValidationError,
)

from app.core.config import settings


T = TypeVar(
    "T",
    bound=BaseModel,
)


class GeminiConfigurationError(Exception):
    pass


class GeminiResponseError(Exception):
    pass


PRIMARY_MODEL = (
    settings.GEMINI_MODEL.strip()
    if settings.GEMINI_MODEL
    else "gemini-3.8-flash"
)

FALLBACK_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

MAX_ATTEMPTS_PER_MODEL = 2

RETRY_DELAYS = [
    2,
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


def _candidate_models() -> list[str]:
    models: list[str] = []

    candidates = [
        PRIMARY_MODEL,
        *FALLBACK_MODELS,
    ]

    for model in candidates:
        clean_model = model.strip()

        if (
            clean_model
            and clean_model not in models
        ):
            models.append(
                clean_model
            )

    return models


def _is_temporary_error(
    exc: Exception,
) -> bool:
    text = str(exc).lower()

    signals = [
        "429",
        "503",
        "unavailable",
        "high demand",
        "temporarily",
        "service unavailable",
        "resource_exhausted",
        "rate limit",
        "too many requests",
        "timeout",
        "timed out",
    ]

    return any(
        signal in text
        for signal in signals
    )


def _compact_error(
    exc: Exception,
) -> str:
    text = " ".join(
        str(exc).split()
    )

    if len(text) > 300:
        return (
            text[:300]
            + "..."
        )

    return text


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
            system_instruction=
                system_instruction,
            response_mime_type=
                "application/json",
            response_json_schema=
                schema,
        ),
    )


def generate_structured(
    *,
    system_instruction: str,
    prompt: str,
    response_model: type[T],
    response_schema:
        dict | None = None,
) -> T:
    client = get_client()

    schema = (
        response_schema
        if response_schema is not None
        else response_model
        .model_json_schema()
    )

    models = _candidate_models()

    last_error: Exception | None = None

    errors_by_model: dict[
        str,
        str,
    ] = {}

    for model in models:

        for attempt in range(
            MAX_ATTEMPTS_PER_MODEL
        ):
            try:
                response = _generate_once(
                    client=client,
                    model=model,
                    system_instruction=
                        system_instruction,
                    prompt=prompt,
                    schema=schema,
                )

                return _validate_response(
                    response=response,
                    response_model=
                        response_model,
                )

            except Exception as exc:
                last_error = exc

                errors_by_model[
                    model
                ] = _compact_error(
                    exc
                )

                if not _is_temporary_error(
                    exc
                ):
                    break

                if attempt < (
                    MAX_ATTEMPTS_PER_MODEL
                    - 1
                ):
                    time.sleep(
                        RETRY_DELAYS[0]
                    )

    model_names = ", ".join(
        models
    )

    if (
        last_error is not None
        and _is_temporary_error(
            last_error
        )
    ):
        raise GeminiResponseError(
            "El proveedor de IA esta "
            "temporalmente saturado. "
            "Repliker Economy intento: "
            f"{model_names}."
        ) from last_error

    details = "; ".join(
        f"{model}: {error}"
        for model, error
        in errors_by_model.items()
    )

    raise GeminiResponseError(
        "No fue posible obtener una "
        "respuesta valida del motor IA. "
        f"Modelos intentados: "
        f"{model_names}. "
        f"Detalle: {details}"
    ) from last_error


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
        return (
            response_model
            .model_validate_json(
                output_text
            )
        )

    except ValidationError as exc:
        raise GeminiResponseError(
            "Gemini genero JSON, "
            "pero no cumple la "
            "estructura requerida por "
            "Repliker Economy."
        ) from exc
