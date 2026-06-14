"""Lógica de horarios y excepciones de agenda (E2).

Regla 1: toda operación valida que el recurso pertenezca a la empresa ANTES
de tocar su horario. Las excepciones con recurso_id NULL (feriados de toda
la empresa) llevan empresa_id directo.

Este service es la base sobre la que E2-final monta el cálculo de disponibilidad.
"""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExcepcionAgenda, HorarioRecurso, Recurso
from app.schemas.agenda import ExcepcionCrear, HorarioCrear


def _recurso_de_empresa(db: Session, empresa_id: int, recurso_id: int) -> Recurso | None:
    """Devuelve el recurso solo si es de esta empresa (guardia de la Regla 1)."""
    return db.scalar(
        select(Recurso).where(
            Recurso.id == recurso_id, Recurso.empresa_id == empresa_id
        )
    )


# ---------- Horarios ----------

def listar_horarios(
    db: Session, empresa_id: int, recurso_id: int
) -> list[HorarioRecurso] | None:
    """Horarios de un recurso. None si el recurso no es de esta empresa."""
    if _recurso_de_empresa(db, empresa_id, recurso_id) is None:
        return None
    return list(
        db.scalars(
            select(HorarioRecurso)
            .where(
                HorarioRecurso.empresa_id == empresa_id,
                HorarioRecurso.recurso_id == recurso_id,
            )
            .order_by(HorarioRecurso.dia_semana, HorarioRecurso.hora_desde)
        )
    )


def agregar_horario(
    db: Session, empresa_id: int, recurso_id: int, datos: HorarioCrear
) -> HorarioRecurso | None:
    """Agrega una franja al recurso. None si el recurso no es de esta empresa."""
    if _recurso_de_empresa(db, empresa_id, recurso_id) is None:
        return None
    horario = HorarioRecurso(
        empresa_id=empresa_id, recurso_id=recurso_id, **datos.model_dump()
    )
    db.add(horario)
    db.commit()
    db.refresh(horario)
    return horario


def eliminar_horario(
    db: Session, empresa_id: int, horario_id: int
) -> bool:
    """Borra una franja (sí se borra físicamente: no tiene historial asociado)."""
    horario = db.scalar(
        select(HorarioRecurso).where(
            HorarioRecurso.id == horario_id,
            HorarioRecurso.empresa_id == empresa_id,
        )
    )
    if horario is None:
        return False
    db.delete(horario)
    db.commit()
    return True


# ---------- Excepciones ----------

def listar_excepciones(
    db: Session, empresa_id: int, *, desde: dt.date | None = None
) -> list[ExcepcionAgenda]:
    """Excepciones de la empresa (de todos los recursos + las generales).

    Opcionalmente solo las que terminan de 'desde' en adelante (las vigentes).
    """
    condiciones = [ExcepcionAgenda.empresa_id == empresa_id]
    if desde:
        condiciones.append(ExcepcionAgenda.fecha_hasta >= desde)
    return list(
        db.scalars(
            select(ExcepcionAgenda)
            .where(*condiciones)
            .order_by(ExcepcionAgenda.fecha_desde)
        )
    )


def agregar_excepcion(
    db: Session, empresa_id: int, datos: ExcepcionCrear
) -> ExcepcionAgenda | None:
    """Agrega un bloqueo. Si trae recurso_id, valida que sea de esta empresa.

    recurso_id NULL = excepción de toda la empresa (un feriado, p. ej.).
    """
    if datos.recurso_id is not None:
        if _recurso_de_empresa(db, empresa_id, datos.recurso_id) is None:
            return None
    excepcion = ExcepcionAgenda(empresa_id=empresa_id, **datos.model_dump())
    db.add(excepcion)
    db.commit()
    db.refresh(excepcion)
    return excepcion


def eliminar_excepcion(db: Session, empresa_id: int, excepcion_id: int) -> bool:
    """Borra una excepción de esta empresa."""
    excepcion = db.scalar(
        select(ExcepcionAgenda).where(
            ExcepcionAgenda.id == excepcion_id,
            ExcepcionAgenda.empresa_id == empresa_id,
        )
    )
    if excepcion is None:
        return False
    db.delete(excepcion)
    db.commit()
    return True