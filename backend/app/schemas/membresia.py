"""Schemas de membresías / abonos (E11)."""

import datetime as dt
from pydantic import BaseModel, Field

from app.models.enums import EstadoMembresia


# ===== PLAN DE ABONO (el molde) =====

class PlanAbonoBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=300)
    precio: float = Field(ge=0)
    ilimitado: bool = True
    cantidad_cupos: int | None = Field(default=None, ge=1)
    servicios_cubiertos: list[int] = Field(default_factory=list)


class PlanAbonoCrear(PlanAbonoBase):
    pass


class PlanAbonoEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    descripcion: str | None = Field(default=None, max_length=300)
    precio: float | None = Field(default=None, ge=0)
    ilimitado: bool | None = None
    cantidad_cupos: int | None = Field(default=None, ge=1)
    servicios_cubiertos: list[int] | None = None
    activo: bool | None = None


class PlanAbonoOut(PlanAbonoBase):
    id: int
    empresa_id: int
    activo: bool
    model_config = {"from_attributes": True}


# ===== MEMBRESÍA (el cliente que compra) =====

class MembresiaCrear(BaseModel):
    cliente_id: int
    plan_id: int
    fecha_desde: dt.date
    fecha_hasta: dt.date


class MembresiaOut(BaseModel):
    id: int
    empresa_id: int
    cliente_id: int
    plan_id: int
    fecha_desde: dt.date
    fecha_hasta: dt.date
    estado: EstadoMembresia
    cupos_usados: int

    # datos del plan resueltos (para mostrar sin otra consulta)
    plan_nombre: str | None = None
    plan_precio: float | None = None
    plan_ilimitado: bool | None = None

    # calculado: ¿está vigente hoy?
    vigente: bool = False

    model_config = {"from_attributes": True}