"""Tenant y organización: Rubro (catálogo global), Empresa, Sucursal, Usuario, SuperAdmin.

Regla 1: TODA tabla de negocio hereda TenantMixin → empresa_id NOT NULL + índice.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import datetime as dt

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func, text, Numeric
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
    # Foto de fondo del hero de la vidriera (el local, una toma del trabajo).
    # Si está vacía, el hero queda blanco como hasta ahora.
    portada_url: Mapped[str | None] = mapped_column(String(300))
    color_marca: Mapped[str | None] = mapped_column(String(7))  # acento, ej. #00d4aa

    # --- Reglas de la reserva pública (configurables por el dueño) ---------
    # Antes vivían hardcodeadas en services/publico.py e iguales para todos.
    reserva_anticipacion_min: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    reserva_dias_max: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="180"
    )
    # Cierre fijo de agenda. Manda la MÁS restrictiva entre esta y dias_max.
    reserva_fecha_limite: Mapped[dt.date | None] = mapped_column(Date)
    reserva_permite_cancelar: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    reserva_pide_telefono: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    reserva_pide_nacimiento: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # --- Seguimiento publicitario de la vidriera ---------------------------
    # IDs públicos (viajan en el HTML de cualquier sitio que los use). El
    # formato se valida en el schema ANTES de escribirlos en un <script>.
    meta_pixel_id: Mapped[str | None] = mapped_column(String(40))
    google_tag_id: Mapped[str | None] = mapped_column(String(40))
    horarios_atencion: Mapped[dict | None] = mapped_column(JSONB, default=None)
    redes: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    # Galería de la landing: lista de URLs de fotos del local/trabajos.
    galeria: Mapped[list | None] = mapped_column(JSONB, default=list)
    wa_credenciales: Mapped[bytes | None] = mapped_column(BYTEA)  # Fernet (app.core.crypto)
    email_credenciales: Mapped[bytes | None] = mapped_column(BYTEA)

    # Campañas / automatizaciones del negocio (switches + config de cada una).
    automatizaciones: Mapped[dict | None] = mapped_column(JSONB)

    # Señas con Mercado Pago (opcional por empresa). Token encriptado (Regla 7).
    mp_credenciales: Mapped[bytes | None] = mapped_column(BYTEA)
    sena_activa: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Qué se cobra al reservar online: "ninguno" | "sena" (monto fijo) | "total"
    # (el precio del servicio). Lo elige el negocio.
    cobro_modo: Mapped[str] = mapped_column(
        String(10), default="ninguno", server_default="ninguno"
    )
    sena_monto: Mapped[float | None] = mapped_column(Numeric(12, 2))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    # Suscripción: el plan y hasta cuándo está paga. La prórroga (días de
    # gracia tras el vencimiento) se define globalmente, no por empresa.
    plan: Mapped[str] = mapped_column(
        String(20), default="gratuito", server_default="gratuito"
    )
    suscripcion_vence: Mapped[dt.date | None] = mapped_column(Date)
    # Fin del período de prueba. NULL = cliente normal.
    # Mientras hoy <= prueba_hasta el negocio NO es moroso ni cliente al día:
    # es un estado propio, y mezclarlo con cualquiera de los dos ensucia el
    # MRR y la deuda vencida del panel de cobranza.
    prueba_hasta: Mapped[dt.date | None] = mapped_column(Date)

    # ── Datos comerciales (los ve solo el super-admin) ──────────────────
    # Ficha del cliente del SaaS: a quién le facturo y por cuánto. Nada de
    # esto lo ve el negocio en su panel.
    razon_social: Mapped[str | None] = mapped_column(String(160))
    cuit: Mapped[str | None] = mapped_column(String(20))
    contacto_nombre: Mapped[str | None] = mapped_column(String(120))
    contacto_email: Mapped[str | None] = mapped_column(String(160))
    contacto_telefono: Mapped[str | None] = mapped_column(String(40))
    notas_admin: Mapped[str | None] = mapped_column(Text)

    # Precio mensual pactado con ESTE negocio (puede diferir del precio de
    # lista: pilotos bonificados, descuentos por referido). Es la base del
    # MRR y del "pendiente estimado" de la cobranza.
    precio_mensual: Mapped[float | None] = mapped_column(Numeric(12, 2))

    # Tope de profesionales según el plan. None = sin límite.
    limite_recursos: Mapped[int | None] = mapped_column()
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
    # El email identifica a la PERSONA en todo el sistema, no dentro de su
    # empresa. Antes era UNIQUE(empresa_id, email), pero el login busca por
    # email SIN empresa (el usuario todavía no dijo a cuál entra), y
    # Session.scalar() con varias filas devuelve una al azar en vez de
    # fallar. Con la misma persona en dos negocios eso significaba entrar a
    # la empresa equivocada, o quedar afuera de una de las dos sin ninguna
    # explicación.
    #
    # Va sobre lower(email) porque para una persona Juan@Gmail.com y
    # juan@gmail.com son la misma dirección, y si el sistema las trata como
    # dos cuentas vuelve el mismo problema por otra puerta.
    #
    # Índice y no UniqueConstraint: Postgres no admite expresiones en una
    # constraint.
    __table_args__ = (
        Index("uq_usuario_email_lower", text("lower(email)"), unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int | None] = mapped_column(ForeignKey("sucursal.id"))
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200))
    hash_clave: Mapped[str] = mapped_column(String(300))
    rol: Mapped[RolUsuario] = mapped_column(enum_pg(RolUsuario, "rol_usuario"))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Recuperación de contraseña: HASH del token de un solo uso + expiración.
    reset_token_hash: Mapped[str | None] = mapped_column(String(128))
    reset_token_expira: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    # Revocación de sesiones. Viaja dentro del JWT (claim 'tv') y se compara en
    # cada request: al cambiar o restablecer la contraseña se incrementa, y todos
    # los tokens emitidos antes —incluido el refresh de 7 días que pueda tener un
    # atacante en otro dispositivo— dejan de servir en el acto.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

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