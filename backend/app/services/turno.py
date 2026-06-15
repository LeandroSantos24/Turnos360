"""Lógica de negocio de Turno (E2) — usa el motor de disponibilidad.

Al crear o mover un turno, se valida el hueco con esta_disponible() del motor
ANTES de guardar (salvo que sea sobreturno). Las transiciones de estado
siguen un flujo válido (no se puede finalizar un turno cancelado, etc.).

Regla 1: todo se filtra por empresa_id, igual que los demás services.
"""

import datetime as dt

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Cliente, Recurso, Servicio, Turno
from app.models.enums import EstadoTurno
from app.schemas.turno import TurnoCambiarEstado, TurnoCrear, TurnoMover
from app.services import disponibilidad as disp

# Transiciones de estado permitidas. Desde cada estado, a cuáles se puede pasar.
TRANSICIONES = {
    EstadoTurno.PENDIENTE: {EstadoTurno.CONFIRMADO, EstadoTurno.CANCELADO, EstadoTurno.AUSENTE},
    EstadoTurno.CONFIRMADO: {EstadoTurno.EN_CURSO, EstadoTurno.CANCELADO, EstadoTurno.AUSENTE},
    EstadoTurno.EN_CURSO: {EstadoTurno.FINALIZADO, EstadoTurno.CANCELADO},
    EstadoTurno.FINALIZADO: set(),   # estado terminal
    EstadoTurno.CANCELADO: set(),    # estado terminal
    EstadoTurno.AUSENTE: set(),      # estado terminal
}


def _entidad_de_empresa(db, modelo, entidad_id: int, empresa_id: int):
    """Trae una entidad (Cliente/Recurso/Servicio) solo si es de esta empresa."""
    return db.scalar(
        select(modelo).where(modelo.id == entidad_id, modelo.empresa_id == empresa_id)
    )


def _resolver_nombres(db: Session, turno: Turno) -> Turno:
    """Adjunta cliente_nombre, recurso_nombre y servicio_nombre al objeto turno.

    No son columnas: los seteamos como atributos para que el schema TurnoOut
    los incluya en la respuesta (útil para pintar la agenda sin más consultas).
    """
    cliente = db.get(Cliente, turno.cliente_id)
    recurso = db.get(Recurso, turno.recurso_id)
    servicio = db.get(Servicio, turno.servicio_id) if turno.servicio_id else None
    turno.cliente_nombre = (
        f"{cliente.nombre} {cliente.apellido or ''}".strip() if cliente else None
    )
    turno.recurso_nombre = recurso.nombre if recurso else None
    turno.servicio_nombre = servicio.nombre if servicio else None
    return turno


def listar(
    db: Session,
    empresa_id: int,
    *,
    recurso_id: int | None = None,
    cliente_id: int | None = None,
    desde: dt.datetime | None = None,
    hasta: dt.datetime | None = None,
    estado: EstadoTurno | None = None,
) -> tuple[int, list[Turno]]:
    """Lista turnos de la empresa, filtrables por recurso, rango de fechas y estado.

    Es el corazón de la vista de agenda: 'dame los turnos de Juan esta semana'.
    """
    condiciones = [Turno.empresa_id == empresa_id]
    if recurso_id is not None:
        condiciones.append(Turno.recurso_id == recurso_id)
    if cliente_id is not None:
        condiciones.append(Turno.cliente_id == cliente_id)
    if desde is not None:
        condiciones.append(Turno.fecha_inicio >= desde)
    if hasta is not None:
        condiciones.append(Turno.fecha_inicio < hasta)
    if estado is not None:
        condiciones.append(Turno.estado == estado)

    total = db.scalar(select(func.count()).select_from(Turno).where(*condiciones))
    turnos = list(
        db.scalars(
            select(Turno).where(*condiciones).order_by(Turno.fecha_inicio)
        )
    )
    for t in turnos:
        _resolver_nombres(db, t)
    return total or 0, turnos


def obtener(db: Session, empresa_id: int, turno_id: int) -> Turno | None:
    """Trae un turno por id, solo si es de esta empresa, con nombres resueltos."""
    turno = db.scalar(
        select(Turno).where(Turno.id == turno_id, Turno.empresa_id == empresa_id)
    )
    return _resolver_nombres(db, turno) if turno else None


def crear(db: Session, empresa_id: int, datos: TurnoCrear) -> Turno:
    """Crea un turno validando disponibilidad con el motor (salvo sobreturno).

    Pasos: valida que cliente/recurso/servicio sean de la empresa → calcula
    fecha_fin desde la duración del servicio → pregunta al motor si el hueco
    está libre → si lo está (o es sobreturno), guarda.
    """
    # 1. Las tres entidades deben ser de esta empresa (Regla 1)
    cliente = _entidad_de_empresa(db, Cliente, datos.cliente_id, empresa_id)
    if cliente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado")
    recurso = _entidad_de_empresa(db, Recurso, datos.recurso_id, empresa_id)
    if recurso is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurso no encontrado")
    servicio = _entidad_de_empresa(db, Servicio, datos.servicio_id, empresa_id)
    if servicio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no encontrado")

    # 2. El sistema calcula la fecha de fin (no la manda el cliente)
    fecha_fin = datos.fecha_inicio + dt.timedelta(minutes=servicio.duracion_min)

    # 3. Validar disponibilidad con el motor (salvo que sea sobreturno)
    if not datos.es_sobreturno:
        libre = disp.esta_disponible(
            db, empresa_id, datos.recurso_id, datos.fecha_inicio, fecha_fin
        )
        if not libre:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "El horario no está disponible (fuera de agenda, bloqueado o ya ocupado)",
            )

    # 4. Crear el turno
    turno = Turno(
        empresa_id=empresa_id,
        cliente_id=datos.cliente_id,
        recurso_id=datos.recurso_id,
        servicio_id=datos.servicio_id,
        tipo=datos.tipo,
        estado=EstadoTurno.PENDIENTE,
        categoria=datos.categoria,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=fecha_fin,
        es_sobreturno=datos.es_sobreturno,
        importe_previsto=datos.importe_previsto if datos.importe_previsto is not None else servicio.precio,
        notas=datos.notas,
    )
    db.add(turno)
    db.commit()
    db.refresh(turno)
    return _resolver_nombres(db, turno)


def mover(
    db: Session, empresa_id: int, turno_id: int, datos: TurnoMover
) -> Turno | None:
    """Reprograma un turno (nuevo horario y/o recurso), revalidando disponibilidad.

    Excluye el propio turno del chequeo (si no, chocaría consigo mismo).
    """
    turno = db.scalar(
        select(Turno).where(Turno.id == turno_id, Turno.empresa_id == empresa_id)
    )
    if turno is None:
        return None

    nuevo_recurso_id = datos.recurso_id or turno.recurso_id
    if datos.recurso_id is not None:
        # si cambia de recurso, validar que el nuevo sea de la empresa
        if _entidad_de_empresa(db, Recurso, datos.recurso_id, empresa_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Recurso no encontrado")

    # recalcular duración a partir del servicio (la misma de antes)
    duracion = (turno.fecha_fin - turno.fecha_inicio) if turno.fecha_fin else dt.timedelta(minutes=30)
    nueva_fin = datos.fecha_inicio + duracion

    # validar el nuevo hueco, excluyendo este mismo turno
    if not turno.es_sobreturno:
        libre = disp.esta_disponible(
            db, empresa_id, nuevo_recurso_id, datos.fecha_inicio, nueva_fin,
            excluir_turno_id=turno.id,
        )
        if not libre:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "El nuevo horario no está disponible",
            )

    turno.fecha_inicio = datos.fecha_inicio
    turno.fecha_fin = nueva_fin
    turno.recurso_id = nuevo_recurso_id
    db.commit()
    db.refresh(turno)
    return _resolver_nombres(db, turno)


def cambiar_estado(
    db: Session, empresa_id: int, turno_id: int, datos: TurnoCambiarEstado
) -> Turno | None:
    """Cambia el estado del turno respetando las transiciones válidas."""
    turno = db.scalar(
        select(Turno).where(Turno.id == turno_id, Turno.empresa_id == empresa_id)
    )
    if turno is None:
        return None

    # ¿La transición es válida? (no se puede finalizar un cancelado, etc.)
    permitidos = TRANSICIONES[turno.estado]
    if datos.estado not in permitidos:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede pasar de '{turno.estado.value}' a '{datos.estado.value}'",
        )

    turno.estado = datos.estado
    if datos.estado == EstadoTurno.CANCELADO and datos.motivo_cancelacion:
        turno.motivo_cancelacion = datos.motivo_cancelacion
    db.commit()
    db.refresh(turno)
    return _resolver_nombres(db, turno)