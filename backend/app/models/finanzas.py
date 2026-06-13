"""Finanzas y caja (las tablas nacen en E1; la lógica llega en E10)."""

import datetime as dt
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import EstadoCaja, ModalidadComision, TipoMovimiento
from app.models.organizacion import TenantMixin
from app.models.tipos import enum_pg


class Caja(TenantMixin, Base):
    __tablename__ = "caja"

    id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int | None] = mapped_column(ForeignKey("sucursal.id"))
    fecha_apertura: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    fecha_cierre: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    saldo_inicial: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    saldo_final: Mapped[float | None] = mapped_column(Numeric(12, 2))
    estado: Mapped[EstadoCaja] = mapped_column(
        enum_pg(EstadoCaja, "estado_caja"), default=EstadoCaja.ABIERTA
    )
    abierta_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    cerrada_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))


class CategoriaFinanciera(TenantMixin, Base):
    __tablename__ = "categoria_financiera"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[TipoMovimiento] = mapped_column(enum_pg(TipoMovimiento, "tipo_movimiento"))


class MetodoPago(TenantMixin, Base):
    """D-14: métodos por empresa con comisión configurable."""

    __tablename__ = "metodo_pago"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60))
    comision_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class MovimientoFinanciero(TenantMixin, Base):
    __tablename__ = "movimiento_financiero"
    __table_args__ = (
        Index("ix_movfin_empresa_fecha", "empresa_id", "fecha"),
        Index("ix_movfin_empresa_tipo_categoria", "empresa_id", "tipo", "categoria_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    caja_id: Mapped[int | None] = mapped_column(ForeignKey("caja.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tipo: Mapped[TipoMovimiento] = mapped_column(enum_pg(TipoMovimiento, "tipo_movimiento"))
    concepto: Mapped[str | None] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(String(300))
    monto: Mapped[float] = mapped_column(Numeric(12, 2))
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    metodo_pago_id: Mapped[int | None] = mapped_column(ForeignKey("metodo_pago.id"))
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categoria_financiera.id"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))


class Pago(TenantMixin, Base):
    __tablename__ = "pago"

    id: Mapped[int] = mapped_column(primary_key=True)
    turno_id: Mapped[int | None] = mapped_column(ForeignKey("turno.id"))
    orden_trabajo_id: Mapped[int | None] = mapped_column(Integer)  # FK real en E14
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    metodo_pago_id: Mapped[int | None] = mapped_column(ForeignKey("metodo_pago.id"))
    monto: Mapped[float] = mapped_column(Numeric(12, 2))
    comision_aplicada: Mapped[float | None] = mapped_column(Numeric(12, 2))
    movimiento_id: Mapped[int | None] = mapped_column(ForeignKey("movimiento_financiero.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeudaCliente(TenantMixin, Base):
    """Cuenta corriente simple de clientes (E10)."""

    __tablename__ = "deuda_cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    monto: Mapped[float] = mapped_column(Numeric(12, 2))
    saldada: Mapped[bool] = mapped_column(Boolean, default=False)
    ref_tabla: Mapped[str | None] = mapped_column(String(40))
    ref_id: Mapped[int | None] = mapped_column(Integer)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComisionProfesional(TenantMixin, Base):
    """Porcentaje (70/30), canon por consulta o alquiler. Base de liquidaciones (E10)."""

    __tablename__ = "comision_profesional"

    id: Mapped[int] = mapped_column(primary_key=True)
    recurso_id: Mapped[int] = mapped_column(ForeignKey("recurso.id"))
    modalidad: Mapped[ModalidadComision] = mapped_column(
        enum_pg(ModalidadComision, "modalidad_comision")
    )
    porcentaje: Mapped[float | None] = mapped_column(Numeric(5, 2))
    monto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    vigencia_desde: Mapped[dt.date | None] = mapped_column(Date)