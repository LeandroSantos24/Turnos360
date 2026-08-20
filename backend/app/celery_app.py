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
    # La tarea se confirma DESPUÉS de ejecutarse, no antes. Sin esto, si
    # el worker moría a mitad (falta de memoria, un deploy, un `down`), la
    # tarea se daba por hecha y el email no salía nunca. Nadie se enteraba.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Un worker toma de a una: las tareas son envíos de email, no cálculo.
    # Con prefetch alto, un worker acapara la cola y el resto espera.
    worker_prefetch_multiplier=1,
    # Reintentos automáticos ante fallas transitorias (Gmail que rechaza
    # por rate limit, DNS que parpadea, Redis que se reinicia). Antes no
    # había ninguno: el primer error era definitivo.
    task_annotations={
        "*": {
            "autoretry_for": (Exception,),
            "retry_backoff": True,      # 1s, 2s, 4s, 8s...
            "retry_backoff_max": 600,
            "retry_jitter": True,       # evita que 300 emails reintenten juntos
            "max_retries": 3,
        }
    },
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
        # Cobranza del SaaS: avisos de vencimiento a los negocios. 13:00 UTC
        # (~10:00 Argentina), después de los otros para no amontonar envíos
        # en el límite diario de Gmail.
        "vencimientos": {
            "task": "app.tasks.emails.avisar_vencimientos",
            "schedule": crontab(hour=13, minute=0),
        },
    },
)
