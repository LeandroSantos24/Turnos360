"""Alta de usuarios por invitación (desde la ficha de la empresa en el super-admin).

El flujo:
1. El admin carga nombre, email y rol. El usuario nace con
   `activacion_pendiente=True` y una contraseña al azar que nadie conoce
   (la columna no admite NULL y así ningún camino viejo lo deja entrar).
2. Se genera un token de 32 bytes; en la base va solo su SHA-256, con
   vencimiento (settings.invitacion_horas) y uso único.
3. Se manda el email con el link /activar?token=… La tarea anota si salió
   (enviada_en) o por qué no (envio_error): el panel muestra el estado real.
4. La persona elige su contraseña: la cuenta se activa, el email queda
   verificado (llegó al link) y la invitación se marca usada.

Reenviar revoca la invitación anterior y crea otra (un único link vivo por
usuario, también garantizado por un índice único parcial). Revocar deja la
cuenta pendiente y sin link.

Nada de esto pasa por el restablecimiento de contraseña: son tokens, columnas
y endpoints separados, para que un link de alta no sirva para robar una
cuenta ya activa ni al revés.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import secrets

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import hash_clave
from app.models import Empresa, InvitacionUsuario, Usuario
from app.services import auditoria_admin as audit

log = logging.getLogger(__name__)

LINK_INVALIDO = "El link no es válido o ya venció. Pedile a quien te invitó que te mande otro."


def _ahora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def vigente(db: Session, usuario_id: int) -> InvitacionUsuario | None:
    return db.scalar(
        select(InvitacionUsuario).where(
            InvitacionUsuario.usuario_id == usuario_id,
            InvitacionUsuario.usada_en.is_(None),
            InvitacionUsuario.revocada_en.is_(None),
        )
    )


def estado(db: Session, usuario: Usuario) -> dict | None:
    """Lo que muestra el panel. None si la cuenta no vino por invitación pendiente."""
    if not usuario.activacion_pendiente:
        return None
    inv = vigente(db, usuario.id)
    if inv is None:
        return {"estado": "sin_invitacion", "expira_en": None, "enviada_en": None, "envio_error": None}
    if inv.expira_en <= _ahora():
        est = "vencida"
    elif inv.envio_error:
        est = "envio_fallido"
    elif inv.enviada_en is None:
        est = "enviando"
    else:
        est = "enviada"
    return {
        "estado": est,
        "creada_en": inv.creada_en.isoformat() if inv.creada_en else None,
        "expira_en": inv.expira_en.isoformat(),
        "enviada_en": inv.enviada_en.isoformat() if inv.enviada_en else None,
        "envio_error": inv.envio_error,
    }


def _emitir(db: Session, usuario: Usuario, creada_por: str) -> tuple[InvitacionUsuario, str]:
    previa = vigente(db, usuario.id)
    if previa is not None:
        previa.revocada_en = _ahora()
        previa.revocada_por = creada_por[:160]
        db.flush()
    token = secrets.token_urlsafe(32)
    inv = InvitacionUsuario(
        usuario_id=usuario.id,
        empresa_id=usuario.empresa_id,
        token_hash=_hash(token),
        creada_por=creada_por[:160],
        expira_en=_ahora() + dt.timedelta(hours=settings.invitacion_horas),
    )
    db.add(inv)
    db.flush()
    return inv, token


def _mandar(db: Session, inv: InvitacionUsuario, token: str) -> None:
    """Encola el email. Si ni siquiera se pudo intentar, lo deja anotado."""
    from app.core.cola import Resultado, encolar
    from app.tasks.emails import enviar_invitacion

    if encolar(enviar_invitacion, inv.id, token) is Resultado.FALLO:
        db.refresh(inv)
        if not inv.envio_error:
            inv.envio_error = "No se pudo mandar el email. Probá reenviar en un rato."
            db.commit()


def crear(db: Session, empresa_id: int, datos, admin, request=None) -> Usuario:
    """Alta con invitación. El email se valida igual que el alta anterior."""
    from app.services import sucursal as sucursal_svc

    if db.get(Empresa, empresa_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")
    existe = db.scalar(select(Usuario).where(func.lower(Usuario.email) == datos.email.lower()))
    if existe:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ya hay un usuario con ese email en este negocio."
            if existe.empresa_id == empresa_id
            else "Ese email ya está en uso en otro negocio del sistema. Cada persona entra con una dirección propia: usá otra.",
        )
    usuario = Usuario(
        empresa_id=empresa_id,
        sucursal_id=sucursal_svc.id_principal(db, empresa_id),
        nombre=datos.nombre,
        email=datos.email,
        hash_clave=hash_clave(secrets.token_urlsafe(32)),
        rol=datos.rol,
        activacion_pendiente=True,
    )
    db.add(usuario)
    db.flush()
    inv, token = _emitir(db, usuario, admin.email)
    audit.auditar(
        db, admin, "invitar_usuario", empresa_id=empresa_id,
        descripcion=f"Invitó a {usuario.nombre} ({usuario.rol.value})",
        request=request,
    )
    db.commit()
    _mandar(db, inv, token)
    db.refresh(usuario)
    return usuario


def _usuario_pendiente(db: Session, usuario_id: int) -> Usuario:
    u = db.get(Usuario, usuario_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado.")
    if not u.activacion_pendiente:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esa cuenta ya está activada.")
    return u


def reenviar(db: Session, usuario_id: int, admin, request=None) -> dict:
    u = _usuario_pendiente(db, usuario_id)
    inv, token = _emitir(db, u, admin.email)
    audit.auditar(
        db, admin, "reenviar_invitacion", empresa_id=u.empresa_id,
        descripcion=f"Reenvió la invitación de {u.nombre}", request=request,
    )
    db.commit()
    _mandar(db, inv, token)
    return estado(db, u) or {}


def revocar(db: Session, usuario_id: int, admin, request=None) -> dict:
    u = _usuario_pendiente(db, usuario_id)
    inv = vigente(db, u.id)
    if inv is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No tiene una invitación vigente.")
    inv.revocada_en = _ahora()
    inv.revocada_por = admin.email[:160]
    audit.auditar(
        db, admin, "revocar_invitacion", empresa_id=u.empresa_id,
        descripcion=f"Revocó la invitación de {u.nombre}", request=request,
    )
    db.commit()
    return estado(db, u) or {}


# ── Lado público ─────────────────────────────────────────────────────────

def _por_token(db: Session, token: str) -> tuple[InvitacionUsuario, Usuario]:
    """Una sola respuesta para todo lo que no sirve (inexistente, vencida,
    usada, revocada): no se revela cuál de las cosas pasó."""
    if not token or len(token) > 200:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, LINK_INVALIDO)
    inv = db.scalar(select(InvitacionUsuario).where(InvitacionUsuario.token_hash == _hash(token)))
    u = db.get(Usuario, inv.usuario_id) if inv else None
    if (
        inv is None
        or u is None
        or inv.usada_en is not None
        or inv.revocada_en is not None
        or inv.expira_en <= _ahora()
        or not u.activacion_pendiente
        or not u.activo
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, LINK_INVALIDO)
    return inv, u


def ver(db: Session, token: str) -> dict:
    inv, u = _por_token(db, token)
    empresa = db.get(Empresa, u.empresa_id)
    return {
        "nombre": (u.nombre or "").split(" ")[0],
        "negocio": empresa.nombre if empresa else None,
        "email": _ocultar(u.email),
    }


def activar(db: Session, token: str, clave: str) -> dict:
    inv, u = _por_token(db, token)
    from app.services import auditoria

    ahora = _ahora()
    u.hash_clave = hash_clave(clave)
    u.activacion_pendiente = False
    # Llegó al link que le mandamos a esa casilla: el email está verificado.
    u.email_verificado = True
    inv.usada_en = ahora
    auditoria.registrar(
        db, accion="activar_cuenta", empresa_id=u.empresa_id, usuario_id=u.id,
        tabla="usuario", registro_id=u.id, detalle={"via": "invitacion"},
    )
    db.commit()
    return {"detalle": "Listo, tu cuenta está activa. Ya podés entrar con tu email y tu contraseña.", "email": u.email}


def _ocultar(email: str) -> str:
    usuario, _, dominio = (email or "").partition("@")
    return (usuario[:2] + "•••" if len(usuario) > 2 else usuario[:1] + "•••") + "@" + dominio
