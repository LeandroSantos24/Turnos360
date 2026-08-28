"""Validación de la firma de los webhooks de Mercado Pago.

Qué protegía el código antes de esto
------------------------------------
Bastante, en realidad, y conviene decirlo para no exagerar el hallazgo: la
notificación NO se cree nada de lo que le mandan. Toma el `payment_id`, va a
la API de Mercado Pago **con el token del propio negocio** y pregunta si ese
pago existe y está aprobado. Un pago inventado no existe en esa cuenta, así
que no se puede marcar una seña como pagada desde afuera.

Lo que sí quedaba abierto
-------------------------
Cualquiera podía disparar el circuito: un POST sin credenciales hacía que el
backend saliera a consultar la API de MP. Un amplificador gratis. El fix
anterior lo acotó exigiendo que el id fuera numérico y corto, pero el pedido
sigue entrando y sigue costando una llamada saliente.

La firma cierra eso: sin `x-signature` válida, no se toca la red.

POR QUÉ TIENE TRES MODOS Y NO UN BOOLEANO
------------------------------------------
Esto es plata y no se puede probar en local: la firma la genera Mercado Pago
con un secreto que solo existe en su panel. Si el manifiesto que armamos acá
no coincide con el que arma MP —por un separador, por un campo de más—, en
`enforce` **dejan de acreditarse las señas reales** y el negocio se entera
cuando un cliente reclama.

Por eso:

    off      se comporta exactamente como antes. Es el default.
    log      valida y escribe en el log si cierra o no, PERO NO BLOQUEA.
    enforce  rechaza lo que no venga firmado.

El camino es: poner `log`, mirar los logs con tráfico real un par de días,
confirmar que todas las notificaciones legítimas dan `firma_ok=true`, y recién
ahí pasar a `enforce`. Un escalón por vez, mirando.

El manifiesto
-------------
MP arma este texto y lo firma con HMAC-SHA256:

    id:<data.id>;request-id:<x-request-id>;ts:<ts>;

y manda el resultado en el encabezado:

    x-signature: ts=1704908010,v1=618c85345248dd820d...

Los segmentos que no vienen se omiten. Y si el id trae letras, va en
minúsculas.
"""

import hashlib
import hmac
import logging

from fastapi import Request

from app.core.config import settings

log = logging.getLogger("turnos360.mp")


def _partes_firma(cabecera: str | None) -> dict:
    """`ts=123,v1=abc` -> {'ts': '123', 'v1': 'abc'}"""
    salida = {}
    for trozo in (cabecera or "").split(","):
        if "=" not in trozo:
            continue
        clave, _, valor = trozo.partition("=")
        salida[clave.strip()] = valor.strip()
    return salida


def manifiesto(data_id: str | None, request_id: str | None, ts: str | None) -> str:
    partes = []
    if data_id:
        # MP pide el id en minúsculas cuando trae letras. Los de pago son
        # numéricos, así que esto casi nunca cambia nada — pero cuando cambia,
        # cambia todo: la firma no cierra y no hay forma de darse cuenta.
        partes.append(f"id:{data_id.lower()};")
    if request_id:
        partes.append(f"request-id:{request_id};")
    if ts:
        partes.append(f"ts:{ts};")
    return "".join(partes)


def verificar(
    request: Request, data_id: str | None, secreto: str | None = None
) -> bool | None:
    """True/False si se pudo verificar; None si no hay con qué (no configurado).

    None NO es un fallo: es "no tengo el secreto, no puedo opinar". El
    llamador decide qué hacer con eso según el modo.

    `secreto` existe porque hay DOS webhooks de Mercado Pago con DOS cuentas
    distintas: el de las señas (cuenta de cada negocio, MP_WEBHOOK_SECRET) y el
    de las cuotas del SaaS (cuenta de Turnos360, MP_SAAS_WEBHOOK_SECRET). El
    algoritmo es el mismo; lo que cambia es con qué clave se firma.
    """
    secreto = (secreto if secreto is not None else settings.mp_webhook_secret or "").strip()
    if not secreto:
        return None

    firma = _partes_firma(request.headers.get("x-signature"))
    v1, ts = firma.get("v1"), firma.get("ts")
    if not v1 or not ts:
        return False

    texto = manifiesto(data_id, request.headers.get("x-request-id"), ts)
    esperada = hmac.new(secreto.encode(), texto.encode(), hashlib.sha256).hexdigest()
    # compare_digest y no ==: comparar firmas con == filtra el secreto por
    # el tiempo que tarda en devolver False.
    return hmac.compare_digest(esperada, v1)


def acepta(
    request: Request, data_id: str | None, secreto: str | None = None
) -> bool:
    """¿Se sigue procesando esta notificación?

    Devuelve False solo en `enforce` y solo con firma inválida. En `log` deja
    pasar todo y escribe qué habría pasado, que es el punto de ese modo.
    """
    modo = (settings.mp_firma_modo or "off").strip().lower()
    if modo == "off":
        return True

    resultado = verificar(request, data_id, secreto)

    if resultado is None:
        log.warning(
            "webhook de MP sin secreto configurado",
            extra={"modo": modo, "data_id": data_id},
        )
        # Sin secreto no se puede bloquear nada, ni siquiera en enforce: eso
        # sería cortar todas las señas por un .env incompleto.
        return True

    if resultado:
        log.info("webhook de MP con firma válida", extra={"data_id": data_id})
        return True

    log.warning(
        "webhook de MP con firma INVÁLIDA",
        extra={"modo": modo, "data_id": data_id, "bloqueado": modo == "enforce"},
    )
    return modo != "enforce"
