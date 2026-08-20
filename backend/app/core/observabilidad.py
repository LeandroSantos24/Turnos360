"""Middleware, manejador de errores y chequeos de salud.

Vive aparte de main.py para que ese archivo siga siendo un índice legible de
routers y no se convierta en un cajón de sastre.
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import (
    empresa_id_var,
    nuevo_request_id,
    request_id_var,
    usuario_id_var,
)
from app.db.session import SessionLocal

log = logging.getLogger("turnos360")

# Rutas que no vale la pena loguear: las sondas del contenedor pegan cada
# pocos segundos y taparían todo lo demás.
_RUTAS_SILENCIOSAS = {"/health", "/ready"}


class ContextoYAcceso:
    """Middleware ASGI: un id por pedido y una línea de log por pedido.

    Es ASGI puro y NO BaseHTTPMiddleware, por una razón concreta:
    BaseHTTPMiddleware corre la aplicación en una tarea aparte, así que los
    ContextVar que setean las dependencias (empresa_id, usuario_id) NO vuelven
    a verse acá. Con ASGI puro corre todo en la misma tarea y el contexto
    fluye, que es justo lo que hace útil al log: sin eso, una línea de error
    dice "falló un pedido" en vez de "falló un pedido de la empresa 42".
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        cabeceras = dict(scope.get("headers") or [])
        crudo = cabeceras.get(b"x-request-id", b"").decode("latin1", "ignore")
        # Se acepta el id del proxy si viene (permite seguir una traza de punta
        # a punta), pero acotado: un header gigante no puede terminar en el log.
        rid = crudo.strip()[:64] or nuevo_request_id()

        # request_id va por ContextVar: se setea acá, en la tarea principal,
        # así que anyio lo copia hacia los hilos del threadpool y TODA línea
        # que emita este pedido lo lleva, aunque la emita un service.
        #
        # A propósito no se hace reset(): cada pedido corre con su propia copia
        # del contexto (no hay fuga entre pedidos) y dejarlo puesto permite que
        # el manejador global de excepciones —que corre por FUERA de este
        # middleware— siga viendo el id para devolvérselo al cliente.
        request_id_var.set(rid)
        empresa_id_var.set("-")
        usuario_id_var.set("-")

        # empresa y usuario NO pueden ir por ContextVar: los setea una
        # dependencia SINCRÓNICA, y FastAPI corre esas en el threadpool.
        # anyio copia el contexto hacia el hilo pero no lo trae de vuelta, así
        # que el set se perdería. scope["state"] es un dict compartido y sí
        # cruza hilos.
        estado = scope.setdefault("state", {})

        arranque = time.perf_counter()
        codigo = 500  # si la app explota, nunca llega http.response.start

        async def enviar(mensaje):
            nonlocal codigo
            if mensaje["type"] == "http.response.start":
                codigo = mensaje["status"]
                lista = list(mensaje.get("headers") or [])
                lista.append((b"x-request-id", rid.encode("latin1")))
                mensaje = {**mensaje, "headers": lista}
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        finally:
            ruta = scope.get("path", "")
            if ruta not in _RUTAS_SILENCIOSAS:
                ms = round((time.perf_counter() - arranque) * 1000, 1)
                # 5xx en ERROR, 4xx en WARNING, el resto INFO: así un
                # `grep ERROR` alcanza para saber si algo anda mal.
                nivel = (
                    logging.ERROR
                    if codigo >= 500
                    else logging.WARNING
                    if codigo >= 400
                    else logging.INFO
                )
                metodo = scope.get("method", "?")
                log.log(
                    nivel,
                    "%s %s -> %s (%sms)",
                    metodo,
                    ruta,
                    codigo,
                    ms,
                    extra={
                        "metodo": metodo,
                        "ruta": ruta,
                        "estado": codigo,
                        "ms": ms,
                        "ip": cabeceras.get(b"x-real-ip", b"").decode("latin1", "ignore")
                        or (scope.get("client") or ("-",))[0],
                        # También van en `extra` y no solo vía el filtro del
                        # handler: así el registro los lleva encima aunque lo
                        # capture otro handler (un test, un agregador que se
                        # enganche aparte).
                        "empresa_id": str(estado.get("empresa_id", "-")),
                        "usuario_id": str(estado.get("usuario_id", "-")),
                    },
                )


def registrar_observabilidad(app: FastAPI) -> None:
    """Engancha el middleware de pedidos y el manejador global de errores."""

    app.add_middleware(ContextoYAcceso)

    @app.exception_handler(Exception)
    async def error_no_controlado(request: Request, exc: Exception):
        """Cualquier excepción que nadie atrapó.

        Antes: 500 genérico y un traceback sin contexto en la salida de error,
        imposible de asociar con nada. Ahora queda logueado con el id del
        pedido, la empresa y el usuario, y el cliente recibe ese mismo id para
        poder pasártelo.

        NUNCA se filtra el detalle del error al cliente: puede contener
        nombres de tablas, consultas o valores de otra empresa.
        """
        rid = request_id_var.get()
        estado = request.scope.get("state") or {}
        log.exception(
            "Error no controlado en %s %s",
            request.method,
            request.url.path,
            extra={
                "metodo": request.method,
                "ruta": request.url.path,
                "empresa_id": str(estado.get("empresa_id", "-")),
                "usuario_id": str(estado.get("usuario_id", "-")),
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detalle": (
                    "Se produjo un error inesperado. Si el problema sigue, "
                    f"pasanos este código: {rid}"
                ),
                "request_id": rid,
            },
            headers={"X-Request-Id": rid},
        )


# ══════════════════════════════════════════════════════════════════════════
# Salud
# ══════════════════════════════════════════════════════════════════════════

def _base_responde() -> tuple[bool, str]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as e:  # noqa: BLE001 — acá queremos el motivo, sea cual sea
        return False, type(e).__name__


def _redis_responde() -> tuple[bool, str]:
    try:
        import redis

        cliente = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        cliente.ping()
        return True, "ok"
    except Exception as e:  # noqa: BLE001
        return False, type(e).__name__


def estado_vivo() -> dict:
    """¿El proceso está vivo? No mira dependencias.

    Es lo que tiene que mirar un orquestador para decidir si REINICIAR el
    contenedor. Si acá mirara la base, un Postgres caído provocaría un bucle
    de reinicios del backend, que no arregla nada y encima borra los logs.
    """
    return {"status": "ok"}


def estado_listo() -> tuple[dict, int]:
    """¿Puede atender pedidos de verdad? Mira base y Redis.

    Esto es lo que tiene que mirar el healthcheck del compose y un balanceador
    para decidir si MANDARLE TRÁFICO. Antes /health devolvía {"status":"ok"}
    incondicionalmente: el backend se reportaba sano con Postgres caído y con
    Redis caído.
    """
    base_ok, base_detalle = _base_responde()
    redis_ok, redis_detalle = _redis_responde()
    cuerpo = {
        "status": "ok" if (base_ok and redis_ok) else "degradado",
        "base": base_detalle,
        "redis": redis_detalle,
    }
    codigo = 200 if (base_ok and redis_ok) else 503
    return cuerpo, codigo


# ══════════════════════════════════════════════════════════════════════════
# Sentry (opcional)
# ══════════════════════════════════════════════════════════════════════════

def iniciar_sentry() -> bool:
    """Arranca Sentry si hay DSN configurado y el paquete instalado.

    Es opcional a propósito: sin SENTRY_DSN el sistema funciona igual, y sin
    el paquete instalado tampoco rompe. Poner el DSN es lo que convierte
    "me enteré por un cliente" en "me llegó una alerta".
    """
    dsn = (settings.sentry_dsn or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        log.warning(
            "SENTRY_DSN está configurado pero falta el paquete. "
            "Instalalo con: pip install 'sentry-sdk[fastapi]'"
        )
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.env,
        # Sin performance tracing: es lo que más cuota consume y hoy no lo
        # necesitás. Los errores sí, todos.
        traces_sample_rate=0.0,
        # No mandar cuerpos ni headers: pueden traer datos de salud o
        # credenciales de Mercado Pago.
        send_default_pii=False,
    )
    log.info("Sentry activo (entorno %s)", settings.env)
    return True
