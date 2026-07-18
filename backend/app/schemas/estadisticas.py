"""Schemas de estadísticas de facturación (lo cobrado de verdad, por período)."""

from pydantic import BaseModel


class MetodoTotal(BaseModel):
    metodo: str
    total: float


class ProfesionalTotal(BaseModel):
    recurso: str
    total: float
    turnos: int
    ticket: float = 0.0   # facturación ÷ turnos
    pct: float = 0.0      # % del total facturado


class DiaTotal(BaseModel):
    fecha: str
    total: float


class EstadosResumen(BaseModel):
    finalizados: int
    cancelados: int
    ausentes: int
    tasa_ausentismo: float  # ausentes / (finalizados + ausentes), en %


class ServicioTotal(BaseModel):
    servicio: str
    cantidad: int
    total: float


class HoraTotal(BaseModel):
    hora: int       # 0-23
    cantidad: int


class EstadisticasFacturacion(BaseModel):
    """Facturación real de un período: cuánto entró, neto de comisiones, y desgloses."""

    facturado_real: float          # Σ de los pagos cobrados en el rango
    facturado_anterior: float = 0.0  # mismo lapso anterior (para comparar)
    variacion_pct: float | None = None  # % vs período anterior
    comision_total: float          # comisiones de los métodos de pago
    neto: float                    # facturado − comisiones
    cantidad_pagos: int
    ticket_promedio: float
    por_metodo: list[MetodoTotal]
    por_profesional: list[ProfesionalTotal]
    por_dia: list[DiaTotal]         # evolución diaria (para el gráfico)
    estados: EstadosResumen
    por_servicio: list[ServicioTotal]
    por_hora: list[HoraTotal]