"""Lo reservable y su disponibilidad: Recurso (Regla 2), Especialidad (D-15),
HorarioRecurso, ExcepcionAgenda y Servicio."""

import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TipoExcepcion, TipoRecurso
from app.models.organizacion import TenantMixin
from app.models.tipos import enum_pg

# Tablas puente N:M (no son clases porque no tienen datos propios)
recurso_especialidad = Table(
    "recurso_especialidad",
    Base.metadata,
    Column("recurso_id", ForeignKey("recurso.id"), primary_key=True),
    Column("especialidad_id", ForeignKey("especialidad.id"), primary_key=True),
)

servicio_recurso = Table(
    "servicio_recurso",
    Base.metadata,
    Column("servicio_id", ForeignKey("servicio.id"), primary_key=True),
    Column("recurso_id", ForeignKey("recurso.id"), primary_key=True),
)


class Especialidad(TenantMixin, Base):
    """Catálogo parametrizable por empresa (D-15)."""

    __tablename__ = "especialidad"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))


class Recurso(TenantMixin, Base):
    """Regla 2: lo reservable es un Recurso con tipo persona/box/equipo."""

    __tablename__ = "recurso"
    __table_args__ = (Index("ix_recurso_empresa_tipo", "empresa_id", "tipo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int | None] = mapped_column(ForeignKey("sucursal.id"))
    tipo: Mapped[TipoRecurso] = mapped_column(enum_pg(TipoRecurso, "tipo_recurso"))
    nombre: Mapped[str] = mapped_column(String(120))
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id")
    )  # si el recurso es una persona con login
    color: Mapped[str | None] = mapped_column(String(9))  # para la agenda visual
    # Foto del profesional para la sección "Equipo" de la landing pública.
    foto_url: Mapped[str | None] = mapped_column(String(300))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    especialidades: Mapped[list["Especialidad"]] = relationship(
        secondary=recurso_especialidad
    )


class HorarioRecurso(TenantMixin, Base):
    """Franjas de disponibilidad. Apertura por día o por semana con vigencia."""

    __tablename__ = "horario_recurso"
    __table_args__ = (
        Index("ix_horario_empresa_recurso_dia", "empresa_id", "recurso_id", "dia_semana"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recurso_id: Mapped[int] = mapped_column(ForeignKey("recurso.id"))
    dia_semana: Mapped[int] = mapped_column(Integer)  # 0=lunes … 6=domingo
    hora_desde: Mapped[dt.time] = mapped_column(Time)
    hora_hasta: Mapped[dt.time] = mapped_column(Time)
    vigencia_desde: Mapped[dt.date | None] = mapped_column(Date)
    vigencia_hasta: Mapped[dt.date | None] = mapped_column(Date)


class ExcepcionAgenda(TenantMixin, Base):
    """Feriados, licencias, vacaciones, bloqueos. recurso_id NULL = toda la empresa."""

    __tablename__ = "excepcion_agenda"

    id: Mapped[int] = mapped_column(primary_key=True)
    recurso_id: Mapped[int | None] = mapped_column(ForeignKey("recurso.id"))
    tipo: Mapped[TipoExcepcion] = mapped_column(enum_pg(TipoExcepcion, "tipo_excepcion"))
    fecha_desde: Mapped[dt.date] = mapped_column(Date)
    fecha_hasta: Mapped[dt.date] = mapped_column(Date)
    motivo: Mapped[str | None] = mapped_column(String(200))


class Servicio(TenantMixin, Base):
    __tablename__ = "servicio"
    __table_args__ = (Index("ix_servicio_empresa_activo", "empresa_id", "activo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    duracion_min: Mapped[int] = mapped_column(Integer)
    buffer_min: Mapped[int] = mapped_column(Integer, default=0)
    # cada cuántos minutos se ofrecen turnos de este servicio.
    # corte: 15-20 · color/reflejos: 60 (el barbero maneja varias a la vez)
    paso_turno_min: Mapped[int] = mapped_column(Integer, default=15)
    grupo_agenda: Mapped[str | None] = mapped_column(String(40), default=None)
    precio: Mapped[float | None] = mapped_column(Numeric(12, 2))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Si NO ocupa turno (perfilado, lavado, productos): no aparece al agendar,
    # solo se puede sumar como adicional. server_default cubre las filas ya creadas.
    agendable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    recursos: Mapped[list["Recurso"]] = relationship(secondary=servicio_recurso)