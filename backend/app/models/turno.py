"""Turno: la reserva. Regla 3: las 5 formas (D-04) desde el día uno."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
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
        Index("ix_turno_empresa_cupon", "empresa_id", "cupon_id"),
        # Índices PARCIALES para la tarea de recordatorios, que corre cada
        # 15 minutos y filtra por fecha + flag SIN empresa_id. Como los tres
        # índices de arriba empiezan por empresa_id, ninguno le servía:
        # Postgres escaneaba la tabla entera, dos veces cada cuarto de hora.
        # Son parciales porque casi todos los turnos ya tienen el flag en
        # true, así que el índice queda chico.
        Index(
            "ix_turno_recordatorio_pendiente",
            "fecha_inicio",
            postgresql_where=text("recordatorio_enviado = false"),
        ),
        Index(
            "ix_turno_recordatorio_2h_pendiente",
            "fecha_inicio",
            postgresql_where=text("recordatorio_2h_enviado = false"),
        ),
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
    # True si el turno lo cubrió un abono activo del cliente (importe queda en 0).
    # Sirve para finanzas: distinguir "$0 por abono" de "$0 por otra razón".
    cubierto_por_abono: Mapped[bool] = mapped_column(Boolean, default=False)
    # Descuento aplicado al turno (%). Total = (servicio + adicionales) − este %.
    descuento_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    # Qué cupón produjo ese descuento, si vino de uno. Antes solo se guardaba
    # el porcentaje y un contador global de usos: con eso era imposible saber
    # cuánta gente usó un código y cuánto facturó, que es exactamente lo que
    # decide si la promoción sirvió o fue regalar plata.
    cupon_id: Mapped[int | None] = mapped_column(ForeignKey("cupon_descuento.id"))
    # ¿Ya se cobró este turno? Lo marca el registro de cobro (N-52).
    cobrado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Seña online (Mercado Pago): null = sin seña · "pendiente" · "pagada"
    sena_estado: Mapped[str | None] = mapped_column(String(20))
    sena_monto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    mp_payment_id: Mapped[str | None] = mapped_column(String(60))

    # Recordatorios por email ya enviados (dedup del beat de Celery)
    recordatorio_enviado: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    recordatorio_2h_enviado: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    # Cuándo se creó. Lo escribe Postgres con now(): es un INSTANTE REAL
    # en UTC, NO la hora de pared con la que trabaja fecha_inicio. Son dos
    # convenciones distintas en la misma tabla y mezclarlas da tres horas
    # de error. Se compara contra datetime.now(timezone.utc).
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    motivo_cancelacion: Mapped[str | None] = mapped_column(String(300))
    notas: Mapped[str | None] = mapped_column(Text)
    creado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id")
    )  # NULL = landing pública
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )