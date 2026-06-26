"""Schemas de finanzas (E10): métodos de pago, cobros, caja, gastos.

Construido sobre las tablas que ya existen en app/models/finanzas.py.
"""

import datetime as dt

from pydantic import BaseModel, Field

from app.models.enums import EstadoCaja, TipoMovimiento


# ─────────────────────────── Métodos de pago (N-53, N-55) ───────────────────

class MetodoPagoCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    comision_pct: float = Field(default=0, ge=0, le=100)


class MetodoPagoEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    comision_pct: float | None = Field(default=None, ge=0, le=100)
    activo: bool | None = None


class MetodoPagoOut(BaseModel):
    id: int
    nombre: str
    comision_pct: float
    activo: bool

    model_config = {"from_attributes": True}


# ─────────────────────────── Categorías de gasto (N-56) ─────────────────────

class CategoriaCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    tipo: TipoMovimiento = TipoMovimiento.EGRESO


class CategoriaOut(BaseModel):
    id: int
    nombre: str
    tipo: TipoMovimiento

    model_config = {"from_attributes": True}


# ─────────────────────────── Cobro de un turno (N-52, N-54) ─────────────────

class PagoLinea(BaseModel):
    """Una porción del cobro con un método (permite pago dividido)."""

    metodo_pago_id: int | None = None
    monto: float = Field(gt=0)


class CobroCrear(BaseModel):
    """Registrar el cobro de un turno: una o varias líneas de pago."""

    pagos: list[PagoLinea] = Field(min_length=1)


class PagoOut(BaseModel):
    id: int
    turno_id: int | None
    cliente_id: int
    metodo_pago_id: int | None
    metodo_pago_nombre: str | None = None
    monto: float
    comision_aplicada: float | None
    fecha: dt.datetime

    model_config = {"from_attributes": True}


class CobroOut(BaseModel):
    """Resultado de un cobro: lo cobrado, la comisión y el neto."""

    turno_id: int
    total_cobrado: float
    total_comision: float
    neto: float
    pagos: list[PagoOut]


# ─────────────────────────── Caja (N-50, N-51) ──────────────────────────────

class CajaAbrir(BaseModel):
    saldo_inicial: float = Field(default=0, ge=0)
    observaciones: str | None = Field(default=None, max_length=300)


class CajaCerrar(BaseModel):
    saldo_real: float = Field(ge=0)  # lo que hay físicamente al cerrar
    observaciones: str | None = Field(default=None, max_length=300)


class CajaOut(BaseModel):
    id: int
    fecha_apertura: dt.datetime
    fecha_cierre: dt.datetime | None
    saldo_inicial: float
    saldo_final: float | None
    estado: EstadoCaja

    model_config = {"from_attributes": True}


class MetodoResumen(BaseModel):
    """Cuánto entró por cada método de pago (arqueo: dónde está la plata)."""

    metodo: str
    total: float


class CajaResumen(BaseModel):
    """Cifras de la caja (para el cierre): ingresos, egresos, esperado, diferencia."""

    caja: CajaOut
    total_ingresos: float
    total_egresos: float
    saldo_esperado: float           # saldo_inicial + ingresos − egresos
    saldo_real: float | None = None # lo cargado al cerrar
    diferencia: float | None = None # real − esperado
    cantidad_movimientos: int
    por_metodo: list[MetodoResumen] = []


# ─────────────────────────── Gastos (N-56) ──────────────────────────────────

class CajaDetalle(BaseModel):
    """Una caja con su resumen y sus movimientos (para imprimir el cierre)."""

    resumen: CajaResumen
    movimientos: list["MovimientoOut"]


class GastoCrear(BaseModel):
    concepto: str = Field(min_length=1, max_length=120)
    monto: float = Field(gt=0)
    categoria_id: int | None = None
    metodo_pago_id: int | None = None
    descripcion: str | None = Field(default=None, max_length=300)


class MovimientoOut(BaseModel):
    id: int
    fecha: dt.datetime
    tipo: TipoMovimiento
    concepto: str | None
    descripcion: str | None
    monto: float
    metodo_pago_id: int | None
    metodo_pago: str | None = None  # nombre resuelto por el service
    categoria_id: int | None

    model_config = {"from_attributes": True}


# ─────────────────────────── Historial comercial (N-62) ─────────────────────

class CobradoCliente(BaseModel):
    """Total realmente cobrado a un cliente (suma de sus pagos)."""

    total_cobrado: float
    cantidad_pagos: int