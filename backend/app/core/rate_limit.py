"""Rate limiting (slowapi). Limita intentos por IP en endpoints sensibles.

Los contadores viven en Redis (el mismo del stack): así los límites son
coherentes aunque uvicorn corra con varios workers — en memoria, cada proceso
llevaría su propia cuenta y "10/min" serían 10 POR worker. Si Redis no está
disponible (p. ej. pytest local sin docker), cae solo a memoria y sigue
funcionando.
"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def ip_del_cliente(request: Request) -> str:
    """Clave del rate limit: la IP real del visitante.

    Se prefiere X-Real-IP porque Nginx lo SOBREESCRIBE con $remote_addr en
    cada request (`proxy_set_header X-Real-IP $remote_addr`), así que el
    cliente no lo puede elegir. X-Forwarded-For, en cambio, se ACUMULA: lo
    que manda el visitante queda primero en la cadena.

    Sin proxy adelante (desarrollo) el header no existe y se cae a la IP de
    la conexión, que es la correcta en ese caso.
    """
    real = (request.headers.get("x-real-ip") or "").strip()
    if real:
        return real
    return get_remote_address(request)

# Identifica al cliente por su IP. Detrás de un reverse proxy (Nginx en
# producción), hay que pasar la IP real en X-Forwarded-For y correr uvicorn
# con --proxy-headers; si no, todos los visitantes comparten la IP del proxy
# y el límite se vuelve global (va configurado en el compose de producción).
limiter = Limiter(
    key_func=ip_del_cliente,
    storage_uri=settings.redis_url,
    in_memory_fallback_enabled=True,
)
