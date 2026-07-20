"""Cobranza del SaaS: lo que cada negocio le paga a Turnos360.

OJO con no confundirlo con app/models/finanzas.py: eso es la caja DEL NEGOCIO
(lo que un cliente le paga a la barbería). Esto es la caja de Leandro: la
cuota mensual que la barbería le paga a Turnos360. Por eso vive fuera del
TenantMixin — no lo ve ningún negocio, solo el super-admin.
"""

import datetime as dt
from datetime import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PagoSuscripcion(Base):
    """Un pago de cuota registrado a mano por el super-admin.

    Registrar un pago normalmente EMPUJA suscripcion_vence 30 días (lo hace el
    servicio), pero el registro y el vencimiento son cosas separadas a
    propósito: se puede anotar un pago parcial sin renovar, o renovar sin
    cobrar (una cortesía).
    """

    __tablename__ = "pago_suscripcion"
    __table_args__ = (
        Index("ix_pago_suscripcion_fecha", "fecha"),
        Index("ix_pago_suscripcion_empresa_fecha", "empresa_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)

    fecha: Mapped[dt.date] = mapped_column(Date)
    monto: Mapped[float] = mapped_column(Numeric(12, 2))
    # Texto libre y no un enum: los métodos de cobro del SaaS cambian solos
    # (transferencia, efectivo, MP, dólares) y no vale una migración por cada uno.
    metodo: Mapped[str] = mapped_column(String(40), default="transferencia")

    # Período que cubre el pago (para el historial: "esto es el mes de julio").
    periodo_desde: Mapped[dt.date | None] = mapped_column(Date)
    periodo_hasta: Mapped[dt.date | None] = mapped_column(Date)

    notas: Mapped[str | None] = mapped_column(Text)
    registrado_por: Mapped[str | None] = mapped_column(String(160))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    empresa: Mapped["Empresa"] = relationship()  # noqa: F821
