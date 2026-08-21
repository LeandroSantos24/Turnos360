"""El medidor de WhatsApp: saldo por empresa y el libro de movimientos.

Por qué son DOS tablas y no un contador
---------------------------------------
`wa_saldo` es un número mutable, uno por empresa, que se lee y se descuenta
con un lock. `wa_movimiento` es un libro que solo crece: cada carga y cada
consumo deja una fila y nada se borra.

El contador solo existe para poder preguntar "¿le queda saldo?" sin sumar
todo el histórico en cada envío. El libro es la verdad: si algún día el
contador y el libro no coinciden, gana el libro y el contador se recalcula.

Esto importa porque acá hay plata de un tercero. Cuando una barbería diga
"pagué 500 y me consumiste 700", la respuesta tiene que ser una lista de
movimientos con fecha, no "el sistema dice 200".
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.organizacion import TenantMixin


class SaldoWhatsapp(Base):
    """Un renglón por empresa. Se lee con FOR UPDATE antes de cada envío."""

    __tablename__ = "wa_saldo"

    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), primary_key=True)
    disponible: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Acumulado histórico, solo informativo: cuántos mensajes gastó en total.
    # No se usa para decidir nada; sirve para la pantalla y para cotizar packs.
    consumidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actualizado: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MovimientoWhatsapp(TenantMixin, Base):
    """El libro. Positivo acredita, negativo consume. Nunca se borra una fila."""

    __tablename__ = "wa_movimiento"
    __table_args__ = (Index("ix_wa_movimiento_empresa_fecha", "empresa_id", "fecha"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # + carga de un pack o un regalo · - un mensaje enviado
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    # pack · regalo · ajuste · envio · devolucion
    motivo: Mapped[str] = mapped_column(String(20), nullable=False)
    detalle: Mapped[str | None] = mapped_column(String(200))
    # Lo que el negocio pagó por esta carga, en pesos. Se guarda el precio del
    # DÍA de la carga: el precio de lista cambia con el dólar y sin esto no se
    # puede reconstruir cuánto facturamos.
    precio_ars: Mapped[float | None] = mapped_column(Numeric(12, 2))
    mensaje_id: Mapped[int | None] = mapped_column(ForeignKey("mensaje.id"))
    # Quién cargó el pack (un super-admin). Vacío cuando lo genera el sistema.
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
