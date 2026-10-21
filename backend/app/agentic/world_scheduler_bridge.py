"""Puente opt-in entre el planificador y el motor gobernado.
No inicia el servidor, IA externa ni tareas al importarse.
"""
import re
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker
from app.agentic.world_autonomous_scheduler import WorldScheduleConfig
from app.agentic.world_event_runtime import run_logged_governed_round

class WorldRunnerIsolationError(ValueError):
    pass

class GovernedSQLiteRunner:
    def __init__(self, *, config, db_path, allowed_directory,
                 idea_engine, response_engine, initiator_owner_id: int | None = None):
        if not isinstance(config, WorldScheduleConfig) or not config.enabled:
            raise WorldRunnerIsolationError('Controlador no autorizado.')
        if (config.economy_mode != 'simulation'
                or config.real_payments_enabled is not False
                or config.external_ai_enabled is not False):
            raise WorldRunnerIsolationError('Solo simulacion sin IA externa.')
        if not callable(idea_engine) or not callable(response_engine):
            raise WorldRunnerIsolationError('Motores invalidos.')

        allowed = Path(allowed_directory).resolve()
        target = Path(db_path).resolve()

        if (allowed.name != 'replikers-world-backups'
                or target.parent != allowed
                or not re.fullmatch(r'rw_bridge_[0-9a-f]{16}\.db', target.name)
                or not target.is_file()):
            raise WorldRunnerIsolationError('Base de ensayo no autorizada.')

        url = make_url(config.database_url)
        if (url.get_backend_name() != 'sqlite' or url.query
                or not url.database or Path(url.database).resolve() != target):
            raise WorldRunnerIsolationError('URL no coincide con copia SQLite.')

        with sqlite3.connect(target.as_uri() + '?mode=ro', uri=True) as db:
            db.execute('PRAGMA query_only=ON')
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise WorldRunnerIsolationError('Base SQLite no integra.')
            if db.execute('PRAGMA foreign_key_check').fetchall():
                raise WorldRunnerIsolationError('Claves foraneas invalidas.')
            tables = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            required = {'replikers', 'world_agent_events',
                        'world_agent_memories', 'world_agent_autonomy_policies',
                        'ledger_transactions'}
            if not required.issubset(tables):
                raise WorldRunnerIsolationError('Esquema World incompleto.')

        if initiator_owner_id is not None and (
            type(initiator_owner_id) is not int or initiator_owner_id <= 0
        ):
            raise WorldRunnerIsolationError("Propietario iniciador invalido.")
        self.initiator_owner_id = initiator_owner_id
        self.config = config
        self.database_path = target
        self.idea_engine = idea_engine
        self.response_engine = response_engine
        self.engine = create_engine(
            URL.create('sqlite', database=str(target)),
            connect_args={'timeout': 10},
        )
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    def __call__(self, *, round_id, max_agents):
        if (not isinstance(round_id, str) or
                re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9:_-]{7,79}', round_id) is None):
            raise WorldRunnerIsolationError('Identificador invalido.')
        if type(max_agents) is not int or max_agents != self.config.max_agents:
            raise WorldRunnerIsolationError('Cantidad de agentes no coincide.')
        with self.sessions() as db:
            try:
                result = run_logged_governed_round(
                    db, round_id=round_id,
                    idea_engine=self.idea_engine,
                    response_engine=self.response_engine,
                    max_agents=max_agents,
                    **({'initiator_owner_id': self.initiator_owner_id} if self.initiator_owner_id is not None else {}),
                )
                db.commit()
                return result
            except Exception:
                db.rollback()
                raise

    def close(self):
        self.engine.dispose()
