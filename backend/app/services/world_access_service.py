
"""Autorizacion de propietarios para Replikers World.

Solo la autenticacion existente establece al usuario.

No se aceptan identificadores de propietario desde
parametros del cliente para decidir autorizaciones.

Este servicio no concede permisos a los agentes
para realizar pagos o transferencias.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.repliker import Repliker


def require_active_owner(user):
    if (
        user is None
        or getattr(user, "is_active", None) is not True
        or type(getattr(user, "id", None)) is not int
    ):
        raise HTTPException(
            status_code=401,
            detail="Usuario no autenticado o inactivo.",
        )

    return user


def require_owned_repliker(
    db: Session,
    user,
    repliker_id: int,
) -> Repliker:
    """Acceso exclusivamente al propietario autentico.

    Devuelve 404 tanto si el agente no existe como
    si pertenece a otro propietario. Esto evita
    revelar la existencia de agentes ajenos.
    """

    require_active_owner(user)

    if type(repliker_id) is not int or repliker_id <= 0:
        raise HTTPException(
            status_code=404,
            detail="Repliker no encontrado.",
        )

    agent = db.get(Repliker, repliker_id)

    if (
        agent is None
        or agent.owner_id != user.id
    ):
        raise HTTPException(
            status_code=404,
            detail="Repliker no encontrado.",
        )

    if not agent.is_active:
        raise HTTPException(
            status_code=403,
            detail="Repliker inactivo.",
        )

    return agent
