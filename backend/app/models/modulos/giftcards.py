"""Gift cards (E11-fidelización).

Una gift card es un código único que vale un monto (o un servicio) y se canjea
UNA sola vez. La autenticidad NO está en el QR: está en que el código existe
en la base, pertenece a esta empresa y sigue activa. El QR es solo el código
hecho imagen para escanearlo cómodo.

Estados (EstadoGiftCard): ACTIVA -> CANJEADA (o VENCIDA si pasó la fecha).
El código se genera con `secrets` (criptográfico): imposible de adivinar.
"""

import datetime as dt
from datetime import datetime

from sqlalchemy import (
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.organizacion import TenantMixin
from app.models.enums import EstadoGiftCard
from app.models.tipos import enum_pg


class GiftCard(TenantMixin, Base):
    """Tarjeta de regalo con código único, canjeable una sola vez."""

    __tablename__ = "gift_card"
    __table_args__ = (
        # El código es único DENTRO de la empresa (multi-tenant).
        Index("ix_gift_card_empresa_codigo", "empresa_id", "codigo", unique=True),
        Index("ix_gift_card_empresa_estado", "empresa_id", "estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # El código legible que va impreso / en el QR (ej. "GIFT-A1B2-C3D4").
    codigo: Mapped[str] = mapped_column(String(40))

    # Para quién es (texto libre: no exige que sea un cliente cargado).
    beneficiario: Mapped[str | None] = mapped_column(String(120))
    de_parte_de: Mapped[str | None] = mapped_column(String(120))
    mensaje: Mapped[str | None] = mapped_column(String(300))

    # Valor: un monto en $ (lo más común). El canje por servicio puntual queda
    # como texto en 'concepto' para v1; el monto es lo que mueve la caja.
    monto: Mapped[float] = mapped_column(Numeric(12, 2))
    concepto: Mapped[str | None] = mapped_column(String(120))  # "Corte + barba", opcional

    estado: Mapped[EstadoGiftCard] = mapped_column(
        enum_pg(EstadoGiftCard, "estado_gift_card"),
        default=EstadoGiftCard.ACTIVA,
    )

    vence: Mapped[dt.date | None] = mapped_column(Date)  # None = sin vencimiento

    # Trazabilidad del canje.
    canjeada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canjeada_por: Mapped[str | None] = mapped_column(String(120))  # usuario que la validó

    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def esta_vencida(self) -> bool:
        return self.vence is not None and self.vence < dt.date.today()
