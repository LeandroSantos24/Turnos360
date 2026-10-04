"""Latido de las tareas programadas.

Beat la encola cada 5 minutos y el worker la ejecuta: si la hora que deja en
Redis se atrasa, /estado responde 503 y el monitor externo avisa que el
worker, beat o la cola dejaron de andar (ver core/observabilidad.py).
"""

import time

import redis

from app.celery_app import celery_app
from app.core.config import settings
from app.core.observabilidad import LATIDO_CLAVE


@celery_app.task(name="app.tasks.latido.latido")
def latido() -> None:
    cliente = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
    # Expira solo: si todo se detiene, la clave desaparece en vez de quedar
    # mintiendo con una hora vieja para siempre.
    cliente.set(LATIDO_CLAVE, str(time.time()), ex=3600)
