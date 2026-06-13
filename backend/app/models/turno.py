"""Turno: la reserva. Regla 3: las 5 formas (D-04) desde el día uno."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import EstadoTurno, TipoTurno
from app.models.organizacion import TenantMixin
from app.models.tipos import enum_pg


class Turno(TenantMixin, Base):
    __tablename__ = "turno"
    __table_args__ = (
        Index("ix_turno_empresa_recurso_inicio", "empresa_id", "recurso_id", "fecha_inicio"),
        Index("ix_turno_empresa_cliente", "empresa_id", "cliente_id"),
        Index("ix_turno_empresa_estado_inicio", "empresa_id", "estado", "fecha_inicio"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int | None] = mapped_column(ForeignKey("sucursal.id"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    recurso_id: Mapped[int] = mapped_column(ForeignKey("recurso.id"))
    servicio_id: Mapped[int | None] = mapped_column(ForeignKey("servicio.id"))
    # FKs reales a vehiculo / paquete_sesiones llegan con sus módulos (E14 / E11)
    vehiculo_id: Mapped[int | None] = mapped_column(Integer)
    paquete_id: Mapped[int | None] = mapped_column(Integer)

    tipo: Mapped[TipoTurno] = mapped_column(
        enum_pg(TipoTurno, "tipo_turno"), default=TipoTurno.SIMPLE
    )
    estado: Mapped[EstadoTurno] = mapped_column(
        enum_pg(EstadoTurno, "estado_turno"), default=EstadoTurno.PENDIENTE
    )
    categoria: Mapped[str | None] = mapped_column(String(60))

    fecha_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posicion_cola: Mapped[int | None] = mapped_column(Integer)  # orden de llegada (taller)
    serie_grupo_id: Mapped[int | None] = mapped_column(Integer)  # recurrencias / sesión N de M
    es_sobreturno: Mapped[bool] = mapped_column(Boolean, default=False)

    importe_previsto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(300))
    notas: Mapped[str | None] = mapped_column(Text)
    creado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id")
    )  # NULL = landing pública
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )