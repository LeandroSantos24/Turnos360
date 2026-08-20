"""El equipo del negocio, desde el panel del dueño.

Por qué existe este módulo
--------------------------
Hasta acá los usuarios los creaba y administraba SOLO el super-admin. Para el
dueño de una barbería eso significa que, cuando un empleado se olvida la
contraseña, tiene que escribirle al proveedor y esperar.

Y el flujo normal de "olvidé mi contraseña" no lo cubre: manda un link por
email, y en una barbería la mitad del personal no tiene email cargado, o
tiene uno que no revisa nunca. Esa persona queda sin forma de entrar.

Acá el dueño resuelve solo: genera un link de un solo uso y se lo pasa por
WhatsApp. Reusa exactamente la misma maquinaria del olvidé-mi-contraseña
(token de 32 bytes, solo el hash guardado, 60 minutos, un uso), así que no
hay un segundo camino de seguridad que auditar: es el mismo.

Lo que NO se hace acá, a propósito
----------------------------------
- No se genera una contraseña temporal para mostrarla en pantalla. Una clave
  en texto plano en la UI termina en una captura, en un WhatsApp o en un
  papel pegado al monitor. El link, en cambio, se quema al usarse.
- El dueño no puede tocar a otro DUEÑO. Si pudiera, cualquier dueño
  secuestraría la cuenta del otro dueño del mismo negocio, y eso es una
  escalada de privilegios, no una comodidad.
- El dueño no puede generarse un link a sí mismo: para eso está el flujo
  normal del login, que verifica que tenga acceso a ese email.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Recurso, Usuario
from app.models.enums import RolUsuario
from app.services import auditoria

MINUTOS_VALIDEZ = 60


def _email_sirve_para_recuperar(email: str | None) -> bool:
    """¿Este email puede recibir de verdad un link de recuperación?

    No valida que exista la casilla —eso no se puede saber sin mandar—, pero
    descarta lo que claramente no es una dirección: los "barbero1" y
    "juan@nada" que se cargan cuando el empleado no quiere dar su mail.

    La UI usa esto para avisarle al dueño quién NO va a poder recuperar su
    contraseña por sus propios medios.
    """
    if not email:
        return False
    email = email.strip()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        return False
    dominio = email.rsplit("@", 1)[1]
    return "." in dominio and not dominio.startswith(".") and not dominio.endswith(".")


def listar_equipo(db: Session, empresa_id: int) -> list[dict]:
    """Los usuarios del negocio, con lo que el dueño necesita ver de cada uno."""
    usuarios = list(
        db.scalars(
            select(Usuario)
            .where(Usuario.empresa_id == empresa_id)
            .order_by(Usuario.activo.desc(), Usuario.nombre)
        )
    )

    # Qué recurso opera cada uno (el vínculo vive en Recurso.usuario_id).
    vinculos = {
        r.usuario_id: r.nombre
        for r in db.scalars(
            select(Recurso).where(
                Recurso.empresa_id == empresa_id, Recurso.usuario_id.is_not(None)
            )
        )
    }

    return [
        {
            "id": u.id,
            "nombre": u.nombre,
            "email": u.email,
            "rol": u.rol,
            "activo": u.activo,
            # Le dice a la UI si esta persona puede recuperar su contraseña
            # sola o si depende del dueño.
            "email_recuperable": _email_sirve_para_recuperar(u.email),
            "recurso": vinculos.get(u.id),
        }
        for u in usuarios
    ]


def generar_link_restablecer(
    db: Session,
    *,
    empresa_id: int,
    quien_pide: Usuario,
    usuario_id: int,
    ip: str | None = None,
) -> dict:
    """Genera un link de un solo uso para que un empleado elija contraseña.

    Devuelve la URL lista para copiar o mandar por WhatsApp. El token no se
    guarda en claro en ningún lado: en la base queda solo su hash, igual que
    en el flujo de "olvidé mi contraseña".
    """
    objetivo = db.scalar(
        select(Usuario).where(
            Usuario.id == usuario_id, Usuario.empresa_id == empresa_id
        )
    )
    if objetivo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")

    if objetivo.id == quien_pide.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Para cambiar tu propia contraseña usá Mi cuenta, o "
            "'¿Olvidaste tu contraseña?' desde el login.",
        )

    if objetivo.rol == RolUsuario.DUENO:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "No se puede restablecer la contraseña de otro dueño. Que la "
            "recupere desde el login con su email.",
        )

    if not objetivo.activo:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ese usuario está desactivado. Activalo primero.",
        )

    token = secrets.token_urlsafe(32)
    objetivo.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
    objetivo.reset_token_expira = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        minutes=MINUTOS_VALIDEZ
    )

    # Queda registrado: quién generó el link, para quién, y desde qué IP.
    # Sin esto la acción sería invisible, y es la más delicada que puede
    # hacer un dueño sobre la cuenta de otra persona.
    auditoria.registrar(
        db,
        accion="reset_password",
        empresa_id=empresa_id,
        usuario_id=quien_pide.id,
        tabla="usuario",
        registro_id=objetivo.id,
        detalle={
            "objetivo_nombre": objetivo.nombre,
            "objetivo_rol": objetivo.rol.value,
            "via": "link_del_dueno",
        },
        ip=ip,
    )

    db.commit()

    return {
        "url": f"{settings.public_base_url}/restablecer?token={token}",
        "usuario": objetivo.nombre,
        "vence_en_minutos": MINUTOS_VALIDEZ,
    }
