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
                "activacion_pendiente": bool(u.activacion_pendiente),
                "ultimo_ingreso_en": u.ultimo_ingreso_en.isoformat() if u.ultimo_ingreso_en else None,
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
        from app.services import sesiones

        sesiones.revocar_todas(db, u, "Se cortó el acceso", getattr(admin, "email", "admin"))
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
        from app.services import sesiones

        sesiones.revocar_todas(
            db, u, "Restablecimiento de contraseña iniciado por soporte", getattr(admin, "email", "admin")
        )
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


# ── Sesiones y actividad ──────────────────────────────────────────────────

def _usuario_o_404(db: Session, usuario_id: int) -> Usuario:
    u = db.get(Usuario, usuario_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado.")
    return u


def sesiones_de(db: Session, usuario_id: int) -> dict:
    """Ficha de actividad: sesiones (últimas 50), último ingreso, invitación
    y el historial de ingresos y cierres armado con esas mismas filas."""
    from app.services import invitaciones, sesiones

    u = _usuario_o_404(db, usuario_id)
    ahora = dt.datetime.now(dt.timezone.utc)
    filas = sesiones.de_usuario(db, u)
    lista = [sesiones.a_dict(s, u, ahora) for s in filas]
    historial: list[dict] = []
    for s in filas:
        historial.append({"fecha": s.creada_en.isoformat() if s.creada_en else None, "tipo": "ingreso",
                          "detalle": s.dispositivo or "Dispositivo sin identificar", "por": None})
        if s.revocada_en:
            historial.append({"fecha": s.revocada_en.isoformat(), "tipo": "cierre",
                              "detalle": s.motivo_revocacion or "Sesión cerrada", "por": s.revocada_por})
    historial.sort(key=lambda h: h["fecha"] or "", reverse=True)
    emp = db.get(Empresa, u.empresa_id)
    return {
        "usuario": {
            "id": u.id, "nombre": u.nombre, "email": u.email, "rol": u.rol.value,
            "activo": bool(u.activo), "empresa_id": u.empresa_id, "empresa": emp.nombre if emp else None,
            "ultimo_ingreso_en": u.ultimo_ingreso_en.isoformat() if u.ultimo_ingreso_en else None,
            "activacion_pendiente": bool(u.activacion_pendiente),
        },
        "invitacion": invitaciones.estado(db, u),
        "activas": sum(1 for s in lista if s["estado"] == "activa"),
        "sesiones": lista,
        "historial": historial[:100],
        # Lo que hace falta para leer bien la pantalla.
        "notas": [
            "El último uso se registra como mucho una vez por minuto.",
            "Las sesiones abiertas antes de esta función no figuran: aparecen la próxima vez que esa pestaña renueve su acceso.",
        ],
    }


def revocar_sesion(db: Session, usuario_id: int, sesion_id: int, motivo: str, admin, request=None) -> dict:
    from app.models import SesionUsuario
    from app.services import sesiones

    u = _usuario_o_404(db, usuario_id)
    s = db.get(SesionUsuario, sesion_id)
    # La sesión tiene que ser de ESE usuario: un id de otra cuenta da 404.
    if s is None or s.usuario_id != u.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sesión no encontrada.")
    if not sesiones.revocar(db, s, motivo.strip(), admin.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Esa sesión ya estaba cerrada.")
    audit.auditar(
        db, admin, "revocar_sesion", empresa_id=u.empresa_id,
        descripcion=f"Cerró la sesión {s.dispositivo or ''} de {u.nombre}: {motivo.strip()[:150]}",
        request=request,
    )
    db.commit()
    return sesiones_de(db, u.id)


def cerrar_todas(db: Session, usuario_id: int, motivo: str, admin, request=None) -> dict:
    from app.services import sesiones

    u = _usuario_o_404(db, usuario_id)
    n = sesiones.revocar_todas(db, u, motivo.strip(), admin.email)
    audit.auditar(
        db, admin, "cerrar_sesiones", empresa_id=u.empresa_id,
        descripcion=f"Cerró todas las sesiones de {u.nombre} ({n}): {motivo.strip()[:150]}",
        request=request,
    )
    db.commit()
    return sesiones_de(db, u.id)
