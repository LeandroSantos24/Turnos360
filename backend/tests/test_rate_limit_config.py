"""Configuración del rate limiting.

El COMPORTAMIENTO (429 al undécimo intento, contadores por IP real en Redis)
está verificado a mano en el sandbox y forma parte del runbook de staging: no
se testea acá porque con TestClient todos los requests comparten la IP
"testclient" y los contadores en Redis persistirían entre corridas, haciendo
la suite frágil y dependiente del orden.

Lo que SÍ se vigila acá es la CONFIGURACIÓN: que los endpoints sensibles
sigan decorados. Si alguien borra un @limiter.limit(...) en un refactor,
este test falla. Es la clase de regresión silenciosa que nadie nota hasta
que un atacante prueba 10.000 claves contra el login.
"""

import app.main  # noqa: F401  (importa los routers => registra los decoradores)
from app.core.rate_limit import limiter


def test_endpoints_sensibles_siguen_limitados():
    marcados = set(limiter._Limiter__marked_for_limiting.keys())

    esperados = {
        "app.routers.auth.login",
        "app.routers.auth.refresh",
        "app.routers.auth.olvide_password",
        "app.routers.auth.restablecer_password",
        "app.routers.admin.login",
        "app.routers.publico.reservar",
        "app.routers.publico.validar_cupon_publico",
    }
    faltan = esperados - marcados
    assert not faltan, f"Endpoints que perdieron su rate limit: {sorted(faltan)}"


def test_limiter_usa_redis_como_storage():
    """El storage compartido es lo que hace coherentes los límites con varios
    workers de uvicorn (P1-5 de la auditoría). Si vuelve a memoria, '10/min'
    se convierte en 10 POR worker."""
    assert type(limiter.limiter.storage).__name__ == "RedisStorage"
    assert limiter._in_memory_fallback_enabled  # y aguanta un Redis caído
