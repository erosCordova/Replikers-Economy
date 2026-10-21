
"""Puente de supervisor para economia FICTICIA aislada.

Prohibido su uso con dinero real o bases de produccion.
No inicia hilos de ejecucion continua.
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.agentic.world_economic_cycle import (
    run_simulated_owner_cycle,
    SimulatedCycleError,
)


class SimulatedEconomicRunner:
    def __init__(
        self,
        *,
        db_path,
        owner_id,
        idea_engine,
        response_engine,
    ):
        self.db_path = Path(db_path).resolve()
        self.owner_id = owner_id
        self.idea_engine = idea_engine
        self.response_engine = response_engine
        self.last_result = None

        if (
            self.db_path.parent.name != "replikers-world-backups"
            or not self.db_path.name.startswith("rw_economic_")
            or not self.db_path.is_file()
        ):
            raise SimulatedCycleError(
                "Runner restringido a una copia SQLite de ensayo"
            )

    def __call__(self, *args, **kwargs):
        engine = create_engine(
            URL.create(
                "sqlite",
                database=str(self.db_path),
            )
        )

        try:
            with Session(engine) as db:
                outcome = run_simulated_owner_cycle(
                    db,
                    owner_id=self.owner_id,
                    idea_engine=self.idea_engine,
                    response_engine=self.response_engine,
                )

            self.last_result = outcome

            return {
                "status": "settled",
                "result": outcome,
                "results": [
                    {
                        "repliker_id": outcome["seller_id"],
                        "status": "accepted",
                    }
                ],
                "events_inserted": 1,
            }
        finally:
            engine.dispose()

    def run(self, *args, **kwargs):
        return self(*args, **kwargs)

    def run_once(self, *args, **kwargs):
        return self(*args, **kwargs)

    def close(self):
        pass
