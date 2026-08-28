"""Cobranza del SaaS: lo que cada negocio le paga a Turnos360.

OJO con no confundirlo con app/models/finanzas.py: eso es la caja DEL NEGOCIO
(lo que un cliente le paga a la barbería). Esto es la caja de Leandro: la
cuota mensual que la barbería le paga a Turnos360. Por eso vive fuera del
TenantMixin — no lo ve ningún negocio, solo el super-admin.
"""

import datetime as dt
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
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
        Index(
            "uq_pago_suscripcion_mp",
            "mp_payment_id",
            unique=True,
            postgresql_where=text("mp_payment_id is not null"),
        ),
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

    # Id del pago en Mercado Pago, cuando la cuota entró por ahí. Único: es la
    # idempotencia del webhook. Mercado Pago reintenta la misma notificación
    # varias veces y sin esto cada reintento renovaba otros 30 días.
    mp_payment_id: Mapped[str | None] = mapped_column(String(40))

    # Anulación: una cuota anotada por error deja de contar para el historial
    # y para el MRR, pero la fila queda (es plata, tiene que dejar rastro).
    anulado: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por: Mapped[str | None] = mapped_column(String(160))

    empresa: Mapped["Empresa"] = relationship()  # noqa: F821


class AjusteSuscripcion(Base):
    """Toda vez que se movió el vencimiento de una empresa, y por qué.

    POR QUÉ EXISTE
    ──────────────
    Antes, mover el vencimiento no dejaba ningún rastro. El botón "Renovar 30
    días" regalaba un mes con un click, sin cartel de confirmación y sin
    registrar nada: si se apretaba por error no había forma de enterarse
    después, ni de saber cuál era la fecha anterior para volver atrás. Lo mismo
    con las prórrogas, que además son acumulativas.

    Acá queda la película: quién, cuándo, de qué fecha a qué fecha y por qué.
    Con `vence_antes` guardado, revertir es restaurar un dato, no adivinarlo.

    Ojo con la diferencia con PagoSuscripcion: eso es "cobré una cuota" (plata).
    Esto es "moví la fecha" (efecto). Un pago genera un ajuste, pero hay ajustes
    sin pago —una cortesía, una prórroga— y por eso son dos tablas.
    """

    __tablename__ = "ajuste_suscripcion"
    __table_args__ = (
        Index("ix_ajuste_suscripcion_empresa", "empresa_id", "creado_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)

    # "pago" | "renovacion" | "prorroga" | "manual" | "reversion"
    tipo: Mapped[str] = mapped_column(String(20))
    vence_antes: Mapped[dt.date | None] = mapped_column(Date)
    vence_despues: Mapped[dt.date | None] = mapped_column(Date)
    dias: Mapped[int | None] = mapped_column(Integer)
    detalle: Mapped[str | None] = mapped_column(Text)

    # El pago que originó el ajuste, si lo hubo. Revertir el ajuste anula el
    # pago: si no, quedaría una cuota cobrada que no cubre ningún período.
    pago_id: Mapped[int | None] = mapped_column(ForeignKey("pago_suscripcion.id"))

    hecho_por: Mapped[str | None] = mapped_column(String(160))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Un ajuste revertido no se borra ni se puede revertir dos veces.
    revertido: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    revertido_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revertido_por: Mapped[str | None] = mapped_column(String(160))


class AvisoPago(Base):
    """El negocio avisa "ya te pagué". No es plata todavía: es un aviso.

    POR QUÉ NO ES UN PagoSuscripcion
    ────────────────────────────────
    Una transferencia tarda en verse en la cuenta. Anotar la cuota en el
    momento en que el dueño dice que pagó sería registrar plata que quizá no
    llegó, y el MRR pasaría a ser un número de buena fe.

    Así que el aviso vive aparte: le da al dueño la respuesta que necesita
    ("tu pago está en proceso, en 24 h vas a verlo reflejado") y a Leandro una
    bandeja de entrada con lo que tiene que ir a confirmar contra el banco.
    Cuando confirma, ahí sí nace el PagoSuscripcion y se mueve el vencimiento.

    Los pagos por Mercado Pago NO pasan por acá: los confirma el webhook con la
    respuesta de la API de MP, que es una fuente de verdad y no una promesa.
    """

    __tablename__ = "aviso_pago"
    __table_args__ = (
        Index("ix_aviso_pago_pendiente", "creado_en", postgresql_where=text("resuelto = false")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)

    metodo: Mapped[str] = mapped_column(String(40), default="transferencia")
    monto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    # Lo que el dueño escriba: número de operación, banco, "lo mandó mi socia".
    referencia: Mapped[str | None] = mapped_column(Text)
    avisado_por: Mapped[str | None] = mapped_column(String(160))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    resuelto: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resuelto_por: Mapped[str | None] = mapped_column(String(160))
    # Si se confirmó, la cuota que se registró a partir de este aviso.
    pago_id: Mapped[int | None] = mapped_column(ForeignKey("pago_suscripcion.id"))

    empresa: Mapped["Empresa"] = relationship()  # noqa: F821
