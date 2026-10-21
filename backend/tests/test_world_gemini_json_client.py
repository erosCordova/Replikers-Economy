
"""Pruebas locales del proveedor JSON sin Internet."""

from types import SimpleNamespace

import pytest

from app.agentic.world_gemini_json_client import (
    GeminiJSONModel,
    GeminiJSONProviderError,
)
from app.agentic.world_gemini_governed import (
    parse_model_json,
)


class FakeModels:
    def __init__(self, text):
        self.text = text
        self.calls = 0
        self.configuration = None

    def generate_content(
        self,
        *,
        model,
        contents,
        config,
    ):
        self.calls += 1
        self.configuration = config

        return SimpleNamespace(text=self.text)


def test_01_enforces_json_response():
    provider = FakeModels('{"ok":true}')
    client = SimpleNamespace(models=provider)

    model = GeminiJSONModel(
        client,
        "gemini-2.5-flash-lite",
    )

    result = model.invoke("Genera JSON")

    assert parse_model_json(result) == {"ok": True}
    assert provider.calls == 1
    assert (
        provider.configuration.response_mime_type
        == "application/json"
    )


def test_02_empty_output_rejected():
    client = SimpleNamespace(
        models=FakeModels("")
    )

    model = GeminiJSONModel(
        client,
        "gemini-2.5-flash-lite",
    )

    with pytest.raises(GeminiJSONProviderError):
        model.invoke("Genera JSON")


def test_03_invalid_model_rejected():
    with pytest.raises(GeminiJSONProviderError):
        GeminiJSONModel(
            SimpleNamespace(),
            "../../modelo",
        )


def test_04_invalid_prompt_rejected():
    client = SimpleNamespace(
        models=FakeModels("{}")
    )

    model = GeminiJSONModel(
        client,
        "gemini-2.5-flash-lite",
    )

    with pytest.raises(GeminiJSONProviderError):
        model.invoke("")

    assert model.calls == 0
