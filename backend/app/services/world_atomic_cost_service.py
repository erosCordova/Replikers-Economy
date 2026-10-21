
"""Proteccion SQLite para gastos contractuales simultaneos.

Un gasto se valida y contabiliza manteniendo
un bloqueo de escritura BEGIN IMMEDIATE.

IMPORTANTE:
- Exclusivo para SQLite.
- Uso interno en modo simulacion.
- No sustituye autenticacion de agentes.
- No sustituye bloqueo de filas PostgreSQL.
- Todas las rutas que escriban gastos deben
  utilizar el mismo mecanismo para mantener
  esta garantia de serializacion.
"""

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.services.economy_service import (
    ensure_simulation_mode,
)

from app.services.world_cost_service import (
    record_contract_expense,
)


class AtomicCostError(ValueError):
    pass


def record_serialized_expense(
    engine: Engine,
    *,
    contract_id: int,
    acting_repliker_id: int,
    provider_repliker_id: int,
    amount_cents: int,
    expense_key: str,
    note: str,
    timeout_seconds: int = 25,
) -> dict:
    """Registrar un costo en una transaccion SQLite serializada.

    El identificador del actor debe provenir de una
    capa de autenticacion confiable; esta funcion
    por si sola no autentica usuarios.

    El bloqueo se obtiene antes de consultar los
    gastos ya registrados y el presupuesto restante.

    Unicamente confirma los cambios cuando toda
    la operacion ha finalizado sin excepciones.
    """

    ensure_simulation_mode()

    if not isinstance(engine, Engine):
        raise AtomicCostError(
            "Se requiere un motor SQLAlchemy."
        )

    if engine.dialect.name != "sqlite":
        raise AtomicCostError(
            "Este protector solo admite SQLite."
        )

    database_path = engine.url.database

    if database_path in (None, "", ":memory:"):
        raise AtomicCostError(
            "Se requiere una base SQLite de archivo."
        )

    if (
        type(timeout_seconds) is not int
        or not 1 <= timeout_seconds <= 60
    ):
        raise AtomicCostError(
            "Tiempo de espera invalido."
        )

    with engine.connect() as connection:
        connection.exec_driver_sql(
            "PRAGMA busy_timeout="
            + str(timeout_seconds * 1000)
        )

        connection.exec_driver_sql(
            "BEGIN IMMEDIATE"
        )

        db = Session(
            bind=connection,
            join_transaction_mode="rollback_only",
            expire_on_commit=False,
        )

        try:
            result = record_contract_expense(
                db,
                contract_id=contract_id,
                acting_repliker_id=acting_repliker_id,
                provider_repliker_id=provider_repliker_id,
                amount_cents=amount_cents,
                expense_key=expense_key,
                note=note,
            )

            db.flush()
            connection.commit()

            return dict(result)

        except Exception:
            connection.rollback()
            raise

        finally:
            db.close()
