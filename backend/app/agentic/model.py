from __future__ import annotations

import logging

from functools import lru_cache

from langchain_google_genai import (
    ChatGoogleGenerativeAI,
)

from app.agentic.provider_retry import (
    is_quota_exhausted_error,
    is_transient_provider_error,
)
from app.core.config import settings


logger = logging.getLogger(
    __name__
)


class AgenticConfigurationError(
    RuntimeError
):
    pass


AGENTIC_FALLBACK_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
)


def candidate_chat_model_names(
    primary_model: str | None = None,
) -> list[str]:
    primary = str(
        primary_model
        or settings.GEMINI_MODEL
        or ""
    ).strip()

    models: list[str] = []

    for name in (
        primary,
        *AGENTIC_FALLBACK_MODELS,
    ):
        clean = str(
            name
        ).strip()

        if (
            clean
            and clean not in models
        ):
            models.append(
                clean
            )

    return models


def _supports_sampling_temperature(
    model_name: str,
) -> bool:
    normalized = (
        model_name
        .strip()
        .lower()
    )

    return not normalized.startswith(
        (
            "gemini-3.6",
            "gemini-3.8",
        )
    )


def _model_kwargs(
    *,
    model_name: str,
    temperature: float,
) -> dict:
    api_key = (
        settings.GEMINI_API_KEY
        .strip()
    )

    if not api_key:
        raise AgenticConfigurationError(
            "GEMINI_API_KEY no esta configurada."
        )

    kwargs = {
        "model":
            model_name,
        "google_api_key":
            api_key,

        # Los reintentos entre proveedores
        # los controla Replikers.
        "max_retries":
            0,
    }

    if _supports_sampling_temperature(
        model_name
    ):
        kwargs[
            "temperature"
        ] = temperature

    return kwargs


def _provider_can_fallback(
    exc: Exception,
) -> bool:
    return (
        is_transient_provider_error(
            exc
        )
        or is_quota_exhausted_error(
            exc
        )
    )


class ResilientChatGoogleGenerativeAI(
    ChatGoogleGenerativeAI
):
    """
    Chat model con cambio automatico entre
    modelos Gemini ante 429, 503, cuota o
    indisponibilidad temporal.

    Mantiene las tools y mensajes de LangChain
    porque el fallback recibe exactamente los
    mismos argumentos de _generate.
    """

    def _generate(
        self,
        messages,
        stop=None,
        run_manager=None,
        **kwargs,
    ):
        primary_model = str(
            getattr(
                self,
                "model",
                "",
            )
        )

        try:
            return super()._generate(
                messages,
                stop=stop,
                run_manager=run_manager,
                **kwargs,
            )

        except Exception as first_exc:
            if not _provider_can_fallback(
                first_exc
            ):
                raise

            last_exc = first_exc

            candidates = (
                candidate_chat_model_names(
                    primary_model
                )
            )

            for model_name in candidates:

                if (
                    model_name
                    == primary_model
                ):
                    continue

                logger.warning(
                    "Modelo %s no disponible. "
                    "Replikers continua con %s.",
                    primary_model,
                    model_name,
                )

                temperature = getattr(
                    self,
                    "temperature",
                    0.1,
                )

                if temperature is None:
                    temperature = 0.1

                fallback = (
                    ChatGoogleGenerativeAI(
                        **_model_kwargs(
                            model_name=
                                model_name,
                            temperature=
                                float(
                                    temperature
                                ),
                        )
                    )
                )

                try:
                    return fallback._generate(
                        messages,
                        stop=stop,
                        run_manager=run_manager,
                        **kwargs,
                    )

                except Exception as exc:
                    last_exc = exc

                    if not _provider_can_fallback(
                        exc
                    ):
                        raise

            raise last_exc

    async def _agenerate(
        self,
        messages,
        stop=None,
        run_manager=None,
        **kwargs,
    ):
        primary_model = str(
            getattr(
                self,
                "model",
                "",
            )
        )

        try:
            return await super()._agenerate(
                messages,
                stop=stop,
                run_manager=run_manager,
                **kwargs,
            )

        except Exception as first_exc:
            if not _provider_can_fallback(
                first_exc
            ):
                raise

            last_exc = first_exc

            candidates = (
                candidate_chat_model_names(
                    primary_model
                )
            )

            for model_name in candidates:

                if (
                    model_name
                    == primary_model
                ):
                    continue

                logger.warning(
                    "Modelo %s no disponible. "
                    "Replikers continua con %s.",
                    primary_model,
                    model_name,
                )

                temperature = getattr(
                    self,
                    "temperature",
                    0.1,
                )

                if temperature is None:
                    temperature = 0.1

                fallback = (
                    ChatGoogleGenerativeAI(
                        **_model_kwargs(
                            model_name=
                                model_name,
                            temperature=
                                float(
                                    temperature
                                ),
                        )
                    )
                )

                try:
                    return await fallback._agenerate(
                        messages,
                        stop=stop,
                        run_manager=run_manager,
                        **kwargs,
                    )

                except Exception as exc:
                    last_exc = exc

                    if not _provider_can_fallback(
                        exc
                    ):
                        raise

            raise last_exc


@lru_cache(
    maxsize=16
)
def get_chat_model(
    temperature: float = 0.1,
    model_name: str | None = None,
) -> ChatGoogleGenerativeAI:
    selected_model = str(
        model_name
        or settings.GEMINI_MODEL
        or ""
    ).strip()

    if not selected_model:
        raise AgenticConfigurationError(
            "GEMINI_MODEL no esta configurado."
        )

    return (
        ResilientChatGoogleGenerativeAI(
            **_model_kwargs(
                model_name=
                    selected_model,
                temperature=
                    temperature,
            )
        )
    )
