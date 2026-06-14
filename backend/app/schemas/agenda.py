"""Schemas de disponibilidad: horarios y excepciones de un recurso (E2).

- Horario: franja recurrente semanal (ej: lunes 9-19). Lo que el recurso SÍ trabaja.
- Excepción: bloqueo puntual por fechas (feriado, licencia, vacaciones, bloqueo).
  Lo que se RESTA del horario base.
"""

import datetime as dt

from pydantic import BaseModel, Field, model_validator

from app.models.enums import TipoExcepcion


# ---------- Horarios ----------

class HorarioCrear(BaseModel):
    """Una franja de atención semanal de un recurso."""

    dia_semana: int = Field(ge=0, le=6, description="0=lunes … 6=domingo")
    hora_desde: dt.time
    hora_hasta: dt.time
    vigencia_desde: dt.date | None = None
    vigencia_hasta: dt.date | None = None

    @model_validator(mode="after")
    def _validar_rango(self) -> "HorarioCrear":
        """La hora de fin debe ser posterior a la de inicio."""
        if self.hora_hasta <= self.hora_desde:
            raise ValueError("hora_hasta debe ser posterior a hora_desde")
        return self


class HorarioOut(BaseModel):
    id: int
    recurso_id: int
    dia_semana: int
    hora_desde: dt.time
    hora_hasta: dt.time
    vigencia_desde: dt.date | None
    vigencia_hasta: dt.date | None

    model_config = {"from_attributes": True}


# ---------- Excepciones ----------

class ExcepcionCrear(BaseModel):
    """Un bloqueo por rango de fechas. recurso_id NULL = toda la empresa (feriado)."""

    tipo: TipoExcepcion
    fecha_desde: dt.date
    fecha_hasta: dt.date
    motivo: str | None = Field(default=None, max_length=200)
    recurso_id: int | None = None  # NULL = aplica a toda la empresa

    @model_validator(mode="after")
    def _validar_rango(self) -> "ExcepcionCrear":
        if self.fecha_hasta < self.fecha_desde:
            raise ValueError("fecha_hasta no puede ser anterior a fecha_desde")
        return self


class ExcepcionOut(BaseModel):
    id: int
    recurso_id: int | None
    tipo: TipoExcepcion
    fecha_desde: dt.date
    fecha_hasta: dt.date
    motivo: str | None

    model_config = {"from_attributes": True}