import inspect
import os
import re
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agentic import world_scheduler_bridge as bridge
from app.agentic.world_autonomy_runtime import (
    available_agents,
    WorldAutonomyError,
)
from app.agentic.world_social_learning import run_social_round
from app.agentic.world_governed_runtime import run_governed_social_round
from app.agentic.world_event_runtime import run_logged_governed_round
from app.agentic.world_scheduler_bridge import GovernedSQLiteRunner
from app.models.repliker import Repliker


class Capture:
    def scalars(self, query):
        self.query = query
        return SimpleNamespace(all=lambda: [])


def sql(c):
    return str(c.query.compile(
        compile_kwargs={"literal_binds": True}
    ))


def test_sql_owner():
    c = Capture()

    available_agents(
        c, limit=3, initiator_owner_id=4
    )

    assert re.search(
        r"\bowner_id\s*=\s*4\b", sql(c)
    )


def test_default_compatible():
    c = Capture()
    available_agents(c, limit=3)

    assert not re.search(
        r"\bowner_id\s*=", sql(c)
    )


@pytest.mark.parametrize("bad", [0, -1, True, "4"])
def test_invalid_owner(bad):
    with pytest.raises(WorldAutonomyError):
        available_agents(
            Capture(),
            limit=3,
            initiator_owner_id=bad,
        )


def test_scope_signatures():
    for function in (
        available_agents,
        run_social_round,
        run_governed_social_round,
        run_logged_governed_round,
        GovernedSQLiteRunner.__init__,
    ):
        assert "initiator_owner_id" in (
            inspect.signature(function).parameters
        )


class Context:
    def __enter__(self):
        return SimpleNamespace(
            commit=lambda: None,
            rollback=lambda: None,
        )

    def __exit__(self, *args):
        return False


@pytest.mark.parametrize("owner", [4, None])
def test_bridge_passes_scope(monkeypatch, owner):
    seen = {}

    def stub(db, **kwargs):
        seen.update(kwargs)

        return {
            "results": [],
            "payments_executed": False,
        }

    monkeypatch.setattr(
        bridge,
        "run_logged_governed_round",
        stub,
    )

    runner = object.__new__(GovernedSQLiteRunner)
    runner.config = SimpleNamespace(max_agents=1)
    runner.sessions = lambda: Context()
    runner.idea_engine = lambda x: x
    runner.response_engine = lambda x: x
    runner.initiator_owner_id = owner

    result = runner(
        round_id="owner_scope_01",
        max_agents=1,
    )

    assert result["payments_executed"] is False

    if owner is None:
        assert "initiator_owner_id" not in seen
    else:
        assert seen["initiator_owner_id"] == owner


def test_sqlite_owned():
    path = os.environ[
        "REPLIKERS_WORLD_TEST_DB"
    ].replace("\\", "/")

    engine = create_engine("sqlite:///" + path)

    try:
        with Session(engine) as db:
            ids = available_agents(db, limit=50)
            assert ids

            owner = int(
                db.get(Repliker, ids[0]).owner_id
            )

            selected = available_agents(
                db,
                limit=50,
                initiator_owner_id=owner,
            )

            assert selected

            assert all(
                int(db.get(Repliker, x).owner_id)
                == owner
                for x in selected
            )
    finally:
        engine.dispose()


def test_no_agents_other_owner():
    path = os.environ[
        "REPLIKERS_WORLD_TEST_DB"
    ].replace("\\", "/")

    engine = create_engine("sqlite:///" + path)

    try:
        with Session(engine) as db:
            owners = db.scalars(
                select(Repliker.owner_id)
            ).all()

            assert owners

            unknown = (
                max(int(x) for x in owners)
                + 1000
            )

            assert available_agents(
                db,
                limit=50,
                initiator_owner_id=unknown,
            ) == []
    finally:
        engine.dispose()
