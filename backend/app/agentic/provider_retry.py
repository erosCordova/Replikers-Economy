from __future__ import annotations

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


def is_quota_exhausted_error(
    exc: Exception,
) -> bool:
    """
    Detecta una cuota de larga duracion agotada.

    Este tipo de error NO debe provocar
    reintentos inmediatos.
    """

    text = str(exc).lower()

    return any(
        marker in text
        for marker
        in QUOTA_EXHAUSTED_MARKERS
    )


def is_transient_provider_error(
    exc: Exception,
) -> bool:
    """
    Identifica interrupciones del proveedor.

    Tambien puede devolver True para un 429
    de cuota, porque esa informacion sirve
    para recuperar artifacts producidos antes
    de que el proveedor interrumpiera el turno.

    invoke_with_transient_retry diferencia
    despues las cuotas largas para no insistir.
    """

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
    Reintenta errores temporales breves.

    Una cuota diaria agotada se devuelve
    inmediatamente al llamador.
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

            if (
                attempt >= max_attempts
                or not is_transient_provider_error(
                    exc
                )
            ):
                raise

            delay = (
                base_delay_seconds
                * (2 ** (attempt - 1))
            )

            sleep_fn(
                delay
            )

    raise RuntimeError(
        "Estado de reintento imposible."
    )
