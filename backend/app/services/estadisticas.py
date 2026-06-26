"""Cálculo de estadísticas de facturación sobre los pagos reales."""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Recurso
from app.models.finanzas import MetodoPago, Pago
from app.models.turno import Turno


def facturacion(
    db: Session, empresa_id: int, desde: dt.datetime, hasta: dt.datetime
) -> dict:
    """Resumen de lo cobrado en el rango: totales, por método, por profesional y por día."""
    cond = [
        Pago.empresa_id == empresa_id,
        Pago.fecha >= desde,
        Pago.fecha < hasta,
    ]

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

    ticket = facturado / cantidad if cantidad else 0.0

    return {
        "facturado_real": facturado,
        "comision_total": comision,
        "neto": facturado - comision,
        "cantidad_pagos": cantidad,
        "ticket_promedio": round(ticket, 2),
        "por_metodo": por_metodo,
        "por_profesional": por_profesional,
        "por_dia": por_dia,
    }