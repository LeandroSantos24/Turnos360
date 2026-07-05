"""Tenant y organización: Rubro (catálogo global), Empresa, Sucursal, Usuario, SuperAdmin.

Regla 1: TODA tabla de negocio hereda TenantMixin → empresa_id NOT NULL + índice.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RolUsuario
from app.models.tipos import enum_pg

if TYPE_CHECKING:
    # Solo para el type checker; en runtime SQLAlchemy resuelve "Recurso" por el
    # registro de clases mapeadas. Evita el import circular con agenda.py
    # (agenda.py importa TenantMixin desde acá).
    from app.models.agenda import Recurso


class TenantMixin:
    """empresa_id obligatorio e indexado en toda tabla de negocio (Regla 1)."""

    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresa.id"), nullable=False, index=True
    )


class Rubro(Base):
    """Catálogo GLOBAL de presets (sin empresa_id). Se puebla en E5/E12."""

    __tablename__ = "rubro"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    # terminología, campos_cliente, módulos on/off, tipo_turno_default,
    # servicios sugeridos, régimen de datos sensibles
    preset: Mapped[dict] = mapped_column(JSONB, default=dict)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Empresa(Base):
    """El tenant. config_pack overridea el preset del rubro; credenciales encriptadas (Regla 7)."""

    __tablename__ = "empresa"

    id: Mapped[int] = mapped_column(primary_key=True)
    rubro_id: Mapped[int] = mapped_column(ForeignKey("rubro.id"))
    nombre: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True)  # turnos360.com/<slug>
    config_pack: Mapped[dict] = mapped_column(JSONB, default=dict)
    # --- Landing pública (turnos360.com/<slug>) ---
    # Todo nullable: las empresas existentes no se rompen y el dueño completa
    # de a poco desde "Mi página". horarios_atencion es SOLO para mostrar
    # (cartel "Lun a Vie 9-19"); los huecos reservables salen del motor de
    # disponibilidad, no de acá. redes (JSONB) guarda instagram/facebook/
    # tiktok/linkedin/sitio_web y futuras sin re-migrar.
    descripcion: Mapped[str | None] = mapped_column(Text)
    direccion: Mapped[str | None] = mapped_column(String(200))
    telefono_publico: Mapped[str | None] = mapped_column(String(40))
    email_publico: Mapped[str | None] = mapped_column(String(120))
    logo_url: Mapped[str | None] = mapped_column(String(300))
    color_marca: Mapped[str | None] = mapped_column(String(7))  # acento, ej. #00d4aa
    horarios_atencion: Mapped[dict | None] = mapped_column(JSONB, default=None)
    redes: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    # Galería de la landing: lista de URLs de fotos del local/trabajos.
    galeria: Mapped[list | None] = mapped_column(JSONB, default=list)
    wa_credenciales: Mapped[bytes | None] = mapped_column(BYTEA)  # Fernet (app.core.crypto)
    email_credenciales: Mapped[bytes | None] = mapped_column(BYTEA)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rubro: Mapped["Rubro"] = relationship()


class Sucursal(TenantMixin, Base):
    """Prevista en E1, se activa en E16 (D-09)."""

    __tablename__ = "sucursal"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    direccion: Mapped[str | None] = mapped_column(String(200))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class Usuario(TenantMixin, Base):
    __tablename__ = "usuario"
    __table_args__ = (UniqueConstraint("empresa_id", "email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int | None] = mapped_column(ForeignKey("sucursal.id"))
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200))
    hash_clave: Mapped[str] = mapped_column(String(300))
    rol: Mapped[RolUsuario] = mapped_column(enum_pg(RolUsuario, "rol_usuario"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    # El recurso (silla/barbero) que opera este usuario, si es un profesional.
    # Decisión 1-a-1: un profesional ↔ un recurso. El FK vive en Recurso.usuario_id;
    # esto es solo la lectura inversa cómoda desde el ORM (usuario.recurso).
    # viewonly=True: el dueño del vínculo es Recurso.usuario_id; se setea desde ahí
    # (panel de usuarios, Bloque 3), nunca desde acá.
    recurso: Mapped["Recurso | None"] = relationship(
        "Recurso",
        primaryjoin="Usuario.id == Recurso.usuario_id",
        uselist=False,
        viewonly=True,
    )


class SuperAdmin(Base):
    """Login separado del de los negocios (E5). Tabla global, sin tenant."""

    __tablename__ = "super_admin"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    hash_clave: Mapped[str] = mapped_column(String(300))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)