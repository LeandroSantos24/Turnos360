"""Schemas de estadísticas de facturación (lo cobrado de verdad, por período)."""

from pydantic import BaseModel


class MetodoTotal(BaseModel):
    metodo: str
    total: float


class ProfesionalTotal(BaseModel):
    recurso: str
    total: float
    turnos: int


class DiaTotal(BaseModel):
    fecha: str
    total: float


class EstadisticasFacturacion(BaseModel):
    """Facturación real de un período: cuánto entró, neto de comisiones, y desgloses."""

    facturado_real: float          # Σ de los pagos cobrados en el rango
    comision_total: float          # comisiones de los métodos de pago
    neto: float                    # facturado − comisiones
    cantidad_pagos: int
    ticket_promedio: float
    por_metodo: list[MetodoTotal]
    por_profesional: list[ProfesionalTotal]
    por_dia: list[DiaTotal]         # evolución diaria (para el gráfico)