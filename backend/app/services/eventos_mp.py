"""Registro de las notificaciones del webhook de Mercado Pago (cuenta Turnos360).

Es lo que alimenta el estado de la integración en el panel: último aviso
recibido, último procesado bien y errores recientes. Registrar nunca puede
voltear el webhook: si falla, se loguea y se sigue.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import EventoMP

log = logging.getLogger("turnos360.mp_eventos")


def registrar(
    db: Session,
    *,
    tipo: str,
    resultado: str,
    accion: str | None = None,
    recurso_id: str | None = None,
    detalle: str | None = None,
) -> None:
    try:
        db.add(
            EventoMP(
                tipo=(tipo or "?")[:60],
                accion=(accion or None) and accion[:40],
                recurso_id=(recurso_id or None) and str(recurso_id)[:64],
                resultado=resultado[:20],
                detalle=(detalle or None) and detalle[:300],
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        log.exception("No se pudo registrar el evento de Mercado Pago")
