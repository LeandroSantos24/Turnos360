"""Finanzas y caja (las tablas nacen en E1; la lógica llega en E10)."""

import datetime as dt
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import EstadoCaja, ModalidadComision, TipoMovimiento
from app.models.organizacion import (
    TenantMixin,
    fk_sucursal,
    sucursal_por_defecto,
)
from app.models.tipos import enum_pg


class Caja(TenantMixin, Base):
    __tablename__ = "caja"
    __table_args__ = (
        fk_sucursal("fk_caja_sucursal"),
        # Una sola caja abierta por local, garantizado por la base y no por un
        # SELECT seguido de un INSERT: dos pestañas abriendo caja al mismo
        # tiempo pasaban las dos y el negocio terminaba con dos cajas abiertas
        # y la plata del día repartida entre ambas.
        Index(
            "uq_caja_abierta_por_sucursal",
            "empresa_id",
            "sucursal_id",
            unique=True,
            postgresql_where=text("estado = 'abierta'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Cada local cuenta su propia plata y firma su propio arqueo.
    sucursal_id: Mapped[int] = mapped_column(
        Integer, nullable=False, default=sucursal_por_defecto
    )
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
        # Los totales de caja filtran SIEMPRE por anulado = false. El índice lo
        # crea la migración a3d5f81c92e7; declararlo TAMBIÉN acá no es
        # redundancia: sin esto el próximo --autogenerate lo detecta como
        # "índice que sobra en la base" y escribe un DROP INDEX en la migración
        # nueva, silenciosamente.
        Index("ix_movfin_caja_activos", "empresa_id", "caja_id", "anulado"),
        fk_sucursal("fk_movfin_sucursal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    caja_id: Mapped[int | None] = mapped_column(ForeignKey("caja.id"))
    # En qué local entró (o salió) esta plata.
    #
    # Se guarda acá y no se deduce de la caja a propósito: `caja_id` es
    # NULLABLE —un cobro con la caja cerrada igual se registra— y sin esta
    # columna esa plata quedaría sin local, invisible para el arqueo y para
    # las estadísticas por sucursal.
    sucursal_id: Mapped[int] = mapped_column(
        Integer, nullable=False, default=sucursal_por_defecto
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tipo: Mapped[TipoMovimiento] = mapped_column(enum_pg(TipoMovimiento, "tipo_movimiento"))
    concepto: Mapped[str | None] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(String(300))
    monto: Mapped[float] = mapped_column(Numeric(12, 2))
    moneda: Mapped[str] = mapped_column(String(3), default="ARS")
    metodo_pago_id: Mapped[int | None] = mapped_column(ForeignKey("metodo_pago.id"))
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categoria_financiera.id"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))

    # --- Anulación auditada ------------------------------------------------
    # Un movimiento nunca se borra: se anula. Borrarlo hacía imposible auditar
    # una diferencia de arqueo, porque no quedaba rastro de que hubiera
    # existido. Anulado = sigue en el listado, no suma a ningún total.
    anulado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(String(200))


class Pago(TenantMixin, Base):
    __tablename__ = "pago"
    # Los cuatro accesos reales a esta tabla. Sin ellos, Postgres escanea
    # `pago` entero en cada carga de agenda, de estadísticas, de ficha de
    # cliente y en cada webhook de Mercado Pago.
    #
    # OJO con turno_id y movimiento_id: esas consultas NO filtran por
    # empresa_id, así que un índice que empiece por empresa_id no las
    # ayuda. Tienen que ir con la columna de la izquierda.
    __table_args__ = (
        Index("ix_pago_empresa_origen", "empresa_id", "origen"),
        Index("ix_pago_empresa_fecha", "empresa_id", "fecha"),
        Index("ix_pago_turno", "turno_id"),
        Index("ix_pago_empresa_cliente", "empresa_id", "cliente_id"),
        Index("ix_pago_movimiento", "movimiento_id"),
        # Idempotencia de la seña a nivel base. El chequeo en Python es un
        # SELECT seguido de un INSERT: dos notificaciones simultáneas de MP
        # (que llegan en paralelo, no en fila) pasaban las dos y registraban
        # la seña dos veces. Con este índice la segunda falla y se puede
        # atrapar.
        Index(
            "uq_pago_sena_turno",
            "turno_id",
            unique=True,
            postgresql_where=text("origen = 'sena'"),
        ),
        # Estadísticas filtra SIEMPRE por anulado=false. Declarado acá y no
        # solo en la migración para que el autogenerate no lo vea como un
        # índice de más y proponga borrarlo en la próxima migración.
        Index(
            "ix_pago_empresa_vigente",
            "empresa_id",
            "fecha",
            postgresql_where=text("anulado = false"),
        ),
        fk_sucursal("fk_pago_sucursal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # El local que facturó. Estadísticas lee de esta tabla, no de los
    # movimientos, así que sin esta columna no habría forma de comparar la
    # facturación de dos locales.
    sucursal_id: Mapped[int] = mapped_column(
        Integer, nullable=False, default=sucursal_por_defecto
    )
    turno_id: Mapped[int | None] = mapped_column(ForeignKey("turno.id"))
    orden_trabajo_id: Mapped[int | None] = mapped_column(Integer)  # FK real en E14
    # Opcional: la venta de una gift card al mostrador no tiene ficha de
    # cliente (el beneficiario es un texto). Cuando era obligatorio, esas
    # ventas no podían registrarse como pago y por eso entraban a la caja
    # pero NO a Estadísticas: los dos números del mismo día no coincidían.
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("cliente.id"))
    metodo_pago_id: Mapped[int | None] = mapped_column(ForeignKey("metodo_pago.id"))
    # De dónde salió la plata: "turno" | "abono" | "giftcard".
    # Permite separar en Estadísticas la facturación de la atención (turnos)
    # de la venta de abonos y tarjetas, que no tienen profesional ni servicio
    # y distorsionarían el ticket promedio si se mezclaran.
    origen: Mapped[str | None] = mapped_column(String(20), default="turno")
    monto: Mapped[float] = mapped_column(Numeric(12, 2))
    comision_aplicada: Mapped[float | None] = mapped_column(Numeric(12, 2))
    movimiento_id: Mapped[int | None] = mapped_column(ForeignKey("movimiento_financiero.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Anulación (misma idea que en MovimientoFinanciero: no se borra, se
    # marca). Estadísticas lee de esta tabla, así que sin esta columna una
    # venta revertida seguía facturando aunque su movimiento estuviera
    # anulado: los dos números del mismo día no coincidían.
    anulado: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    anulado_por_id: Mapped[int | None] = mapped_column(Integer)
    motivo_anulacion: Mapped[str | None] = mapped_column(String(200))


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