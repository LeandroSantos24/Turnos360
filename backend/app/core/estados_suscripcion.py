"""Los estados de la suscripción de una empresa, en UN solo lugar.

El estado NO se guarda: se DERIVA de los datos (vencimiento, prueba, pausa,
cancelación, avisos y pagos en curso). Guardarlo sería tener dos verdades —la
columna y las fechas— que tarde o temprano dicen cosas distintas. Lo que se
centraliza acá es el VOCABULARIO y las REGLAS: qué estados existen, qué
significa cada uno para el negocio y qué operaciones se permiten desde cada
uno. `services/suscripcion.py::estado_suscripcion` es la única función que
decide en qué estado está una empresa.

Los nombres en inglés son los de la especificación; los valores en castellano
son los que ya viajaban por la API (`activa`, `prorroga`, `vencida`…) y se
mantienen para no romper el contrato con el frontend.

Ciclo de vida:

    TRIAL ──fin de la prueba──► EXPIRED ──pago──► ACTIVE
    ACTIVE ──vence──► GRACE_PERIOD ──pago──► ACTIVE
                          └──sin pago (3 días)──► PAST_DUE ──pago──► ACTIVE
    ACTIVE ──cancelar──► CANCEL_PENDING ──vence──► CANCELED
                              └──reactivar──► ACTIVE
    cualquiera ──pausa del super-admin──► SUSPENDED ──reanudar──► (el que corresponda)

Superpuestos al ciclo, cuando el negocio debe plata:
    PAYMENT_REVIEW  = avisó una transferencia y la estamos verificando
    PAYMENT_PENDING = inició un pago en Mercado Pago que todavía no se acreditó
"""

import enum

from fastapi import HTTPException, status


class EstadoSuscripcion(str, enum.Enum):
    TRIAL = "prueba"
    ACTIVE = "activa"
    PAYMENT_PENDING = "pendiente_pago"
    PAYMENT_REVIEW = "en_revision"
    GRACE_PERIOD = "prorroga"
    PAST_DUE = "vencida"
    CANCEL_PENDING = "cancelacion_programada"
    CANCELED = "cancelada"
    SUSPENDED = "suspendida"
    EXPIRED = "prueba_vencida"
    # Cuenta bonificada / sin ciclo de cobro definido (alta manual sin fecha).
    NO_DUE_DATE = "sin_vencimiento"


E = EstadoSuscripcion

# Etiqueta para el cliente y tono semántico para pintar el badge.
ETIQUETAS: dict[EstadoSuscripcion, tuple[str, str]] = {
    E.TRIAL: ("En prueba", "info"),
    E.ACTIVE: ("Activa · al día", "ok"),
    E.PAYMENT_PENDING: ("Pago pendiente de acreditación", "aviso"),
    E.PAYMENT_REVIEW: ("Pago en revisión", "aviso"),
    E.GRACE_PERIOD: ("Vencida · en período de gracia", "aviso"),
    E.PAST_DUE: ("Vencida", "error"),
    E.CANCEL_PENDING: ("Cancelación programada", "aviso"),
    E.CANCELED: ("Cancelada", "neutro"),
    E.SUSPENDED: ("Suspendida", "error"),
    E.EXPIRED: ("Prueba terminada", "error"),
    E.NO_DUE_DATE: ("Sin vencimiento", "neutro"),
}

# Estados en los que el negocio DEBE una cuota (para cobranza y alertas).
CON_DEUDA = frozenset({E.GRACE_PERIOD, E.PAST_DUE, E.EXPIRED, E.PAYMENT_REVIEW, E.PAYMENT_PENDING})

# Estados que cuentan como suscripción viva para el MRR.
VIVOS = frozenset({E.ACTIVE, E.GRACE_PERIOD, E.PAYMENT_REVIEW, E.PAYMENT_PENDING, E.CANCEL_PENDING})


# Operaciones explícitas y desde qué estados se permiten. Lo que no está en el
# conjunto es una transición imposible y se rechaza con 409.
_TODOS = frozenset(EstadoSuscripcion)
TRANSICIONES: dict[str, frozenset[EstadoSuscripcion]] = {
    # El negocio cancela: desde cualquier estado vivo o con deuda.
    "cancelar": _TODOS - {E.CANCEL_PENDING, E.CANCELED, E.SUSPENDED},
    # Deshacer la cancelación (antes o después de que se haga efectiva).
    "reactivar": frozenset({E.CANCEL_PENDING, E.CANCELED}),
    # Subir de plan = pagar. Pagar también reactiva una cancelación.
    "subir_plan": _TODOS - {E.SUSPENDED},
    # Bajar se programa sobre un ciclo vivo. Con una cancelación pendiente
    # primero hay que reactivar: bajar de plan algo que se va a cancelar no
    # tiene sentido y deja un estado ambiguo.
    "bajar_plan": _TODOS - {E.SUSPENDED, E.CANCEL_PENDING, E.CANCELED},
    "pagar": _TODOS - {E.SUSPENDED},
    "avisar_pago": _TODOS - {E.SUSPENDED},
    "suspender": _TODOS - {E.SUSPENDED},
    "reanudar": frozenset({E.SUSPENDED}),
}

_MENSAJES_RECHAZO = {
    "cancelar": "Tu suscripción ya está cancelada o con una cancelación programada.",
    "reactivar": "Tu suscripción no está cancelada: no hay nada que reactivar.",
    "subir_plan": "La cuenta está suspendida. Escribinos para reactivarla.",
    "bajar_plan": (
        "No se puede programar una baja de plan sobre una suscripción cancelada "
        "o con una cancelación pendiente. Reactivala primero."
    ),
    "pagar": "La cuenta está suspendida. Escribinos para reactivarla.",
    "avisar_pago": "La cuenta está suspendida. Escribinos para reactivarla.",
    "suspender": "La cuenta ya está suspendida.",
    "reanudar": "La cuenta no está suspendida.",
}


def permitido(estado: EstadoSuscripcion | str, operacion: str) -> bool:
    return EstadoSuscripcion(estado) in TRANSICIONES[operacion]


def exigir(estado: EstadoSuscripcion | str, operacion: str) -> None:
    """409 si la operación no se puede hacer desde este estado."""
    if not permitido(estado, operacion):
        raise HTTPException(status.HTTP_409_CONFLICT, _MENSAJES_RECHAZO[operacion])
