"""Logging de Turnos360.

Antes de esto el proyecto no tenía NADA: cero configuración de logging, cero
manejador global de excepciones, y uvicorn corriendo en producción con
`--no-access-log`. Un error no controlado devolvía un 500 genérico y el
traceback se iba a la salida de error sin empresa, sin usuario, sin ruta y sin
forma de correlacionarlo con el reclamo del cliente que llamó por teléfono.

Dos formatos:

- `dev`  → una línea legible por humanos, coloreada por nivel.
- `prod` → JSON, una línea por evento, para que cualquier agregador (o un
  simple `jq`) pueda filtrar sin pelear con expresiones regulares.

Y un identificador de pedido (`request_id`) que viaja en un ContextVar: se
genera en el middleware, se cuela solo en TODOS los logs que emita ese pedido
—aunque los emita un service tres capas más abajo— y vuelve al cliente en el
header `X-Request-Id`. Cuando alguien reporta "me tiró error a las 15:42",
ese id es la diferencia entre encontrar el problema y adivinar.
"""

from __future__ import annotations

import contextvars
import datetime as dt
import json
import logging
import logging.config
import uuid

# El id del pedido en curso. ContextVar y no threading.local a propósito:
# FastAPI mezcla corrutinas y threadpool, y un ContextVar sigue al pedido en
# los dos mundos.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)
empresa_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "empresa_id", default="-"
)
usuario_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "usuario_id", default="-"
)


def nuevo_request_id() -> str:
    """Id corto y legible. 12 caracteres alcanzan y entran en un mensaje."""
    return uuid.uuid4().hex[:12]


class ContextoFilter(logging.Filter):
    """Mete el id de pedido, empresa y usuario en cada registro."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Solo rellena lo que falte: si el que loguea ya pasó el dato por
        # `extra=` (como hace el middleware con la empresa, que le llega por
        # request.state y no por ContextVar), ese valor MANDA. Pisarlo dejaba
        # la línea de acceso con "-" aunque el pedido estuviera autenticado.
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        if not hasattr(record, "empresa_id"):
            record.empresa_id = empresa_id_var.get()
        if not hasattr(record, "usuario_id"):
            record.usuario_id = usuario_id_var.get()
        return True


class FormatoJSON(logging.Formatter):
    """Una línea de JSON por evento. Para producción."""

    def format(self, record: logging.LogRecord) -> str:
        datos = {
            "ts": dt.datetime.fromtimestamp(
                record.created, dt.timezone.utc
            ).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "empresa_id": getattr(record, "empresa_id", "-"),
            "usuario_id": getattr(record, "usuario_id", "-"),
        }
        # Campos sueltos que el código pasa con logger.info(..., extra={...}).
        for clave in ("metodo", "ruta", "estado", "ms", "ip"):
            valor = getattr(record, clave, None)
            if valor is not None:
                datos[clave] = valor
        if record.exc_info:
            datos["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False)


class FormatoHumano(logging.Formatter):
    """Una línea legible, con color por nivel. Para desarrollo."""

    COLORES = {
        "DEBUG": "\033[0;36m",
        "INFO": "\033[0;32m",
        "WARNING": "\033[0;33m",
        "ERROR": "\033[0;31m",
        "CRITICAL": "\033[1;31m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORES.get(record.levelname, "")
        hora = dt.datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        rid = getattr(record, "request_id", "-")
        marca = f" [{rid}]" if rid and rid != "-" else ""
        linea = (
            f"{hora} {color}{record.levelname:<7}{self.RESET}"
            f"{marca} {record.name}: {record.getMessage()}"
        )
        if record.exc_info:
            linea += "\n" + self.formatException(record.exc_info)
        return linea


def configurar_logging(*, nivel: str = "INFO", json_salida: bool = False) -> None:
    """Deja el logging listo. Se llama UNA vez, al importar app.main.

    Toca también los loggers de uvicorn para que sus líneas salgan con el
    mismo formato y el mismo request_id que las nuestras, en vez de tener dos
    estilos mezclados en la misma salida.
    """
    formatter = "json" if json_salida else "humano"

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"contexto": {"()": ContextoFilter}},
            "formatters": {
                "json": {"()": FormatoJSON},
                "humano": {"()": FormatoHumano},
            },
            "handlers": {
                "consola": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": formatter,
                    "filters": ["contexto"],
                }
            },
            "root": {"handlers": ["consola"], "level": nivel},
            "loggers": {
                # uvicorn.access lo apagamos: nuestro middleware ya escribe una
                # línea de acceso, con duración y empresa. Dos sería ruido.
                "uvicorn.access": {"handlers": [], "propagate": False},
                "uvicorn.error": {
                    "handlers": ["consola"],
                    "level": nivel,
                    "propagate": False,
                },
                "uvicorn": {
                    "handlers": ["consola"],
                    "level": nivel,
                    "propagate": False,
                },
                # SQLAlchemy en WARNING: en INFO escupe cada consulta y tapa
                # todo lo demás.
                "sqlalchemy.engine": {"level": "WARNING"},
            },
        }
    )
