"""Rate limiting (slowapi). Limita intentos por IP en endpoints sensibles."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Identifica al cliente por su IP. Detrás de un reverse proxy (Nginx en producción),
# hay que configurar el proxy para pasar la IP real en X-Forwarded-For.
limiter = Limiter(key_func=get_remote_address)