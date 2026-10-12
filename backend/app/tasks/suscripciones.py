"""Tareas de la suscripción del SaaS: la foto diaria del estado de cada empresa."""

from __future__ import annotations

import logging

from app.celery_app import celery_app
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.suscripciones.foto_diaria")
def foto_diaria() -> dict:
    """Foto de hoy + relleno de los días que falten. Idempotente."""
    from app.services import historial_suscripciones

    with SessionLocal() as db:
        r = historial_suscripciones.tomar_fotos(db)
    log.info("Foto diaria de suscripciones: %s", r)
    return r
