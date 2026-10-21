
"""Cliente Google Gemini JSON para ejecutor World.

Solo genera respuestas de IA. No gestiona
dinero, permisos, contratos ni transferencias.

La validacion economica permanece en
world_gemini_governed y world_governed_runtime.
"""

import re
import threading
import time
from types import SimpleNamespace

from google import genai
from google.genai import types


class GeminiJSONProviderError(ValueError):
    pass


class GeminiQuotaBlocked(GeminiJSONProviderError):
    """Cuota agotada o enfriamiento local activo."""


class GeminiJSONModel:
    # Un bloqueo compartido entre instancias del proceso.
    _quota_lock = threading.Lock()
    _blocked_until = 0.0
    _cooldown_seconds = 900
    def __init__(self, client, model_name):
        if (
            not isinstance(model_name, str)
            or not re.fullmatch(
                r"gemini-[A-Za-z0-9._-]{3,80}",
                model_name,
            )
        ):
            raise GeminiJSONProviderError(
                "INVALID_MODEL_NAME"
            )

        self.client = client
        self.model_name = model_name
        self.calls = 0

    def invoke(self, prompt):
        if not isinstance(prompt, str) or not prompt:
            raise GeminiJSONProviderError(
                "INVALID_PROMPT"
            )

        if len(prompt) > 12000:
            raise GeminiJSONProviderError(
                "PROMPT_TOO_LARGE"
            )

        # Serializa las solicitudes de este proceso.
        # Si Google devuelve 429, no continua enviando
        # peticiones durante el periodo de enfriamiento.
        with GeminiJSONModel._quota_lock:
            remaining = (
                GeminiJSONModel._blocked_until
                - time.monotonic()
            )

            if remaining > 0:
                raise GeminiQuotaBlocked(
                    "GOOGLE_QUOTA_COOLDOWN_ACTIVE"
                )

            self.calls += 1

            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                        max_output_tokens=1024,
                    ),
                )

            except Exception as exc:
                status = getattr(exc, "code", None)

                if type(status) is not int:
                    status = getattr(
                        exc, "status_code", None
                    )

                if type(status) is not int:
                    response_obj = getattr(
                        exc, "response", None
                    )
                    status = getattr(
                        response_obj, "status_code", None
                    )

                if status == 429:
                    GeminiJSONModel._blocked_until = (
                        time.monotonic()
                        + GeminiJSONModel._cooldown_seconds
                    )

                    raise GeminiQuotaBlocked(
                        "GOOGLE_QUOTA_429_COOLDOWN_STARTED"
                    ) from None

                raise

        try:
            content = response.text
        except (AttributeError, ValueError):
            content = None

        if not isinstance(content, str):
            raise GeminiJSONProviderError(
                "JSON_RESPONSE_MISSING"
            )

        content = content.strip()

        if not content:
            raise GeminiJSONProviderError(
                "JSON_RESPONSE_EMPTY"
            )

        if len(content) > 6000:
            raise GeminiJSONProviderError(
                "JSON_RESPONSE_TOO_LONG"
            )

        return SimpleNamespace(content=content)


def create_google_json_model(api_key, model_name):
    """Cliente Gemini estable, JSON, un intento HTTP."""

    if not isinstance(api_key, str) or not api_key:
        raise GeminiJSONProviderError(
            "API_KEY_MISSING"
        )

    client = genai.Client(
        api_key=api_key,
        vertexai=False,
        http_options=types.HttpOptions(
            api_version="v1",
            timeout=60000,
            retry_options=types.HttpRetryOptions(
                attempts=1,
            ),
        ),
    )

    return GeminiJSONModel(
        client,
        model_name,
    )
