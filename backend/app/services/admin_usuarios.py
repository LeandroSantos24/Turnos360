"""Usuarios y accesos, vistos desde el super-admin (todos los negocios).

El super-admin NUNCA ve ni cambia una contraseña. Lo que puede hacer es
iniciar un restablecimiento: se genera un link de un solo uso que vence en 60
minutos y se le manda al usuario a SU email (el canal que ya tiene). El link
no se le muestra al admin: así nadie del lado de soporte puede entrar a una
cuenta ajena. Queda en la auditoría quién lo inició y cuándo.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Empresa, Usuario
from app.models.enums import RolUsuario
from app.models.organizacion import Sucursal
from app.services import auditoria_admin as audit

MINUTOS_VALIDEZ = 60


def listar(
    db: Session,
    *,
    buscar: str | None = None,
    empresa_id: int | None = None,
    rol: str | None = None,
    activo: bool | None = None,
    limite: int = 50,
    pagina: int = 1,
) -> dict:
    q = select(Usuario, Empresa.nombre, Sucursal.nombre).join(Empresa, Empresa.id == Usuario.empresa_id).outerjoin(
        Sucursal, Sucursal.id == Usuario.sucursal_id
    )
    if empresa_id:
        q = q.where(Usuario.empresa_id == empresa_id)
    if rol:
        try:
            q = q.where(Usuario.rol == RolUsuario(rol))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Rol desconocido.")
    if activo is not None:
        q = q.where(Usuario.activo.is_(activo))
    if buscar and buscar.strip():
        b = f"%{buscar.strip().lower()}%"
        q = q.where(or_(func.lower(Usuario.nombre).like(b), func.lower(Usuario.email).like(b), func.lower(Empresa.nombre).like(b)))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    limite = max(1, min(limite, 200))
    pagina = max(1, pagina)
    filas = db.execute(q.order_by(Empresa.nombre, Usuario.nombre).limit(limite).offset((pagina - 1) * limite)).all()
    ahora = dt.datetime.now(dt.timezone.utc)
    return {
        "total": int(total),
        "pagina": pagina,
        "limite": limite,
        "filas": [
            {
                "id": u.id,
                "nombre": u.nombre,
                "email": u.email,
                "rol": u.rol.value,
                "activo": bool(u.activo),
                "email_verificado": bool(u.email_verificado),
                "empresa_id": u.empresa_id,
                "empresa": emp,
                "sucursal": suc,
                "restablecimiento_pendiente": bool(
                    u.reset_token_hash and u.reset_token_expira and u.reset_token_expira > ahora
                ),
            }
            for u, emp, suc in filas
        ],
    }


def cambiar_acceso(db: Session, usuario_id: int, *, activo: bool, motivo: str | None, admin, request=None) -> dict:
    u = db.get(Usuario, usuario_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado.")
    if u.activo == activo:
        return {"id": u.id, "activo": u.activo}
    u.activo = activo
    if not activo:
        # Desactivar corta también las sesiones abiertas.
        u.token_version = int(u.token_version or 0) + 1
    audit.auditar(
        db, admin, "acceso_usuario", empresa_id=u.empresa_id,
        descripcion=f"{'Activó' if activo else 'Desactivó'} el acceso de {u.nombre} ({u.rol.value})"
        + (f": {motivo.strip()[:150]}" if motivo and motivo.strip() else ""),
        request=request,
    )
    db.commit()
    return {"id": u.id, "activo": u.activo}


def iniciar_restablecimiento(db: Session, usuario_id: int, *, cerrar_sesiones: bool, admin, request=None) -> dict:
    from app.core.cola import Resultado, encolar
    from app.tasks.emails import enviar_reset_password

    u = db.get(Usuario, usuario_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado.")
    if not u.activo:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese usuario está desactivado. Activalo primero.")
    if not (u.email or "").strip() or "@" not in u.email:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ese usuario no tiene un email válido: no hay un canal seguro para mandarle el link.",
        )
    token = secrets.token_urlsafe(32)
    u.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
    u.reset_token_expira = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=MINUTOS_VALIDEZ)
    if cerrar_sesiones:
        u.token_version = int(u.token_version or 0) + 1
    audit.auditar(
        db, admin, "restablecer_clave", empresa_id=u.empresa_id,
        descripcion=f"Inició el restablecimiento de contraseña de {u.nombre} ({u.rol.value})"
        + (" y cerró sus sesiones" if cerrar_sesiones else ""),
        request=request,
    )
    db.commit()
    if encolar(enviar_reset_password, u.id, token, True) is Resultado.FALLO:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Se generó el link pero no se pudo mandar el email. Probá de nuevo en un rato.",
        )
    return {
        "ok": True,
        "detalle": f"Le mandamos a {_ocultar(u.email)} un link que vence en {MINUTOS_VALIDEZ} minutos y sirve una sola vez.",
        "sesiones_cerradas": cerrar_sesiones,
    }


def _ocultar(email: str) -> str:
    usuario, _, dominio = email.partition("@")
    return (usuario[:2] + "•••" if len(usuario) > 2 else usuario[:1] + "•••") + "@" + dominio
