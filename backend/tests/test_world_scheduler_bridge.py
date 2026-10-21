"""Pruebas del puente aislado, sin IA externa ni Supabase."""
import sqlite3
import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
import app.agentic.world_scheduler_bridge as bridge
from app.agentic.world_autonomous_scheduler import (
    WorldAutonomousScheduler, WorldScheduleConfig, WorldSchedulerError,
)

@pytest.fixture
def isolated(tmp_path):
    folder = tmp_path / 'replikers-world-backups'
    folder.mkdir()
    path = folder / 'rw_bridge_0123456789abcdef.db'
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE replikers (id INTEGER PRIMARY KEY);
            CREATE TABLE world_agent_events (id INTEGER PRIMARY KEY);
            CREATE TABLE world_agent_memories (id INTEGER PRIMARY KEY);
            CREATE TABLE world_agent_autonomy_policies (id INTEGER PRIMARY KEY);
            CREATE TABLE ledger_transactions (id INTEGER PRIMARY KEY);
            CREATE TABLE runner_audit (id INTEGER PRIMARY KEY, round_id TEXT);
        """)
    config = WorldScheduleConfig(
        database_url=str(URL.create('sqlite', database=str(path))),
        enabled=True, max_agents=1, interval_seconds=600,
    )
    return folder, path, config

def build(isolated, **kw):
    folder, path, config = isolated
    return bridge.GovernedSQLiteRunner(
        config=kw.get('config', config),
        db_path=kw.get('db_path', path),
        allowed_directory=folder,
        idea_engine=lambda **k: {}, response_engine=lambda **k: {},
    )

def test_01_governed_runtime_uses_isolated_session(monkeypatch, isolated):
    def fake_round(db, **kw):
        db.execute(text('INSERT INTO runner_audit(round_id) VALUES (:id)'),
                   {'id': kw['round_id']})
        return {'results': [], 'events_inserted': 1}
    monkeypatch.setattr(bridge, 'run_logged_governed_round', fake_round)
    runner = build(isolated)
    try:
        result = runner(round_id='world_bridge_0001', max_agents=1)
        assert result['events_inserted'] == 1
    finally:
        runner.close()
    with sqlite3.connect(isolated[1]) as db:
        assert db.execute('SELECT COUNT(*) FROM runner_audit').fetchone()[0] == 1

def test_02_remote_database_rejected():
    with pytest.raises(WorldSchedulerError):
        WorldScheduleConfig(database_url='postgresql://localhost/db', enabled=True)

def test_03_main_database_outside_backup_rejected(isolated, tmp_path):
    main = tmp_path / 'replikers.db'
    main.write_bytes(isolated[1].read_bytes())
    with pytest.raises(bridge.WorldRunnerIsolationError):
        build(isolated, db_path=main)

def test_04_wrong_filename_rejected(isolated):
    wrong = isolated[0] / 'replikers.db'
    wrong.write_bytes(isolated[1].read_bytes())
    with pytest.raises(bridge.WorldRunnerIsolationError):
        build(isolated, db_path=wrong)

def test_05_url_path_mismatch_rejected(isolated):
    other = isolated[0] / 'rw_bridge_ffffffffffffffff.db'
    other.write_bytes(isolated[1].read_bytes())
    config = WorldScheduleConfig(
        database_url=str(URL.create('sqlite', database=str(other))), enabled=True,
    )
    with pytest.raises(bridge.WorldRunnerIsolationError):
        build(isolated, config=config)

def test_06_disabled_configuration_rejected(isolated):
    config = WorldScheduleConfig(database_url=isolated[2].database_url, enabled=False)
    with pytest.raises(bridge.WorldRunnerIsolationError):
        build(isolated, config=config)

def test_07_failed_round_rolls_back(monkeypatch, isolated):
    def failing_round(db, **kw):
        db.execute(text("INSERT INTO runner_audit(round_id) VALUES ('fallo')"))
        raise RuntimeError('Fallo simulado')
    monkeypatch.setattr(bridge, 'run_logged_governed_round', failing_round)
    runner = build(isolated)
    try:
        with pytest.raises(RuntimeError):
            runner(round_id='world_bridge_fail', max_agents=1)
    finally:
        runner.close()
    with sqlite3.connect(isolated[1]) as db:
        assert db.execute('SELECT COUNT(*) FROM runner_audit').fetchone()[0] == 0

def test_08_scheduler_calls_governed_bridge(monkeypatch, isolated):
    monkeypatch.setattr(bridge, 'run_logged_governed_round',
        lambda db, **kw: {'events_inserted': 0, 'round_id': kw['round_id']})
    runner = build(isolated)
    try:
        scheduler = WorldAutonomousScheduler(config=isolated[2], runner=runner)
        result = scheduler.run_once()
        assert result['status'] == 'executed'
        assert result['round_id'].startswith('world_auto_')
        assert result['result']['events_inserted'] == 0
        assert scheduler.executed == 1 and scheduler.running is False
    finally:
        runner.close()
