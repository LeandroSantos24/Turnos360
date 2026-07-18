"""Cliente (CRM), historial por eventos, calificaciones, adjuntos y lista de espera."""

import datetime as dt
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.organizacion import TenantMixin


class Cliente(TenantMixin, Base):
    __tablename__ = "cliente"
    __table_args__ = (
        Index("ix_cliente_empresa_apellido_nombre", "empresa_id", "apellido", "nombre"),
        Index("ix_cliente_empresa_telefono", "empresa_id", "telefono"),
        Index("ix_cliente_empresa_dni", "empresa_id", "dni"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    apellido: Mapped[str | None] = mapped_column(String(120))
    dni: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    telefono: Mapped[str | None] = mapped_column(String(40))  # la llave de WhatsApp (D-13)
    fecha_nacimiento: Mapped[dt.date | None] = mapped_column(Date)
    # N-04: instagram, tiktok, referido, google, paso_por_la_puerta…
    canal_adquisicion: Mapped[str | None] = mapped_column(String(60))
    # Último año en que se le mandó el saludo de cumpleaños (dedup anual).
    ultimo_cumple_enviado: Mapped[dt.date | None] = mapped_column(Date)
    # Consentimiento para campañas promocionales (Ley 25.326). Los emails
    # transaccionales del turno NO dependen de esto.
    acepta_marketing: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    ultimo_inactivo_enviado: Mapped[dt.date | None] = mapped_column(Date)
    campos_rubro: Mapped[dict] = mapped_column(JSONB, default=dict)  # lo define el preset
    preferencias: Mapped[dict] = mapped_column(JSONB, default=dict)
    etiquetas: Mapped[list | None] = mapped_column(JSONB, default=list)  # VIP, frecuente…
    observaciones: Mapped[str | None] = mapped_column(Text)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class HistorialCliente(TenantMixin, Base):
    """Registro cronológico de eventos: turno, pago, promoción, encuesta, tratamiento…"""

    __tablename__ = "historial_cliente"
    __table_args__ = (
        Index("ix_historial_empresa_cliente_fecha", "empresa_id", "cliente_id", "fecha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    tipo_evento: Mapped[str] = mapped_column(String(40))
    descripcion: Mapped[str | None] = mapped_column(String(300))
    ref_tabla: Mapped[str | None] = mapped_column(String(40))
    ref_id: Mapped[int | None] = mapped_column(Integer)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Calificacion(TenantMixin, Base):
    __tablename__ = "calificacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    turno_id: Mapped[int] = mapped_column(ForeignKey("turno.id"))
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    puntaje: Mapped[int] = mapped_column(Integer)  # 1 a 5
    comentario: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Adjunto(TenantMixin, Base):
    """Gestión documental: contratos, consentimientos, estudios, radiografías, fotos, PDFs."""

    __tablename__ = "adjunto"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    # FK real a entrada_clinica llega con la migración del pack salud (E13)
    entrada_clinica_id: Mapped[int | None] = mapped_column(Integer)
    tipo: Mapped[str | None] = mapped_column(String(40))
    nombre_archivo: Mapped[str] = mapped_column(String(255))
    ruta: Mapped[str] = mapped_column(String(500))
    subido_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ListaEspera(TenantMixin, Base):
    __tablename__ = "lista_espera"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("cliente.id"))
    servicio_id: Mapped[int | None] = mapped_column(ForeignKey("servicio.id"))
    recurso_id: Mapped[int | None] = mapped_column(ForeignKey("recurso.id"))  # NULL = cualquiera
    rango_preferido: Mapped[str | None] = mapped_column(String(120))
    estado: Mapped[str] = mapped_column(String(20), default="esperando")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )