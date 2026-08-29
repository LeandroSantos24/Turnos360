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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import hash_clave
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


# ══════════════════════════════════════════════════════════════════════════
#  Alta y edición de empleados por el propio dueño
# ══════════════════════════════════════════════════════════════════════════
#
# Antes TODO pasaba por el super-admin: para sumar una recepcionista, o para
# corregirle una letra al nombre, el dueño tenía que escribirle a Leandro. El
# panel solo dejaba ver el equipo y generar un link de contraseña.


def _email_libre(db: Session, email: str, excepto_id: int | None = None) -> None:
    """El email es único en TODO el sistema, no por empresa.

    Es a propósito: el login no pide el negocio, así que dos personas con el
    mismo email en empresas distintas no podrían distinguirse al entrar.
    """
    q = select(Usuario.id).where(func.lower(Usuario.email) == email.lower())
    if excepto_id is not None:
        q = q.where(Usuario.id != excepto_id)
    if db.scalar(q) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya hay una cuenta con ese email. Usá otro.",
        )


def _miembro_de(db: Session, empresa_id: int, usuario_id: int) -> Usuario:
    u = db.get(Usuario, usuario_id)
    if u is None or u.empresa_id != empresa_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese usuario no existe.")
    return u


def crear_miembro(db: Session, empresa_id: int, datos) -> dict:
    """Da de alta un empleado. El rol ya viene acotado por el schema."""
    _email_libre(db, datos.email)
    u = Usuario(
        empresa_id=empresa_id,
        nombre=datos.nombre.strip(),
        email=datos.email,
        hash_clave=hash_clave(datos.clave),
        rol=datos.rol,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return _fila(db, empresa_id, u)


def editar_miembro(
    db: Session, empresa_id: int, usuario_id: int, datos, quien_pide: Usuario
) -> dict:
    """Edita un empleado. Con dos candados que no son opcionales.

    1. El dueño no se puede desactivar ni cambiar de rol a sí mismo. Un click
       distraído en su propio switch lo dejaría afuera de su propio negocio,
       sin nadie adentro que pueda volver a activarlo: habría que arreglarlo
       contra la base.
    2. No se puede tocar a otro dueño ni a un admin. El schema ya impide
       ASIGNAR esos roles; esto impide EDITAR a quien ya los tiene, que es el
       otro lado de la misma puerta.
    """
    u = _miembro_de(db, empresa_id, usuario_id)

    if u.id == quien_pide.id and (
        datos.activo is False or (datos.rol is not None and datos.rol != u.rol)
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No podés desactivarte ni cambiarte el rol a vos mismo: quedarías "
            "afuera de tu propio panel y nadie podría volver a activarte.",
        )

    if u.rol in (RolUsuario.DUENO, RolUsuario.ADMIN) and u.id != quien_pide.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Esa cuenta es de otro dueño o administrador. Para cambiarla, "
            "escribinos.",
        )

    cambios = datos.model_dump(exclude_unset=True)
    if "email" in cambios and cambios["email"]:
        _email_libre(db, cambios["email"], excepto_id=u.id)

    for campo, valor in cambios.items():
        if valor is not None:
            setattr(u, campo, valor.strip() if isinstance(valor, str) else valor)

    db.commit()
    db.refresh(u)
    return _fila(db, empresa_id, u)


def _fila(db: Session, empresa_id: int, u: Usuario) -> dict:
    """La misma forma que devuelve listar_equipo, para una sola persona."""
    recurso = db.scalar(
        select(Recurso.nombre).where(
            Recurso.empresa_id == empresa_id, Recurso.usuario_id == u.id
        )
    )
    return {
        "id": u.id,
        "nombre": u.nombre,
        "email": u.email,
        "rol": u.rol,
        "activo": u.activo,
        "email_recuperable": _email_sirve_para_recuperar(u.email),
        "recurso": recurso,
    }
