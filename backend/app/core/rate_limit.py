"""Rate limiting (slowapi). Limita intentos por IP en endpoints sensibles.

Los contadores viven en Redis (el mismo del stack): así los límites son
coherentes aunque uvicorn corra con varios workers — en memoria, cada proceso
llevaría su propia cuenta y "10/min" serían 10 POR worker. Si Redis no está
disponible (p. ej. pytest local sin docker), cae solo a memoria y sigue
funcionando.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Identifica al cliente por su IP. Detrás de un reverse proxy (Nginx en
# producción), hay que pasar la IP real en X-Forwarded-For y correr uvicorn
# con --proxy-headers; si no, todos los visitantes comparten la IP del proxy
# y el límite se vuelve global (va configurado en el compose de producción).
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    in_memory_fallback_enabled=True,
)
