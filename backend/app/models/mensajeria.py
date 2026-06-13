"""Mensajería (tablas nacen en E1; la integración llega en E6/E7).
Regla 6: todo mensaje queda registrado. Regla 5: PROHIBIDO contenido de salud."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import CanalMensaje, DireccionMensaje, EstadoMensaje
from app.models.organizacion import TenantMixin
from app.models.tipos import enum_pg


class PlantillaMensaje(TenantMixin, Base):
    __tablename__ = "plantilla_mensaje"

    id: Mapped[int] = mapped_column(primary_key=True)
    canal: Mapped[CanalMensaje] = mapped_column(enum_pg(CanalMensaje, "canal_mensaje"))
    # confirmacion, recordatorio_24h, recordatorio_2h, cancelacion, cambio_fecha,
    # cambio_profesional, calificacion, auto_listo, cumpleanos, bienvenida, detalle_trabajo
    codigo: Mapped[str] = mapped_column(String(60))
    nombre: Mapped[str] = mapped_column(String(120))
    cuerpo: Mapped[str] = mapped_column(Text)
    aprobada_meta: Mapped[bool] = mapped_column(Boolean, default=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class Mensaje(TenantMixin, Base):
    __tablename__ = "mensaje"
    __table_args__ = (
        Index("ix_mensaje_empresa_fecha", "empresa_id", "fecha"),
        Index("ix_mensaje_empresa_cliente", "empresa_id", "cliente_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cliente.id"))
    turno_id: Mapped[int | None] = mapped_column(ForeignKey("turno.id"))
    canal: Mapped[CanalMensaje] = mapped_column(enum_pg(CanalMensaje, "canal_mensaje"))
    direccion: Mapped[DireccionMensaje] = mapped_column(
        enum_pg(DireccionMensaje, "direccion_mensaje"), default=DireccionMensaje.SALIENTE
    )
    plantilla_id: Mapped[int | None] = mapped_column(ForeignKey("plantilla_mensaje.id"))
    contenido: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[EstadoMensaje] = mapped_column(
        enum_pg(EstadoMensaje, "estado_mensaje"), default=EstadoMensaje.PENDIENTE
    )
    error: Mapped[str | None] = mapped_column(String(300))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())