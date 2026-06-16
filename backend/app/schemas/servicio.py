"""Schemas de Servicio: lo que cada negocio ofrece y reserva (E2)."""

from pydantic import BaseModel, Field


class ServicioBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    duracion_min: int = Field(gt=0, le=600, description="Minutos de atención activa")
    buffer_min: int = Field(default=0, ge=0, le=240, description="Tiempo muerto posterior")
    paso_turno_min: int = Field(default=15, gt=0, le=240, description="Cada cuánto se ofrecen turnos")
    grupo_agenda: str | None = Field(default=None, max_length=40, description="Carril de agenda: servicios del mismo grupo se bloquean entre sí")
    precio: float | None = Field(default=None, ge=0)


class ServicioCrear(ServicioBase):
    pass


class ServicioEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    duracion_min: int | None = Field(default=None, gt=0, le=600)
    buffer_min: int | None = Field(default=None, ge=0, le=240)
    paso_turno_min: int | None = Field(default=None, gt=0, le=240)
    grupo_agenda: str | None = Field(default=None, max_length=40)
    precio: float | None = Field(default=None, ge=0)
    activo: bool | None = None


class ServicioOut(ServicioBase):
    id: int
    empresa_id: int
    activo: bool

    model_config = {"from_attributes": True}


class ServiciosPagina(BaseModel):
    total: int
    items: list[ServicioOut]