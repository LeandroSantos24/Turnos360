"""Ítems adicionales de un turno (facturación, E10).

Un turno puede sumar ítems extra que NO son turnos aparte: un servicio rápido
hecho en el momento (perfilado, lavado) o un producto vendido (una gaseosa).
Cada ítem tiene su precio y cantidad. El importe_previsto del turno sigue siendo
el del servicio principal; el total a cobrar = importe_previsto + Σ(ítems).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.organizacion import TenantMixin


class ItemTurno(TenantMixin, Base):
    """Un ítem adicional cargado dentro de un turno."""

    __tablename__ = "item_turno"
    __table_args__ = (
        Index("ix_item_turno_empresa_turno", "empresa_id", "turno_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("turno.id"))
    descripcion: Mapped[str] = mapped_column(String(160))
    precio: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    # "servicio" (perfilado, lavado) o "producto" (gaseosa, etc.) — para reportes.
    tipo: Mapped[str] = mapped_column(String(40), default="servicio")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )