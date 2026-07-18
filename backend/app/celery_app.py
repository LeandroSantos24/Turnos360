"""Celery de Turnos360 (Regla 6: la mensajería SIEMPRE va por cola).

- Worker:  docker compose ... exec / servicio "worker" del compose
- Beat:    servicio "beat" del compose — dispara el barrido de recordatorios.

El broker es el Redis que ya corre en el stack.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "turnos360",
    broker=settings.redis_url,
    include=["app.tasks.emails"],
)

celery_app.conf.update(
    timezone="America/Argentina/Mendoza",
    enable_utc=True,
    task_ignore_result=True,      # no usamos backend de resultados
    broker_connection_retry_on_startup=True,
    beat_schedule={
        # Cada 15 min: recordatorios de 24 h y de 2 h (doble recordatorio).
        "recordatorios": {
            "task": "app.tasks.emails.encolar_recordatorios",
            "schedule": 900.0,
        },
        # Diarios a las 12:00 UTC (~09:00 Argentina): cumpleaños e inactivos.
        "cumpleanios": {
            "task": "app.tasks.emails.enviar_cumpleanios",
            "schedule": crontab(hour=12, minute=0),
        },
        "inactivos": {
            "task": "app.tasks.emails.enviar_inactivos",
            "schedule": crontab(hour=12, minute=30),
        },
    },
)
