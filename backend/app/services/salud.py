"""Lógica de negocio del pack salud / nutrición (E13).

Regla 1 hecha código: toda función recibe empresa_id y filtra por él SIEMPRE.
La ficha es 1:1 con el paciente; guardar_ficha hace upsert (crea o actualiza).
Antes de tocar la ficha, se valida que el paciente sea de ESTA empresa.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FichaClinica
from app.schemas.salud import FichaGuardar
from app.services import cliente as svc_cliente


def obtener_ficha(db: Session, empresa_id: int, cliente_id: int) -> FichaClinica | None:
    """Trae la ficha de un paciente, solo si es de ESTA empresa."""
    return db.scalar(
        select(FichaClinica).where(
            FichaClinica.cliente_id == cliente_id,
            FichaClinica.empresa_id == empresa_id,
        )
    )


def guardar_ficha(
    db: Session, empresa_id: int, cliente_id: int, datos: FichaGuardar
) -> FichaClinica | None:
    """Crea o actualiza la ficha del paciente (upsert).

    Devuelve None si el paciente no existe o es de otra empresa (el router
    lo traduce a 404). Solo se tocan los campos que el usuario envió.
    """
    # El paciente debe pertenecer a esta empresa (doble validación de aislamiento).
    if svc_cliente.obtener(db, empresa_id, cliente_id) is None:
        return None

    ficha = obtener_ficha(db, empresa_id, cliente_id)
    cambios = datos.model_dump(exclude_unset=True)

    if ficha is None:
        ficha = FichaClinica(empresa_id=empresa_id, cliente_id=cliente_id, **cambios)
        db.add(ficha)
    else:
        for campo, valor in cambios.items():
            setattr(ficha, campo, valor)

    db.commit()
    db.refresh(ficha)
    return ficha