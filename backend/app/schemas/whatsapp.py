"""Lo que el panel ve de WhatsApp."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PackOut(BaseModel):
    cantidad: int
    precio_ars: float
    precio_por_mensaje: float


class EstadoWhatsappOut(BaseModel):
    """La pantalla de WhatsApp del dueño, en un solo pedido."""

    # simulado | meta. Con "simulado" NO sale nada a la calle: sirve para que
    # el dueño vea el circuito completo antes de que haya credenciales.
    proveedor: str
    conectado: bool
    numero: str | None
    disponible: int
    consumidos: int
    precio_mensaje_ars: float
    packs: list[PackOut]
    plantillas_activas: int
    # Clientes con teléfono que NO sirve para WhatsApp. Es el número que le
    # dice al dueño cuántos recordatorios no van a salir nunca.
    clientes_sin_telefono_valido: int


class MensajeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cliente: str | None
    telefono: str | None
    plantilla: str | None
    estado: str
    error: str | None
    fecha: datetime


class MovimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cantidad: int
    motivo: str
    detalle: str | None
    precio_ars: float | None
    fecha: datetime


class PruebaIn(BaseModel):
    telefono: str


class PruebaOut(BaseModel):
    enviado: bool
    proveedor: str
    destino: str
    texto: str
    detalle: str | None = None


class AcreditarIn(BaseModel):
    cantidad: int
    precio_ars: float | None = None
    motivo: str = "pack"
    detalle: str | None = None


class CredencialesIn(BaseModel):
    token: str
    phone_number_id: str
    numero: str | None = None
    waba_id: str | None = None
