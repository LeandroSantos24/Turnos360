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


class OrigenTotal(BaseModel):
    """De dónde salió la plata: atención, venta de abonos o de gift cards."""

    origen: str          # turno | abono | giftcard
    etiqueta: str
    total: float
    cantidad: int


class CuponRendimiento(BaseModel):
    """Cómo le fue a un código de descuento en el período."""

    codigo: str
    tipo: str            # porcentaje | monto
    valor: float
    activo: bool
    vence_el: str | None = None
    max_usos: int | None = None
    usos: int            # turnos que usaron el código
    personas: int        # clientes DISTINTOS que lo usaron
    facturado: float     # lo que facturaron esos turnos, ya con el descuento
    descuento_otorgado: float   # cuánta plata se regaló
    finalizados: int
    cancelados: int
    ausentes: int
    tasa_concrecion: float      # finalizados ÷ usos, en %


class CuponesResumen(BaseModel):
    usos: int = 0
    personas: int = 0
    facturado: float = 0.0
    descuento_otorgado: float = 0.0


class SucursalResumen(BaseModel):
    """Un local en la comparación. Solo se muestra con más de uno."""

    sucursal_id: int
    sucursal: str
    total: float
    cantidad_pagos: int
    turnos: int
    ticket: float
    pct: float


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

    # Facturación separada por origen. `facturado_turnos` es la parte de la
    # atención: es la que se usa para el ticket promedio, porque meter la
    # venta de un abono de $50.000 ahí adentro dejaría el número sin sentido.
    por_origen: list[OrigenTotal] = []
    facturado_turnos: float = 0.0

    # Rendimiento de los cupones de descuento del período.
    por_cupon: list[CuponRendimiento] = []
    cupones_resumen: CuponesResumen = CuponesResumen()

    # Comparación entre locales. Viene SIEMPRE con todos los locales, incluso
    # cuando el panel está filtrado a uno: filtrar la comparación sería sacarle
    # aquello con lo que se compara. Con un solo local trae una fila y el panel
    # no la muestra.
    por_sucursal: list[SucursalResumen] = []