"""Schemas de Turno: la reserva (E2).
Al crear, el cliente manda inicio + servicio; el sistema calcula fecha_fin
desde la duración del servicio y valida disponibilidad con el motor.
Al listar/ver, se devuelven datos relacionados (cliente, recurso, servicio)
para pintarlos en la agenda sin más consultas.
"""
import datetime as dt
from pydantic import BaseModel, Field, field_validator
from app.models.enums import EstadoTurno, TipoTurno
def _hora_de_pared(v: dt.datetime) -> dt.datetime:
    """Misma convención que la reserva pública: hora de pared etiquetada UTC.
    Sin esto, un datetime sin zona hacía reventar el motor (TypeError -> 500)."""
    return v.replace(tzinfo=dt.timezone.utc)


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
    notas: str | None = Field(default=None, max_length=2000)
    importe_previsto: float | None = Field(default=None, ge=0, le=100_000_000)
    es_sobreturno: bool = False  # si es True, salta la validación de disponibilidad

    @field_validator("fecha_inicio")
    @classmethod
    def _zona(cls, v: dt.datetime) -> dt.datetime:
        return _hora_de_pared(v)
class TurnoMover(BaseModel):
    """Reprogramar: nuevo horario y/o nuevo recurso."""
    fecha_inicio: dt.datetime
    recurso_id: int | None = None  # si cambia de profesional

    @field_validator("fecha_inicio")
    @classmethod
    def _zona(cls, v: dt.datetime) -> dt.datetime:
        return _hora_de_pared(v)
class TurnoCambiarEstado(BaseModel):
    """Cambiar el estado del turno (confirmar, atender, cancelar...).

    Al cancelar se puede mandar el motivo. El service lo guarda solo cuando el
    estado es CANCELADO; en las demás transiciones se ignora.
    """
    estado: EstadoTurno
    motivo_cancelacion: str | None = Field(default=None, max_length=300)
class TurnoDescuento(BaseModel):
    """Aplicar un descuento al turno: porcentaje (0-100) y/o fijo en pesos.

    `descuento_monto` es opcional para no romper a quien manda solo el %.
    """
    descuento_pct: float = Field(ge=0, le=100)
    descuento_monto: float | None = Field(default=None, ge=0, le=100_000_000)
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
    cubierto_por_abono: bool
    descuento_pct: float
    descuento_monto: float = 0
    cobrado: bool
    total: float = 0  # servicio + adicionales − descuento (lo calcula el service)
    notas: str | None
    motivo_cancelacion: str | None
    # nombres resueltos (los llena el service para la agenda)
    cliente_nombre: str | None = None
    recurso_nombre: str | None = None
    servicio_nombre: str | None = None
    servicio_grupo: str | None = None  # carril del servicio (corte/tintura/barba)
    # Seña online (Mercado Pago): null = sin seña · pendiente · pagada
    sena_estado: str | None = None
    sena_monto: float | None = None
    # Lo que YA se cobró por adelantado de este turno (señas acreditadas).
    # Se calcula sobre los pagos reales, no sobre sena_monto: si la seña se
    # pagó con un monto distinto al configurado, vale lo que entró.
    senado: float = 0.0
    # Toda la plata ya registrada de este turno (seña + cobro). Si el turno
    # se reabre o se cancela, esta plata NO se va sola de la caja.
    # No se llama `cobrado` porque ese nombre ya lo usa el booleano de arriba.
    pagado_total: float = 0.0
    # Total − señado. Es lo que hay que cobrar al finalizar; si el diálogo de
    # cobro mostrara el total, la recepción le cobraría de más al cliente.
    saldo: float | None = None
    model_config = {"from_attributes": True}
class TurnosPagina(BaseModel):
    total: int
    items: list[TurnoOut]
