"""Cálculo de estadísticas de facturación sobre los pagos reales."""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Recurso
from app.models.agenda import Servicio
from app.models.enums import EstadoTurno
from app.models.finanzas import MetodoPago, Pago
from app.models.turno import Turno


def facturacion(
    db: Session,
    empresa_id: int,
    desde: dt.datetime,
    hasta: dt.datetime,
    recurso_id: int | None = None,
) -> dict:
    """Resumen de lo cobrado en el rango: totales, por método, por profesional y por día.

    Si recurso_id viene, TODO el panel se filtra a ese profesional: sus pagos,
    sus servicios, sus horarios y su ausentismo.
    """
    cond = [
        Pago.empresa_id == empresa_id,
        Pago.fecha >= desde,
        Pago.fecha < hasta,
    ]
    # Los pagos no tienen recurso directo: se filtran por el turno del recurso.
    if recurso_id is not None:
        cond.append(
            Pago.turno_id.in_(
                select(Turno.id).where(
                    Turno.empresa_id == empresa_id,
                    Turno.recurso_id == recurso_id,
                )
            )
        )

    facturado = float(
        db.scalar(select(func.coalesce(func.sum(Pago.monto), 0)).where(*cond)) or 0
    )
    comision = float(
        db.scalar(
            select(func.coalesce(func.sum(Pago.comision_aplicada), 0)).where(*cond)
        )
        or 0
    )
    cantidad = int(db.scalar(select(func.count(Pago.id)).where(*cond)) or 0)

    # Período anterior (mismo lapso justo antes de 'desde'), para la variación %.
    lapso = hasta - desde
    ant_desde = desde - lapso
    cond_ant = [
        Pago.empresa_id == empresa_id,
        Pago.fecha >= ant_desde,
        Pago.fecha < desde,
    ]
    if recurso_id is not None:
        cond_ant.append(
            Pago.turno_id.in_(
                select(Turno.id).where(
                    Turno.empresa_id == empresa_id,
                    Turno.recurso_id == recurso_id,
                )
            )
        )
    facturado_anterior = float(
        db.scalar(select(func.coalesce(func.sum(Pago.monto), 0)).where(*cond_ant)) or 0
    )
    if facturado_anterior > 0:
        variacion_pct = round((facturado - facturado_anterior) / facturado_anterior * 100, 1)
    else:
        variacion_pct = None  # sin base de comparación

    # Por método de pago
    filas_m = db.execute(
        select(MetodoPago.nombre, func.coalesce(func.sum(Pago.monto), 0))
        .select_from(Pago)
        .join(MetodoPago, Pago.metodo_pago_id == MetodoPago.id, isouter=True)
        .where(*cond)
        .group_by(MetodoPago.nombre)
        .order_by(func.coalesce(func.sum(Pago.monto), 0).desc())
    ).all()
    por_metodo = [
        {"metodo": n or "Sin método", "total": float(t)} for n, t in filas_m
    ]

    # Por profesional (el pago se une al turno para saber qué barbero atendió)
    filas_p = db.execute(
        select(
            Recurso.nombre,
            func.coalesce(func.sum(Pago.monto), 0),
            func.count(func.distinct(Turno.id)),
        )
        .select_from(Pago)
        .join(Turno, Pago.turno_id == Turno.id)
        .join(Recurso, Turno.recurso_id == Recurso.id)
        .where(*cond)
        .group_by(Recurso.nombre)
        .order_by(func.coalesce(func.sum(Pago.monto), 0).desc())
    ).all()
    por_profesional = [
        {"recurso": n, "total": float(t), "turnos": int(c)} for n, t, c in filas_p
    ]

    # Evolución diaria
    filas_d = db.execute(
        select(func.date(Pago.fecha), func.coalesce(func.sum(Pago.monto), 0))
        .where(*cond)
        .group_by(func.date(Pago.fecha))
        .order_by(func.date(Pago.fecha))
    ).all()
    por_dia = [{"fecha": str(f), "total": float(t)} for f, t in filas_d]

    # ── Turnos por estado (ausentismo) ─ sobre la agenda, no sobre pagos ──
    # Miramos los turnos del período por su fecha de inicio, y contamos cómo
    # terminaron. La tasa de ausentismo = ausentes / (finalizados + ausentes).
    cond_turno = [
        Turno.empresa_id == empresa_id,
        Turno.fecha_inicio >= desde,
        Turno.fecha_inicio < hasta,
    ]
    if recurso_id is not None:
        cond_turno.append(Turno.recurso_id == recurso_id)
    filas_estado = db.execute(
        select(Turno.estado, func.count(Turno.id))
        .where(*cond_turno)
        .group_by(Turno.estado)
    ).all()
    conteo = {str(e.value if hasattr(e, "value") else e): int(c) for e, c in filas_estado}
    finalizados = conteo.get("finalizado", 0)
    cancelados = conteo.get("cancelado", 0)
    ausentes = conteo.get("ausente", 0)
    base_asistencia = finalizados + ausentes
    tasa_ausentismo = round(ausentes / base_asistencia * 100, 1) if base_asistencia else 0.0
    estados = {
        "finalizados": finalizados,
        "cancelados": cancelados,
        "ausentes": ausentes,
        "tasa_ausentismo": tasa_ausentismo,
    }

    # ── Servicios más pedidos (por facturación) ──
    filas_serv = db.execute(
        select(
            Servicio.nombre,
            func.count(func.distinct(Turno.id)),
            func.coalesce(func.sum(Pago.monto), 0),
        )
        .select_from(Turno)
        .join(Servicio, Turno.servicio_id == Servicio.id)
        .join(Pago, Pago.turno_id == Turno.id, isouter=True)
        .where(
            *cond_turno,
            Turno.estado == EstadoTurno.FINALIZADO,
        )
        .group_by(Servicio.nombre)
        .order_by(func.coalesce(func.sum(Pago.monto), 0).desc())
    ).all()
    por_servicio = [
        {"servicio": n, "cantidad": int(c), "total": float(t)}
        for n, c, t in filas_serv
    ]

    # ── Horarios más demandados (por hora del día) ──
    # Contamos turnos finalizados agrupados por la hora de inicio (0-23).
    filas_hora = db.execute(
        select(
            func.extract("hour", Turno.fecha_inicio),
            func.count(Turno.id),
        )
        .where(
            *cond_turno,
            Turno.estado == EstadoTurno.FINALIZADO,
        )
        .group_by(func.extract("hour", Turno.fecha_inicio))
        .order_by(func.extract("hour", Turno.fecha_inicio))
    ).all()
    por_hora = [
        {"hora": int(h), "cantidad": int(c)} for h, c in filas_hora if h is not None
    ]

    ticket = facturado / cantidad if cantidad else 0.0

    return {
        "facturado_real": facturado,
        "facturado_anterior": facturado_anterior,
        "variacion_pct": variacion_pct,
        "comision_total": comision,
        "neto": facturado - comision,
        "cantidad_pagos": cantidad,
        "ticket_promedio": round(ticket, 2),
        "por_metodo": por_metodo,
        "por_profesional": [
            {
                **p,
                "ticket": round(p["total"] / p["turnos"], 2) if p["turnos"] else 0.0,
                "pct": round(p["total"] / facturado * 100, 1) if facturado else 0.0,
            }
            for p in por_profesional
        ],
        "por_dia": por_dia,
        "estados": estados,
        "por_servicio": por_servicio,
        "por_hora": por_hora,
    }