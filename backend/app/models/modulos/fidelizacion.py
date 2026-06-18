"""Fidelización: membresías / abonos (E11, adelantado para barberías).

Dos tablas:
- PlanAbono: el "molde" que el dueño define una vez (nombre, precio, qué cubre).
- Membresia: cuando un cliente compra un plan (con fechas desde/hasta).

Regla: un cliente tiene UNA membresía activa a la vez. Está "vigente" si
fecha_desde <= hoy <= fecha_hasta y su estado es ACTIVA.
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
    Enum as SAEnum,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.organizacion import TenantMixin
from app.models.enums import EstadoMembresia


class PlanAbono(TenantMixin, Base):
    """El molde de abono que define el dueño (ej. 'PRO', $50.000, ilimitado)."""

    __tablename__ = "plan_abono"
    __table_args__ = (
        Index("ix_plan_abono_empresa_activo", "empresa_id", "activo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))  # "PRO", "Básico"
    descripcion: Mapped[str | None] = mapped_column(String(300))
    precio: Mapped[float] = mapped_column(Numeric(12, 2))

    # ¿Es ilimitado o por cantidad de cortes?
    ilimitado: Mapped[bool] = mapped_column(Boolean, default=True)
    # Si NO es ilimitado, cuántos servicios cubre en el período
    cantidad_cupos: Mapped[int | None] = mapped_column(Integer, default=None)

    # Qué servicios cubre: lista de IDs de servicio (los ya creados).
    # Vacío/None = cubre todos.
    servicios_cubiertos: Mapped[list | None] = mapped_column(JSONB, default=list)

    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Membresia(TenantMixin, Base):
    """Un cliente que compró un plan de abono, con su período de vigencia."""

    __tablename__ = "membresia"
    __table_args__ = (
        Index("ix_membresia_empresa_cliente", "empresa_id", "cliente_id"),
        Index("ix_membresia_vigencia", "empresa_id", "fecha_hasta"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan_abono.id"))

    fecha_desde: Mapped[dt.date] = mapped_column(Date)
    fecha_hasta: Mapped[dt.date] = mapped_column(Date)

    estado: Mapped[EstadoMembresia] = mapped_column(
        SAEnum(EstadoMembresia, name="estado_membresia"),
        default=EstadoMembresia.ACTIVA,
    )

    # Cuántos cupos usó (para los abonos por cantidad). En ilimitados se ignora.
    cupos_usados: Mapped[int] = mapped_column(Integer, default=0)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    plan: Mapped["PlanAbono"] = relationship()