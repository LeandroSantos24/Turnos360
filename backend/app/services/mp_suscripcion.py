"""Cobro de la CUOTA DEL SAAS por Mercado Pago (la cuenta de Turnos360).

NO CONFUNDIR CON app/services/mercadopago.py
────────────────────────────────────────────
Son dos Mercado Pago distintos y es la confusión más cara que se puede tener
acá adentro:

  · `mercadopago.py`  → el MP de CADA NEGOCIO. Cobra la seña de un turno a SU
    cliente final. El token vive cifrado en `empresa.mp_credenciales`, hay uno
    por empresa, y el webhook entra por /publico/mp/webhook/{slug}.

  · este archivo      → el MP de TURNOS360. Cobra la cuota mensual a cada
    negocio. El token es UNO SOLO y sale del entorno
    (`MP_SAAS_ACCESS_TOKEN`). El webhook entra por
    /publico/mp/webhook-suscripcion, sin slug, porque la cuenta es la misma
    para todos.

Meterle el token equivocado a una preferencia significa cobrarle a la cuenta
que no es. Por eso el token nunca se pasa por parámetro: se lee acá.

APAGADO POR DEFECTO
───────────────────
Sin `MP_SAAS_ACCESS_TOKEN`, `esta_activo()` da False, el botón no aparece en
"Mi suscripción" y el webhook contesta 503. Es a propósito: los avisos de
Mercado Pago necesitan una URL pública con HTTPS, y en un staging por VPN no
llegan nunca. Un cobro que entra y que nadie acredita es peor que no ofrecer
el botón.
"""

import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Empresa, PagoSuscripcion

log = logging.getLogger("turnos360.mp_suscripcion")

MP_API = "https://api.mercadopago.com"
TIMEOUT = 15

# external_reference: "sus:<empresa_id>". El prefijo evita confundir esta
# notificación con la de una seña, cuyo external_reference es un id de turno
# pelado. Si algún día las dos cuentas fueran la misma, el prefijo es lo único
# que separa "me pagaron una cuota" de "le pagaron una seña a un negocio".
_REF = re.compile(r"^sus:(\d+)$")


def esta_activo() -> bool:
    return bool(settings.mp_saas_access_token)


def referencia_de(empresa_id: int) -> str:
    return f"sus:{empresa_id}"


def empresa_de_referencia(ref: str | None) -> int | None:
    m = _REF.match((ref or "").strip())
    return int(m.group(1)) if m else None


def precio_de(empresa: Empresa) -> float:
    """Lo que paga ESTA empresa: su precio pactado, o el de lista si no tiene."""
    if empresa.precio_mensual is not None:
        return float(empresa.precio_mensual)
    return float(settings.precio_vigente)


def crear_preferencia(empresa: Empresa) -> str | None:
    """Preferencia de Checkout Pro para la cuota de esta empresa.

    Devuelve el init_point (la URL a la que mandar al dueño), o None si el
    cobro por MP está apagado o la API falló.
    """
    if not esta_activo():
        return None

    monto = precio_de(empresa)
    if monto <= 0:
        # Una cuenta bonificada no tiene nada que pagar.
        return None

    panel = f"{settings.public_base_url}/suscripcion"
    payload = {
        "items": [
            {
                "title": f"Turnos360 · cuota mensual ({empresa.nombre})"[:120],
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": monto,
            }
        ],
        "external_reference": referencia_de(empresa.id),
        "back_urls": {
            "success": f"{panel}?pago=aprobado",
            "pending": f"{panel}?pago=pendiente",
            "failure": f"{panel}?pago=rechazado",
        },
        "auto_return": "approved",
        "notification_url": f"{settings.api_base_url}/publico/mp/webhook-suscripcion",
        "statement_descriptor": "TURNOS360",
    }
    try:
        r = httpx.post(
            f"{MP_API}/checkout/preferences",
            json=payload,
            headers={"Authorization": f"Bearer {settings.mp_saas_access_token}"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("init_point")
    except Exception:
        log.exception("MP SaaS: falló crear la preferencia (empresa %s)", empresa.id)
        return None


def consultar_pago(payment_id: str) -> dict | None:
    """Trae el pago desde la API con el token de Turnos360.

    Esta consulta ES la validación de autenticidad: un id inventado no existe
    en la cuenta y devuelve 404. La firma del webhook solo evita el tráfico
    saliente de notificaciones que ni siquiera vienen de Mercado Pago.
    """
    if not esta_activo():
        return None
    try:
        r = httpx.get(
            f"{MP_API}/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {settings.mp_saas_access_token}"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        log.exception("MP SaaS: falló consultar el pago %s", payment_id)
        return None


def ya_acreditado(db: Session, payment_id: str) -> bool:
    """¿Esta notificación ya se procesó? Mercado Pago reintenta varias veces."""
    return (
        db.scalar(
            select(PagoSuscripcion.id).where(
                PagoSuscripcion.mp_payment_id == str(payment_id)
            )
        )
        is not None
    )


def acreditar(db: Session, payment_id: str) -> PagoSuscripcion | None:
    """Procesa una notificación de pago de cuota. Nunca levanta.

    El orden importa: primero se corta por idempotencia (sin salir a la red),
    después se verifica contra la API, y recién ahí se toca la base.
    """
    from app.services import cobranza

    payment_id = str(payment_id)
    if ya_acreditado(db, payment_id):
        return None

    datos = consultar_pago(payment_id)
    if not datos or datos.get("status") != "approved":
        return None

    empresa_id = empresa_de_referencia(datos.get("external_reference"))
    if empresa_id is None:
        log.warning(
            "MP SaaS: pago %s sin external_reference de suscripción (%r)",
            payment_id,
            datos.get("external_reference"),
        )
        return None

    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        log.warning("MP SaaS: pago %s apunta a una empresa que no existe", payment_id)
        return None

    # El monto que se registra es el que MP confirmó, no el que esperábamos:
    # si el dueño pagó de menos, la cuota tiene que reflejar lo que entró.
    monto = float(datos.get("transaction_amount") or 0)

    pago = cobranza.registrar_pago(
        db,
        empresa,
        monto=monto,
        metodo="mercadopago",
        notas=f"Acreditado por Mercado Pago (pago {payment_id})",
        registrado_por="mercadopago",
        renovar=True,
    )
    pago.mp_payment_id = payment_id
    db.commit()
    log.info(
        "MP SaaS: cuota acreditada",
        extra={"empresa_id": empresa.id, "payment_id": payment_id, "monto": monto},
    )
    return pago
