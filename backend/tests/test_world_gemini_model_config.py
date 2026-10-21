
"""Pruebas de seleccion de modelo sin Google."""

import pytest

import app.agentic.world_gemini_governed as module


def configure_fake_runtime(monkeypatch):
    observed = []

    monkeypatch.setenv(
        "GOOGLE_API_KEY", "TEST_ONLY_NO_REAL"
    )

    monkeypatch.setenv(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    )

    def fake_model(api_key, model_name):
        observed.append(model_name)
        return object()

    def fake_run(db, **kwargs):
        return {
            "results": [],
            "events_inserted": 0,
            "real_money_used": False,
        }

    monkeypatch.setattr(
        module,
        "_create_gemini_model",
        fake_model,
    )

    monkeypatch.setattr(
        module,
        "run_governed_world_with_model",
        fake_run,
    )

    return observed


def test_01_uses_configured_model(monkeypatch):
    observed = configure_fake_runtime(monkeypatch)

    module.run_governed_world_with_gemini(
        None,
        round_id="config_test_001",
        allow_external_calls=True,
    )

    assert observed == ["gemini-3.5-flash-lite"]


def test_02_explicit_model_has_priority(monkeypatch):
    observed = configure_fake_runtime(monkeypatch)

    module.run_governed_world_with_gemini(
        None,
        round_id="config_test_002",
        model_name="gemini-3.8-flash",
        allow_external_calls=True,
    )

    assert observed == ["gemini-3.8-flash"]


def test_03_external_calls_need_permission(monkeypatch):
    observed = configure_fake_runtime(monkeypatch)

    with pytest.raises(
        module.WorldAIConfigurationError
    ):
        module.run_governed_world_with_gemini(
            None,
            round_id="config_test_003",
        )

    assert observed == []


def test_04_invalid_model_rejected(monkeypatch):
    observed = configure_fake_runtime(monkeypatch)

    with pytest.raises(
        module.WorldAIConfigurationError
    ):
        module.run_governed_world_with_gemini(
            None,
            round_id="config_test_004",
            model_name="../invalid-model",
            allow_external_calls=True,
        )

    assert observed == []
