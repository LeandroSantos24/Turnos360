"""Lo reservable y su disponibilidad: Recurso (Regla 2), Especialidad (D-15),
HorarioRecurso, ExcepcionAgenda y Servicio."""

import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Time,
    UniqueConstraint,
    event,
    literal,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TipoExcepcion, TipoRecurso
from app.models.organizacion import (
    Sucursal,
    TenantMixin,
    fk_sucursal,
    sucursal_por_defecto,
)
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
    __table_args__ = (
        Index("ix_recurso_empresa_tipo", "empresa_id", "tipo"),
        fk_sucursal("fk_recurso_sucursal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # El profesional pertenece a UN local. Si una persona atiende en dos,
    # se carga dos veces: es lo que hace el mercado y evita que el motor de
    # disponibilidad tenga que adivinar a qué local corresponde cada hueco.
    sucursal_id: Mapped[int] = mapped_column(
        Integer, nullable=False, default=sucursal_por_defecto
    )
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
    __table_args__ = (
        Index("ix_servicio_empresa_activo", "empresa_id", "activo"),
        # Igual que en sucursal: redundante como identidad, necesaria para que
        # servicio_sucursal pueda apuntar con una FK COMPUESTA y la base
        # rechace cruzar un servicio de una empresa con el local de otra.
        UniqueConstraint("empresa_id", "id", name="uq_servicio_empresa"),
    )

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

class ServicioSucursal(TenantMixin, Base):
    """En qué locales se ofrece cada servicio, y a qué precio (E16, paso 3b).

    Es una tabla de asociación CON dato propio (`precio`), así que va como
    modelo y no como Table suelta: el mismo "Corte" puede costar $8.000 en el
    centro y $6.500 en el barrio, que es la primera pregunta que hace cualquier
    dueño de dos locales.

    `precio` en NULL significa "el del servicio". No se copia el precio base a
    cada fila a propósito: si se copiara, subir el precio general obligaría a
    tocar cada local uno por uno, y el que se olvidara quedaría vendiendo al
    precio viejo sin que nadie se entere.

    INVARIANTE: todo servicio tiene al menos una fila acá. Lo garantiza el
    listener de abajo, no la disciplina de quien escriba el próximo alta.
    """

    __tablename__ = "servicio_sucursal"
    __table_args__ = (
        fk_sucursal("fk_servicio_sucursal_sucursal"),
        ForeignKeyConstraint(
            ["empresa_id", "servicio_id"],
            ["servicio.empresa_id", "servicio.id"],
            name="fk_servicio_sucursal_servicio",
            ondelete="CASCADE",
        ),
    )

    servicio_id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int] = mapped_column(primary_key=True)
    precio: Mapped[float | None] = mapped_column(Numeric(12, 2))


@event.listens_for(Servicio, "after_insert")
def _ofrecer_en_todos_los_locales(mapper, connection, servicio) -> None:
    """Un servicio nuevo se ofrece en TODOS los locales abiertos.

    Es el mismo criterio que el default de `sucursal_id`: el invariante no
    puede depender de que cada alta se acuerde. Un servicio sin ningún local
    no daría un error ruidoso —daría un servicio invisible, que es peor: nadie
    se entera hasta que un cliente no lo encuentra en la página de reservas.

    El alta del panel pisa esto inmediatamente después si el dueño eligió
    locales puntuales. Para un negocio de un solo local, "todos" es "el suyo"
    y nadie ve nada.
    """
    connection.execute(
        servicio_sucursal_tabla().insert().from_select(
            ["empresa_id", "servicio_id", "sucursal_id"],
            select(
                literal(servicio.empresa_id),
                literal(servicio.id),
                Sucursal.id,
            ).where(
                Sucursal.empresa_id == servicio.empresa_id,
                Sucursal.activa.is_(True),
            ),
        )
    )


def servicio_sucursal_tabla():
    return ServicioSucursal.__table__
