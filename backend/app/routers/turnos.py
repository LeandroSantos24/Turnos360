"""Endpoints de turnos: la reserva (E2).

El service ya valida disponibilidad con el motor y controla las transiciones
de estado; acá solo exponemos esas operaciones por HTTP, atadas al guardián.
"""

import datetime as dt

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DB, EmpresaActual
from app.models.enums import EstadoTurno
from app.schemas.turno import (
    TurnoCambiarEstado,
    TurnoDescuento,
    TurnoCrear,
    TurnoMover,
    TurnoOut,
    TurnosPagina,
)
from app.services import turno as svc
from app.services import servicio as svc_servicio
from app.services.disponibilidad import calcular_huecos

router = APIRouter(prefix="/turnos", tags=["turnos"])

@router.get("/huecos", response_model=list[dt.datetime])
def buscar_huecos(
    empresa_id: EmpresaActual,
    db: DB,
    recurso_id: int = Query(..., description="Barbero a consultar"),
    fecha: dt.date = Query(..., description="Día a consultar (YYYY-MM-DD)"),
    servicio_id: int = Query(..., description="Servicio: define duración y carril"),
) -> list[dt.datetime]:
    """Horarios de inicio libres para ese servicio, ese día y ese barbero.

    Reutiliza el motor de disponibilidad: respeta franjas de trabajo,
    excepciones, buffer y el carril (grupo_agenda) del servicio.
    """
    servicio = svc_servicio.obtener(db, empresa_id, servicio_id)
    if servicio is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado"
        )
    return calcular_huecos(
        db,
        empresa_id,
        recurso_id,
        fecha,
        duracion_min=servicio.duracion_min,
        paso_min=servicio.paso_turno_min,
        grupo_agenda=servicio.grupo_agenda,
    )

@router.get("", response_model=TurnosPagina)
def listar_turnos(
    empresa_id: EmpresaActual,
    db: DB,
    recurso_id: int | None = Query(default=None, description="Filtrar por recurso (agenda de un barbero)"),
    cliente_id: int | None = Query(default=None, description="Filtrar por cliente (historial)"),
    desde: dt.datetime | None = Query(default=None, description="Turnos desde esta fecha/hora"),
    hasta: dt.datetime | None = Query(default=None, description="Turnos hasta esta fecha/hora"),
    estado: EstadoTurno | None = Query(default=None),
) -> TurnosPagina:
    """Lista turnos de la empresa, filtrables por recurso, rango y estado.

    Es la consulta que alimenta la vista de agenda.
    """
    total, items = svc.listar(
        db, empresa_id,
        recurso_id=recurso_id, cliente_id=cliente_id,
        desde=desde, hasta=hasta, estado=estado,
    )
    return TurnosPagina(total=total, items=items)


@router.get("/{turno_id}", response_model=TurnoOut)
def obtener_turno(turno_id: int, empresa_id: EmpresaActual, db: DB) -> TurnoOut:
    """Devuelve un turno por id. 404 si no existe o es de otra empresa."""
    turno = svc.obtener(db, empresa_id, turno_id)
    if turno is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno no encontrado")
    return turno


@router.post("", response_model=TurnoOut, status_code=status.HTTP_201_CREATED)
def crear_turno(datos: TurnoCrear, empresa_id: EmpresaActual, db: DB) -> TurnoOut:
    """Crea un turno validando disponibilidad. 409 si el horario no está libre."""
    return svc.crear(db, empresa_id, datos)


@router.patch("/{turno_id}/mover", response_model=TurnoOut)
def mover_turno(
    turno_id: int, datos: TurnoMover, empresa_id: EmpresaActual, db: DB
) -> TurnoOut:
    """Reprograma un turno (horario y/o recurso). 409 si el nuevo horario choca."""
    turno = svc.mover(db, empresa_id, turno_id, datos)
    if turno is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno no encontrado")
    return turno


@router.patch("/{turno_id}/estado", response_model=TurnoOut)
def cambiar_estado_turno(
    turno_id: int, datos: TurnoCambiarEstado, empresa_id: EmpresaActual, db: DB
) -> TurnoOut:
    """Cambia el estado del turno (confirmar, atender, cancelar...).

    409 si la transición no es válida (p. ej. finalizar un turno cancelado).
    """
    turno = svc.cambiar_estado(db, empresa_id, turno_id, datos)
    if turno is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno no encontrado")
    return turno


@router.patch("/{turno_id}/descuento", response_model=TurnoOut)
def aplicar_descuento_turno(
    turno_id: int, datos: TurnoDescuento, empresa_id: EmpresaActual, db: DB
) -> TurnoOut:
    """Aplica un % de descuento al turno (0-100)."""
    turno = svc.aplicar_descuento(db, empresa_id, turno_id, datos.descuento_pct)
    if turno is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turno no encontrado")
    return turno