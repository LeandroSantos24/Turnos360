"""Cupones de descuento para la reserva online (y el mostrador).

El negocio crea códigos (INAUGURACION20, VERANO10OFF) y decide:
- tipo: porcentaje del precio o monto fijo en pesos
- a qué servicios aplica (lista vacía = TODOS los servicios)
- hasta cuándo vale (vence_el) y cuántas veces se puede usar (max_usos)

El descuento se materializa en turno.descuento_pct (el sistema de totales ya
lo aplica en todo el sistema): un cupón de monto fijo se traduce al porcentaje
equivalente sobre el precio del servicio.
"""

import datetime as dt

from sqlalchemy import Boolean, Date, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.organizacion import TenantMixin


class CuponDescuento(TenantMixin, Base):
    __tablename__ = "cupon_descuento"
    __table_args__ = (
        # El código es único DENTRO de cada empresa (dos negocios pueden tener
        # su propio "PROMO10").
        UniqueConstraint("empresa_id", "codigo", name="uq_cupon_empresa_codigo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30))  # se guarda en MAYÚSCULAS
    tipo: Mapped[str] = mapped_column(String(10), default="porcentaje")  # porcentaje | monto
    valor: Mapped[float] = mapped_column(Numeric(12, 2))
    vence_el: Mapped[dt.date | None] = mapped_column(Date)
    max_usos: Mapped[int | None] = mapped_column(Integer)
    usos: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # IDs de servicios a los que aplica. VACÍO = todos (el caso común de un
    # cupón de promoción general; distinto de membresías, donde vacío = ninguno
    # porque regalar servicios es riesgoso).
    servicios_ids: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
