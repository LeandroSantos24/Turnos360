"""Auditoría de las acciones del super-admin.

Toda acción del panel que toca plata, acceso o una suscripción deja una fila
en `auditoria_admin`: quién, cuándo, desde qué IP, sobre qué empresa y cómo
estaba la suscripción ANTES y DESPUÉS. Es append-only: no hay función ni
endpoint que la modifique o la borre.

La fila se agrega a la MISMA transacción que la acción: si la acción se
revierte, la auditoría también, y nunca queda registrada una acción que no
pasó (ni una acción sin registro).
"""

from __future__ import annotations

import ipaddress
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditoriaAdmin, Empresa

# Qué se fotografía de la empresa antes y después. Ningún dato sensible: ni
# tokens, ni claves, ni datos de tarjeta (que tampoco existen en la base).
_CAMPOS = (
    "plan",
    "plan_programado",
    "suscripcion_vence",
    "prueba_hasta",
    "activa",
    "precio_mensual",
    "limite_recursos",
    "limite_sucursales",
    "cancela_al_vencer",
)


def foto(db: Session | None, empresa: Empresa | None) -> dict | None:
    """Estado de la suscripción en un dict serializable (para antes/después)."""
    if empresa is None:
        return None
    datos: dict[str, Any] = {}
    for campo in _CAMPOS:
        valor = getattr(empresa, campo, None)
        if hasattr(valor, "isoformat"):
            valor = valor.isoformat()
        elif valor is not None and not isinstance(valor, (bool, int, str)):
            valor = float(valor)
        datos[campo] = valor
    if db is not None:
        from app.services.suscripcion import estado_suscripcion

        datos["estado"] = estado_suscripcion(empresa, db)["estado"]
    return datos


def ip_de(request) -> str | None:
    if request is None:
        return None
    candidata = (request.headers.get("x-real-ip") or "").strip()
    if not candidata and request.client:
        candidata = request.client.host
    try:
        return str(ipaddress.ip_address(candidata))
    except ValueError:
        return None


def auditar(
    db: Session,
    admin,
    accion: str,
    *,
    empresa_id: int | None = None,
    descripcion: str | None = None,
    antes: dict | None = None,
    despues: dict | None = None,
    request=None,
) -> AuditoriaAdmin:
    """Agrega la fila a la sesión. NO hace commit: va con la acción."""
    fila = AuditoriaAdmin(
        admin_id=getattr(admin, "id", None),
        admin_email=(getattr(admin, "email", None) or str(admin or "desconocido"))[:160],
        accion=accion[:40],
        empresa_id=empresa_id,
        descripcion=(descripcion or "")[:300] or None,
        antes=antes,
        despues=despues,
        ip=ip_de(request),
    )
    db.add(fila)
    return fila


ETIQUETAS = {
    "aprobar_pago": "Aprobó un pago",
    "rechazar_pago": "Rechazó un pago",
    "solicitar_info": "Pidió información de un pago",
    "registrar_pago": "Registró un pago",
    "prorroga": "Dio días de gracia",
    "renovar_manual": "Renovó sin pago",
    "cambiar_vencimiento": "Cambió el vencimiento",
    "cambiar_plan": "Cambió el plan",
    "suspender": "Suspendió la cuenta",
    "reanudar": "Reanudó la cuenta",
    "cancelar": "Canceló la suscripción",
    "reactivar": "Reactivó la suscripción",
    "revertir": "Revirtió un movimiento",
    "ficha": "Editó la ficha comercial",
    "ver_comprobante": "Vio un comprobante",
}


def listar(db: Session, empresa_id: int | None = None, limite: int = 100) -> list[dict]:
    q = select(AuditoriaAdmin).order_by(AuditoriaAdmin.creado_en.desc(), AuditoriaAdmin.id.desc())
    if empresa_id is not None:
        q = q.where(AuditoriaAdmin.empresa_id == empresa_id)
    filas = db.scalars(q.limit(min(max(limite, 1), 500))).all()
    nombres = {}
    ids = {f.empresa_id for f in filas if f.empresa_id}
    if ids:
        nombres = dict(db.execute(select(Empresa.id, Empresa.nombre).where(Empresa.id.in_(ids))).all())
    return [
        {
            "id": f.id,
            "creado_en": f.creado_en.isoformat() if f.creado_en else None,
            "admin_email": f.admin_email,
            "accion": f.accion,
            "accion_etiqueta": ETIQUETAS.get(f.accion, f.accion),
            "empresa_id": f.empresa_id,
            "empresa_nombre": nombres.get(f.empresa_id),
            "descripcion": f.descripcion,
            "antes": f.antes,
            "despues": f.despues,
            "ip": f.ip,
        }
        for f in filas
    ]
