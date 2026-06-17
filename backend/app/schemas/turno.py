"""Schemas de Turno: la reserva (E2).

Al crear, el cliente manda inicio + servicio; el sistema calcula fecha_fin
desde la duración del servicio y valida disponibilidad con el motor.
Al listar/ver, se devuelven datos relacionados (cliente, recurso, servicio)
para pintarlos en la agenda sin más consultas.
"""

import datetime as dt

from pydantic import BaseModel, Field

from app.models.enums import EstadoTurno, TipoTurno


class TurnoCrear(BaseModel):
    """Lo que se manda para reservar un turno.

    No se manda fecha_fin: la calcula el sistema desde la duración del servicio.
    Tampoco empresa_id (sale del token).
    """

    cliente_id: int
    recurso_id: int
    servicio_id: int
    fecha_inicio: dt.datetime
    tipo: TipoTurno = TipoTurno.SIMPLE
    categoria: str | None = Field(default=None, max_length=60)
    notas: str | None = None
    importe_previsto: float | None = None
    es_sobreturno: bool = False  # si es True, salta la validación de disponibilidad


class TurnoMover(BaseModel):
    """Reprogramar: nuevo horario y/o nuevo recurso."""

    fecha_inicio: dt.datetime
    recurso_id: int | None = None  # si cambia de profesional


class TurnoCambiarEstado(BaseModel):
    """Cambiar el estado del turno (confirmar, atender, cancelar...)."""

    estado: EstadoTurno
    motivo_cancelacion: str | None = Field(default=None, max_length=300)


class TurnoOut(BaseModel):
    """Lo que devuelve la API. Incluye nombres relacionados para la agenda."""

    id: int
    empresa_id: int
    cliente_id: int
    recurso_id: int
    servicio_id: int | None
    tipo: TipoTurno
    estado: EstadoTurno
    categoria: str | None
    fecha_inicio: dt.datetime | None
    fecha_fin: dt.datetime | None
    es_sobreturno: bool
    importe_previsto: float | None
    notas: str | None
    motivo_cancelacion: str | None

    # nombres resueltos (los llena el service para la agenda)
    cliente_nombre: str | None = None
    recurso_nombre: str | None = None
    servicio_nombre: str | None = None
    servicio_grupo: str | None = None  # carril del servicio (corte/tintura/barba)

    model_config = {"from_attributes": True}


class TurnosPagina(BaseModel):
    total: int
    items: list[TurnoOut]