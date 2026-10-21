from __future__ import annotations

import re
import time

from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


TRANSIENT_PROVIDER_MARKERS = (
    "503",
    "high demand",
    "temporarily unavailable",
    "service unavailable",
    "429",
    "too many requests",
    "resource_exhausted",
    "resource exhausted",
    "deadline exceeded",
    "connection reset",
    "connection aborted",
    "connection timed out",
)


QUOTA_EXHAUSTED_MARKERS = (
    "exceeded your current quota",
    "quota exceeded",
    "free_tier_requests",
    "generaterequestsperday",
    "generate_content_free_tier_requests",
)


MAX_AUTOMATIC_PROVIDER_WAIT_SECONDS = 120.0


def provider_retry_after_seconds(
    exc: Exception,
) -> float | None:
    """
    Extrae del error del proveedor un tiempo
    corto de espera explícitamente recomendado.

    Ejemplos aceptados:
    - Please retry in 53.92s
    - retryDelay: '54s'

    Esperas superiores a dos minutos no se
    consideran recuperaciones inmediatas.
    """

    text = str(exc).lower()

    patterns = (
        r"retry\s+in\s+"
        r"([0-9]+(?:\.[0-9]+)?)s",
        r"retrydelay['\"]?\s*[:=]\s*"
        r"['\"]?([0-9]+(?:\.[0-9]+)?)s",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
        )

        if match is None:
            continue

        try:
            seconds = float(
                match.group(1)
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if (
            0.0 <= seconds
            <= MAX_AUTOMATIC_PROVIDER_WAIT_SECONDS
        ):
            return seconds

    return None


def is_quota_exhausted_error(
    exc: Exception,
) -> bool:
    """
    Una cuota que indica explícitamente
    'retry in Ns' es un rate limit temporal,
    no una cuota permanente agotada.
    """

    if (
        provider_retry_after_seconds(
            exc
        )
        is not None
    ):
        return False

    text = str(exc).lower()

    return any(
        marker in text
        for marker
        in QUOTA_EXHAUSTED_MARKERS
    )


def is_transient_provider_error(
    exc: Exception,
) -> bool:
    text = str(exc).lower()

    return any(
        marker in text
        for marker
        in TRANSIENT_PROVIDER_MARKERS
    )


def invoke_with_transient_retry(
    operation: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T:
    """
    Reintenta interrupciones temporales.

    Si Gemini informa una ventana concreta
    mediante 'retry in Ns', se respeta esa
    ventana en lugar de abortar inmediatamente.
    """

    if max_attempts < 1:
        raise ValueError(
            "max_attempts debe ser >= 1."
        )

    if base_delay_seconds < 0:
        raise ValueError(
            "base_delay_seconds no puede "
            "ser negativo."
        )

    for attempt in range(
        1,
        max_attempts + 1,
    ):
        try:
            return operation()

        except Exception as exc:
            if is_quota_exhausted_error(
                exc
            ):
                raise

            if not is_transient_provider_error(
                exc
            ):
                raise

            if attempt >= max_attempts:
                raise

            exponential_delay = (
                base_delay_seconds
                * (2 ** (attempt - 1))
            )

            provider_delay = (
                provider_retry_after_seconds(
                    exc
                )
            )

            if provider_delay is not None:
                delay = max(
                    exponential_delay,
                    provider_delay + 1.0,
                )

            else:
                delay = exponential_delay

            sleep_fn(
                delay
            )

    raise RuntimeError(
        "Estado de reintento imposible."
    )
