"""Ajustes administrativos: lo que se le cambió a una suscripción sin plata.

Días de cortesía, extensiones por una incidencia, correcciones, cambios de
plan y los movimientos de vencimiento que trae un pago o una devolución. Vive
en `ajuste_suscripcion` (no se duplica en otra tabla) y NUNCA entra en la caja:
la caja lee pagos y devoluciones, no ajustes.

Los ajustes anteriores a la columna `categoria` se muestran con la categoría
que se deduce sin dudas del tipo (pago, plan, devolución, reversión) o como
«sin clasificar».
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AjusteSuscripcion, Empresa
from app.services.cobranza import CATEGORIA_POR_TIPO, TIPOS_AJUSTE

ETIQUETA_CATEGORIA = {
    "cortesia": "Días de cortesía",
    "incidencia": "Extensión por incidencia",
    "correccion": "Corrección administrativa",
    "plan": "Cambio de plan",
    "pago": "Asociado a un pago",
    "devolucion": "Asociado a una devolución",
    None: "Sin clasificar",
}
ETIQUETA_TIPO = {
    "prorroga": "Prórroga", "renovacion": "Renovación sin pago", "manual": "Vencimiento a mano",
    "reversion": "Reversión", "plan": "Cambio de plan", "pago": "Pago", "pago_devuelto": "Pago devuelto",
}
# Lo que se considera beneficio comercial (días que se dieron sin cobrar).
BENEFICIOS = ("cortesia", "incidencia")


def categoria_de(aj: AjusteSuscripcion) -> str | None:
    return aj.categoria or CATEGORIA_POR_TIPO.get(aj.tipo)


def _dias(aj: AjusteSuscripcion) -> int | None:
    if aj.vence_antes and aj.vence_despues:
        return (aj.vence_despues - aj.vence_antes).days
    return aj.dias


def a_dict(aj: AjusteSuscripcion, empresa: str | None) -> dict:
    cat = categoria_de(aj)
    return {
        "id": aj.id,
        "empresa_id": aj.empresa_id,
        "empresa": empresa,
        "fecha": aj.creado_en.isoformat() if aj.creado_en else None,
        "tipo": aj.tipo,
        "tipo_etiqueta": ETIQUETA_TIPO.get(aj.tipo, aj.tipo),
        "categoria": cat,
        "categoria_etiqueta": ETIQUETA_CATEGORIA.get(cat, cat),
        "clasificado": aj.categoria is not None,
        "vence_antes": aj.vence_antes.isoformat() if aj.vence_antes else None,
        "vence_despues": aj.vence_despues.isoformat() if aj.vence_despues else None,
        "dias": _dias(aj),
        "plan_antes": aj.plan_antes,
        "plan_despues": aj.plan_despues,
        "hecho_por": aj.hecho_por,
        "actor": aj.actor_tipo,
        "motivo": aj.motivo,
        "detalle": aj.detalle,
        "estado": "revertido" if aj.revertido else "vigente",
        "revertido_por": aj.revertido_por,
        "pago_id": aj.pago_id,
    }


def _rango_utc(desde: dt.date | None, hasta: dt.date | None):
    zona = ZoneInfo(settings.zona_horaria)
    d0 = dt.datetime.combine(desde, dt.time.min, zona) if desde else None
    d1 = dt.datetime.combine(hasta + dt.timedelta(days=1), dt.time.min, zona) if hasta else None
    return d0, d1


def listar(
    db: Session,
    *,
    empresa_id: int | None = None,
    admin_email: str | None = None,
    categoria: str | None = None,
    desde: dt.date | None = None,
    hasta: dt.date | None = None,
    incluir_automaticos: bool = False,
    pagina: int = 1,
    limite: int = 50,
) -> dict:
    if categoria and categoria not in ETIQUETA_CATEGORIA and categoria != "sin_clasificar":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Categoría desconocida.")
    q = select(AjusteSuscripcion, Empresa.nombre).join(Empresa, Empresa.id == AjusteSuscripcion.empresa_id).where(
        AjusteSuscripcion.tipo.in_(TIPOS_AJUSTE)
    )
    if not incluir_automaticos:
        # Lo que hizo una persona desde el panel (los pagos de MP o del
        # sistema se ven en Cobros).
        q = q.where(AjusteSuscripcion.actor_tipo == "admin")
    if empresa_id:
        q = q.where(AjusteSuscripcion.empresa_id == empresa_id)
    if admin_email:
        q = q.where(AjusteSuscripcion.hecho_por.ilike(f"%{admin_email.strip()}%"))
    if categoria == "sin_clasificar":
        q = q.where(AjusteSuscripcion.categoria.is_(None), AjusteSuscripcion.tipo.notin_(tuple(CATEGORIA_POR_TIPO)))
    elif categoria:
        tipos = [t for t, c in CATEGORIA_POR_TIPO.items() if c == categoria]
        cond = AjusteSuscripcion.categoria == categoria
        if tipos:
            cond = cond | (AjusteSuscripcion.categoria.is_(None) & AjusteSuscripcion.tipo.in_(tipos))
        q = q.where(cond)
    d0, d1 = _rango_utc(desde, hasta)
    if d0:
        q = q.where(AjusteSuscripcion.creado_en >= d0)
    if d1:
        q = q.where(AjusteSuscripcion.creado_en < d1)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    limite = max(1, min(limite, 200))
    filas = db.execute(
        q.order_by(AjusteSuscripcion.creado_en.desc(), AjusteSuscripcion.id.desc())
        .limit(limite).offset((max(1, pagina) - 1) * limite)
    ).all()
    return {
        "total": int(total), "pagina": max(1, pagina), "limite": limite,
        "filas": [a_dict(a, nombre) for a, nombre in filas],
        "categorias": {k or "sin_clasificar": v for k, v in ETIQUETA_CATEGORIA.items()},
    }


def beneficios(db: Session, desde: dt.date, hasta: dt.date, granularidad: str = "mes") -> dict:
    """Días otorgados sin cobrar, por período. Indicador COMERCIAL: no es plata
    y no se suma a ningún ingreso ni egreso."""
    from app.services.admin_finanzas import _inicio_bucket

    zona = ZoneInfo(settings.zona_horaria)
    d0, d1 = _rango_utc(desde, hasta)
    filas = db.scalars(
        select(AjusteSuscripcion).where(
            AjusteSuscripcion.tipo.in_(("prorroga", "renovacion", "manual")),
            AjusteSuscripcion.revertido.is_(False),
            AjusteSuscripcion.creado_en >= d0,
            AjusteSuscripcion.creado_en < d1,
        )
    ).all()
    buckets: dict[str, dict] = defaultdict(lambda: {"dias_cortesia": 0, "dias_incidencia": 0, "dias_sin_clasificar": 0, "ajustes": 0, "empresas": set()})
    for aj in filas:
        dias = _dias(aj) or 0
        if dias <= 0:
            continue
        cat = aj.categoria
        # Las correcciones no son un beneficio (arreglan un error).
        if cat not in (None, *BENEFICIOS):
            continue
        clave = _inicio_bucket(aj.creado_en.astimezone(zona).date(), granularidad).isoformat()
        b = buckets[clave]
        b[f"dias_{cat}" if cat else "dias_sin_clasificar"] += dias
        b["ajustes"] += 1
        b["empresas"].add(aj.empresa_id)
    serie = [
        {"periodo": k, **{x: v for x, v in b.items() if x != "empresas"}, "empresas": len(b["empresas"])}
        for k, b in sorted(buckets.items())
    ]
    total_emp = {e for b in buckets.values() for e in b["empresas"]}
    return {
        "serie": serie,
        "total": {
            "dias_cortesia": sum(b["dias_cortesia"] for b in serie),
            "dias_incidencia": sum(b["dias_incidencia"] for b in serie),
            "dias_sin_clasificar": sum(b["dias_sin_clasificar"] for b in serie),
            "ajustes": sum(b["ajustes"] for b in serie),
            "empresas": len(total_emp),
        },
        "nota": "Días de servicio dados sin cobrar (cortesías y extensiones por incidencias, sin las revertidas). No es plata: no se suma a ingresos ni a la caja.",
    }
