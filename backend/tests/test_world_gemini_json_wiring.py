
"""Pruebas de conexion Gemini JSON sin llamadas externas."""

from types import SimpleNamespace

import pytest

import app.agentic.world_gemini_governed as governed
import app.agentic.world_gemini_json_client as json_client


class FakeModels:
    def generate_content(self, **kwargs):
        assert kwargs["model"] == "gemini-3.5-flash-lite"
        assert (
            kwargs["config"].response_mime_type
            == "application/json"
        )
        return SimpleNamespace(
            text='{"estado":"OK"}'
        )


def test_01_factory_uses_json_sdk(monkeypatch):
    captured = []

    def fake_client(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(models=FakeModels())

    monkeypatch.setattr(
        json_client.genai,
        "Client",
        fake_client,
    )

    model = governed._create_gemini_model(
        "CLAVE_SOLO_PRUEBA",
        "gemini-3.5-flash-lite",
    )

    assert isinstance(
        model,
        json_client.GeminiJSONModel,
    )

    result = model.invoke(
        "Devuelve un JSON de ejemplo."
    )

    assert governed.parse_model_json(result) == {
        "estado": "OK"
    }

    assert len(captured) == 1


def test_02_stable_api_and_no_retries(monkeypatch):
    captured = []

    def fake_client(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(models=FakeModels())

    monkeypatch.setattr(
        json_client.genai,
        "Client",
        fake_client,
    )

    governed._create_gemini_model(
        "CLAVE_SOLO_PRUEBA",
        "gemini-3.5-flash-lite",
    )

    options = captured[0]["http_options"]

    assert captured[0]["vertexai"] is False
    assert options.api_version == "v1"
    assert options.timeout == 60000
    assert options.retry_options.attempts == 1


def test_03_configured_model_reaches_factory(monkeypatch):
    selected = []

    monkeypatch.setenv(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    )
    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "CLAVE_SOLO_PRUEBA",
    )
    monkeypatch.delenv(
        "GOOGLE_API_KEY",
        raising=False,
    )

    def fake_factory(api_key, model_name):
        selected.append(model_name)
        return object()

    monkeypatch.setattr(
        governed,
        "_create_gemini_model",
        fake_factory,
    )

    monkeypatch.setattr(
        governed,
        "run_governed_world_with_model",
        lambda db, **kwargs: {
            "results": [],
            "events_inserted": 0,
        },
    )

    governed.run_governed_world_with_gemini(
        None,
        round_id="json_wiring_test_001",
        allow_external_calls=True,
    )

    assert selected == ["gemini-3.5-flash-lite"]


def test_04_authorization_remains_required(monkeypatch):
    calls = []

    monkeypatch.setattr(
        governed,
        "_create_gemini_model",
        lambda *args: calls.append(args),
    )

    with pytest.raises(
        governed.WorldAIConfigurationError
    ):
        governed.run_governed_world_with_gemini(
            None,
            round_id="json_wiring_test_002",
        )

    assert calls == []
