"""Encolar una tarea de Celery sin que un worker apagado la haga desaparecer.

EL PROBLEMA QUE RESUELVE
────────────────────────
`tarea.delay(...)` escribe el mensaje en Redis y vuelve enseguida. Devuelve OK
tanto si hay un worker esperando del otro lado como si no hay ninguno. En el
segundo caso el mensaje queda en la cola para siempre, la API le contesta al
usuario «Te lo mandamos a tu casilla, revisá el spam», y el email no sale nunca.

No es un caso raro: es el estado normal de cualquier máquina de desarrollo
donde se levantó el backend a mano sin `docker compose up worker`, y de
cualquier servidor donde el worker se cayó y nadie lo miró. El síntoma que se
ve es «el mail de verificación no llega», que manda a buscar el problema al
lugar equivocado —SMTP, Gmail, la carpeta de spam— cuando en realidad la tarea
nunca se ejecutó.

CÓMO SE RESUELVE
────────────────
Antes de encolar se le pregunta a la cola si hay alguien escuchando
(`control.ping`, que responden solo los workers vivos). Si contesta alguien, se
encola como siempre —con sus reintentos, su backoff y su acks_late, que es lo
que queremos en producción—. Si no contesta nadie, se ejecuta la función acá
mismo, en línea, y el usuario recibe su email igual.

POR QUÉ NO SE EJECUTA SIEMPRE EN LÍNEA
──────────────────────────────────────
Porque un envío por SMTP puede tardar segundos y bloquear el request. En
producción la cola es lo correcto. Esto es una red de contención para el caso
en que la cola no exista, no un reemplazo de la cola.

EL RESULTADO SE DEVUELVE, NO SE ESCONDE
───────────────────────────────────────
`encolar()` devuelve cómo terminó, y quien llama decide qué contarle al usuario.
Es la mitad importante del arreglo: si el envío en línea también falla, la API
tiene que poder decir «no pudimos mandarlo» en vez de mentir.
"""

import logging
from enum import Enum

log = logging.getLogger("turnos360.cola")

# Cuánto se espera a que un worker levante la mano. Corto a propósito: esto
# corre dentro de un request HTTP y en producción SIEMPRE hay worker, así que
# el camino normal es un ida y vuelta local contra Redis.
TIMEOUT_PING = 0.5

# Se cachea la respuesta del ping: preguntarle a Redis en cada request por algo
# que no cambia de un segundo al otro es gasto puro. Se recuerda por poco
# tiempo para que levantar el worker se note enseguida.
SEGUNDOS_CACHE = 15.0

_ultimo_ping: tuple[float, bool] | None = None


class Resultado(str, Enum):
    ENCOLADA = "encolada"    # hay worker; la tarea salió a la cola
    EN_LINEA = "en_linea"    # no hay worker; se ejecutó acá y terminó bien
    FALLO = "fallo"          # no hay worker y la ejecución en línea reventó


def hay_worker() -> bool:
    """¿Hay algún worker de Celery escuchando la cola ahora mismo?

    Cualquier error —Redis caído, credenciales mal, la librería que cambia—
    cuenta como «no hay»: el camino sin worker ejecuta en línea, que es el
    lado seguro para equivocarse. Decir que sí cuando no lo hay pierde el
    mensaje; decir que no cuando lo hay solo lo manda por el camino lento.
    """
    global _ultimo_ping
    import time

    ahora = time.monotonic()
    if _ultimo_ping is not None and (ahora - _ultimo_ping[0]) < SEGUNDOS_CACHE:
        return _ultimo_ping[1]

    try:
        from app.celery_app import celery_app

        respuestas = celery_app.control.ping(timeout=TIMEOUT_PING)
        vivo = bool(respuestas)
    except Exception:
        log.debug("No se pudo consultar la cola; se asume que no hay worker", exc_info=True)
        vivo = False

    _ultimo_ping = (ahora, vivo)
    return vivo


def encolar(tarea, *args, **kwargs) -> Resultado:
    """Manda la tarea por la cola, o la ejecuta acá si no hay quien la tome.

    `tarea` es la función decorada con @celery_app.task. Se la llama con
    `tarea.run(...)` en el camino en línea —no `tarea(...)`— para saltear el
    envoltorio de Celery y ejecutar el cuerpo de la función tal cual.
    """
    nombre = getattr(tarea, "name", getattr(tarea, "__name__", "tarea"))

    if hay_worker():
        try:
            tarea.delay(*args, **kwargs)
            return Resultado.ENCOLADA
        except Exception:
            # El worker contestó el ping hace un momento pero encolar falló
            # (Redis se cayó en el medio). Se intenta en línea antes de darlo
            # por perdido.
            log.warning("Falló encolar %s; se intenta en línea", nombre, exc_info=True)

    try:
        tarea.run(*args, **kwargs)
        log.info("%s se ejecutó en línea (no hay worker de Celery escuchando)", nombre)
        return Resultado.EN_LINEA
    except Exception:
        log.exception("%s falló al ejecutarse en línea", nombre)
        return Resultado.FALLO
