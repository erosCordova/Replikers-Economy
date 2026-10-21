
"""Pruebas de cuota Gemini sin conexiones externas."""

from types import SimpleNamespace

import pytest

from app.agentic.world_gemini_json_client import (
    GeminiJSONModel,
    GeminiQuotaBlocked,
)


class Fake429(Exception):
    code = 429


class Fake503(Exception):
    code = 503


class FakeModels:
    def __init__(self, error=None):
        self.error = error
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1

        if self.error is not None:
            raise self.error

        return SimpleNamespace(
            text='{"estado":"OK"}'
        )


@pytest.fixture(autouse=True)
def reset_cooldown():
    GeminiJSONModel._blocked_until = 0.0

    yield

    GeminiJSONModel._blocked_until = 0.0


def make_model(models):
    client = SimpleNamespace(models=models)

    return GeminiJSONModel(
        client,
        "gemini-3.5-flash-lite",
    )


def test_01_http_429_starts_cooldown():
    models = FakeModels(Fake429())

    model = make_model(models)

    with pytest.raises(GeminiQuotaBlocked):
        model.invoke("Genera JSON")

    assert models.calls == 1
    assert model.calls == 1
    assert GeminiJSONModel._blocked_until > 0


def test_02_repeated_request_does_not_call_google():
    models = FakeModels(Fake429())

    model = make_model(models)

    with pytest.raises(GeminiQuotaBlocked):
        model.invoke("Primera solicitud")

    with pytest.raises(
        GeminiQuotaBlocked,
        match="GOOGLE_QUOTA_COOLDOWN_ACTIVE",
    ):
        model.invoke("Segunda solicitud")

    assert models.calls == 1


def test_03_cooldown_is_shared_by_agents():
    first = FakeModels(Fake429())
    second = FakeModels()

    agent_one = make_model(first)
    agent_two = make_model(second)

    with pytest.raises(GeminiQuotaBlocked):
        agent_one.invoke("Agente 1")

    with pytest.raises(GeminiQuotaBlocked):
        agent_two.invoke("Agente 2")

    assert first.calls == 1
    assert second.calls == 0
    assert agent_two.calls == 0


def test_04_other_errors_and_success():
    failing = FakeModels(Fake503())
    model = make_model(failing)

    with pytest.raises(Fake503):
        model.invoke("Genera JSON")

    assert GeminiJSONModel._blocked_until == 0

    working = FakeModels()
    result = make_model(working).invoke(
        "Devuelve JSON correcto"
    )

    assert result.content == '{"estado":"OK"}'
    assert working.calls == 1
