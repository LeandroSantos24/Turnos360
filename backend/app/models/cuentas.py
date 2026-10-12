"""Sesiones de los usuarios del panel e invitaciones de alta.

SESIONES
────────
Hasta ahora los tokens no se guardaban en el servidor: lo único que se podía
hacer era invalidarlos TODOS juntos subiendo `usuario.token_version`. No había
forma de ver desde qué dispositivos estaba abierta una cuenta ni de cerrar uno
solo.

Cada login crea una fila acá. El id público de la fila (`sid`) viaja dentro
del JWT (access y refresh); en cada request se comprueba que esa sesión siga
viva. Revocar una sesión es marcar la fila: el siguiente request con ese token
—o el siguiente refresh— da 401. `token_version` sigue funcionando igual para
el «cerrar todo», y además se guarda en la sesión para saber, al listar, si
quedó invalidada por un cambio de clave.

Solo se guarda lo necesario: una etiqueta del dispositivo («Chrome en
Android») sacada del user-agent, sin el user-agent completo ni la IP.

INVITACIONES
────────────
El alta desde el super-admin ya no pide una contraseña: el usuario nace
«pendiente de activación» y recibe un link de un solo uso para elegir la suya.
En la base queda solo el SHA-256 del token.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SesionUsuario(Base):
    __tablename__ = "sesion_usuario"
    __table_args__ = (
        Index("ix_sesion_usuario_usuario", "usuario_id", "creada_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    # Identificador opaco que viaja en el JWT. No es un secreto por sí solo
    # (el token está firmado), pero tampoco es el id autoincremental.
    sid: Mapped[str] = mapped_column(String(32), unique=True)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Se actualiza como mucho una vez por minuto: es «último uso registrado»,
    # no un reloj exacto.
    ultimo_uso_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dispositivo: Mapped[str | None] = mapped_column(String(80))
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Rotación del refresh: solo el último emitido sirve (el anterior, unos
    # segundos, por si dos pestañas renuevan a la vez).
    refresh_jti: Mapped[str | None] = mapped_column(String(32))
    refresh_jti_anterior: Mapped[str | None] = mapped_column(String(32))
    rotado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_revocacion: Mapped[str | None] = mapped_column(String(160))
    revocada_por: Mapped[str | None] = mapped_column(String(160))


class InvitacionUsuario(Base):
    __tablename__ = "invitacion_usuario"
    __table_args__ = (
        # Una sola invitación vigente por usuario: generar otra revoca la anterior.
        Index(
            "uq_invitacion_vigente",
            "usuario_id",
            unique=True,
            postgresql_where=text("usada_en IS NULL AND revocada_en IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), index=True
    )
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresa.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    creada_por: Mapped[str | None] = mapped_column(String(160))
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    enviada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    envio_error: Mapped[str | None] = mapped_column(String(200))
    usada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocada_por: Mapped[str | None] = mapped_column(String(160))
