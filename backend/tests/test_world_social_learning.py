
"""Pruebas de aprendizaje social de Replikers World."""

import json
import os
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import (
    create_engine, event, func, select,
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.agentic.world_social_learning import (
    SocialLearningError,
    strategies,
    adoptions,
    publish_strategy,
    list_public_strategies,
    run_social_round,
)
from app.agentic.world_negotiation_graph import negotiations
from app.models.economy import LedgerTransaction


@pytest.fixture
def db(tmp_path):
    source = Path(os.environ["REPLIKERS_WORLD_TEST_DB"])
    destination = tmp_path / "social_test.db"

    with sqlite3.connect(
        source.resolve().as_uri() + "?mode=ro",
        uri=True,
    ) as original:
        with sqlite3.connect(str(destination)) as copy:
            original.backup(copy)

    engine = create_engine(
        URL.create(
            "sqlite+pysqlite",
            database=str(destination),
        )
    )

    @event.listens_for(engine, "connect")
    def enable_fk(connection, record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with Session(engine) as session:
        yield session
        session.rollback()

    engine.dispose()


def negotiation_of(db, author):
    return db.scalar(
        select(negotiations.c.id)
        .where(
            negotiations.c.proposer_repliker_id == author
        )
        .order_by(negotiations.c.id)
        .limit(1)
    )


def publish(db, author=2, engine=None):
    if engine is None:
        engine = lambda context: {
            "publish": True,
            "insight": (
                "Esta experiencia representa una "
                "negociacion observada, no beneficios."
            ),
        }

    return publish_strategy(
        db,
        negotiation_id=negotiation_of(db, author),
        acting_repliker_id=author,
        decision_engine=engine,
    )


def count(db, table):
    return db.scalar(
        select(func.count()).select_from(table)
    )


def idea(context):
    catalog = context["public_strategies"]
    peer = context["potential_counterparties"][0]

    return {
        "title": "Servicio adaptado de investigacion",
        "description": (
            "Preparar un nuevo informe digital "
            "utilizando una experiencia publica."
        ),
        "target_repliker_id": peer["repliker_id"],
        "price_cents": 2500,
        "estimated_cost_cents": 300,
        "inspired_by_strategy_ids": (
            [catalog[0]["strategy_id"]]
            if catalog else []
        ),
    }


def respond(context):
    return {
        "decision": "accept",
        "message": "Acepto evaluar esta iniciativa.",
    }


def run(db, round_id="social_001", generator=idea):
    return run_social_round(
        db,
        round_id=round_id,
        idea_engine=generator,
        response_engine=respond,
        max_agents=1,
    )


def test_01_author_can_publish(db):
    result = publish(db)
    assert result["status"] == "published"
    assert count(db, strategies) == 1


def test_02_publication_is_idempotent(db):
    first = publish(db)
    second = publish(db)

    assert second["status"] == "already_published"
    assert first["strategy_id"] == second["strategy_id"]
    assert count(db, strategies) == 1


def test_03_cannot_publish_someone_elses_history(db):
    with pytest.raises(SocialLearningError):
        publish_strategy(
            db,
            negotiation_id=negotiation_of(db, 2),
            acting_repliker_id=1,
            decision_engine=lambda ctx: {
                "publish": True,
                "insight": "Texto publicado por otro agente.",
            },
        )


def test_04_agent_can_decline_publication(db):
    result = publish(
        db,
        engine=lambda context: {
            "publish": False,
        },
    )

    assert result["status"] == "not_published"
    assert count(db, strategies) == 0


def test_05_short_insight_is_rejected(db):
    with pytest.raises(SocialLearningError):
        publish(
            db,
            engine=lambda context: {
                "publish": True,
                "insight": "Corto",
            },
        )


def test_06_public_catalog_excludes_own(db):
    publish(db, author=2)

    assert len(list_public_strategies(db, 1)) == 1
    assert len(list_public_strategies(db, 2)) == 0


def test_07_public_catalog_does_not_fake_profit(db):
    publish(db, author=2)
    item = list_public_strategies(db, 1)[0]

    assert item["verified_profit_cents"] is None
    assert "balance_cents" not in item
    assert "past_negotiations" not in item


def test_08_agent_adapts_public_strategy(db):
    publish(db, author=2)

    result = run(db)[0]

    assert result["status"] == "accepted"
    assert result["strategy_origin"] == "adapted"
    assert result["inspiration_count"] == 1
    assert count(db, adoptions) == 1


def test_09_adoption_has_provenance(db):
    published = publish(db, author=2)
    run(db)

    record = db.execute(
        select(adoptions)
    ).mappings().one()

    assert json.loads(
        record["source_ids_json"]
    ) == [published["strategy_id"]]


def test_10_agent_can_create_original_idea(db):
    result = run(db)[0]

    assert result["status"] == "accepted"
    assert result["strategy_origin"] == "original"
    assert result["inspiration_count"] == 0


def test_11_private_strategy_cannot_be_invented(db):
    def invalid(context):
        result = idea(context)
        result["inspired_by_strategy_ids"] = [999999]
        return result

    result = run(
        db,
        round_id="social_invalid",
        generator=invalid,
    )[0]

    assert result["status"] == "idea_not_ready"
    assert count(db, adoptions) == 0


def test_12_duplicate_inspiration_is_rejected(db):
    published = publish(db, author=2)

    def invalid(context):
        result = idea(context)
        value = published["strategy_id"]
        result["inspired_by_strategy_ids"] = [value, value]
        return result

    result = run(
        db,
        round_id="social_duplicates",
        generator=invalid,
    )[0]

    assert result["status"] == "idea_not_ready"


def test_13_replay_does_not_duplicate_adoption(db):
    publish(db, author=2)
    first = run(db, round_id="social_replay")
    second = run(db, round_id="social_replay")

    assert first[0]["status"] == "accepted"
    assert second[0]["status"] == "already_recorded"
    assert count(db, adoptions) == 1


def test_14_social_round_does_not_change_ledger(db):
    publish(db, author=2)

    before = count(db, LedgerTransaction.__table__)

    run(db, round_id="social_ledger")

    after = count(db, LedgerTransaction.__table__)
    assert before == after == 8


def test_15_genuine_peer_data_is_provided(db):
    publish(db, author=2)
    observed = []

    def capture(context):
        observed.append(context)
        return idea(context)

    run(
        db,
        round_id="social_context",
        generator=capture,
    )

    assert len(observed) == 1
    assert "economic_feedback" in observed[0]
    assert "past_negotiations" in observed[0]
    assert len(observed[0]["public_strategies"]) == 1
