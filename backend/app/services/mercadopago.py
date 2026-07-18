"""Mercado Pago para señas de reserva (Checkout Pro).

Cada empresa conecta SU cuenta con SU access token, encriptado en reposo con
el mismo Fernet que las credenciales de WhatsApp (Regla 7). La comisión de MP
la absorbe el negocio: la plata va directo a su cuenta, Turnos360 no toca
un peso del pago.

Filosofía de errores: la reserva NUNCA se cae por Mercado Pago. Si la API
falla, devolvemos None y el turno queda creado con la seña pendiente — el
negocio la cobra en persona.
"""

import logging

import httpx

from app.core.config import settings
from app.core.crypto import desencriptar_credenciales, encriptar_credenciales
from app.models import Empresa, Turno

log = logging.getLogger(__name__)

MP_API = "https://api.mercadopago.com"


def guardar_token(empresa: Empresa, access_token: str) -> None:
    """Encripta y guarda el access token de la cuenta MP del negocio."""
    empresa.mp_credenciales = encriptar_credenciales({"access_token": access_token.strip()})


def token_de(empresa: Empresa) -> str | None:
    """Access token desencriptado, o None si el negocio no conectó MP."""
    if not empresa.mp_credenciales:
        return None
    try:
        return desencriptar_credenciales(empresa.mp_credenciales).get("access_token")
    except Exception:  # SECRET_KEY cambiada u otro problema de Fernet
        log.exception("No se pudieron desencriptar credenciales MP (empresa %s)", empresa.id)
        return None


def crear_preferencia(empresa: Empresa, turno: Turno, titulo: str) -> str | None:
    """Crea la preferencia de pago de la seña y devuelve el init_point (URL).

    None si el negocio no tiene MP conectado, no hay monto, o la API falló.
    """
    token = token_de(empresa)
    if not token or not turno.sena_monto:
        return None

    vidriera = f"{settings.public_base_url}/{empresa.slug}"
    payload = {
        "items": [
            {
                "title": titulo[:120],
                "quantity": 1,
                "currency_id": "ARS",
                "unit_price": float(turno.sena_monto),
            }
        ],
        "external_reference": str(turno.id),
        "back_urls": {
            "success": f"{vidriera}?pago=aprobado",
            "pending": f"{vidriera}?pago=pendiente",
            "failure": f"{vidriera}?pago=rechazado",
        },
        "auto_return": "approved",
        "notification_url": f"{settings.api_base_url}/publico/mp/webhook/{empresa.slug}",
        "statement_descriptor": empresa.nombre[:22],
    }
    try:
        r = httpx.post(
            f"{MP_API}/checkout/preferences",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("init_point")
    except Exception:
        log.exception("MP: falló crear preferencia (empresa %s, turno %s)", empresa.id, turno.id)
        return None


def consultar_pago(token: str, payment_id: str) -> dict | None:
    """Trae el pago desde la API de MP (la consulta con el token del negocio
    es a la vez la validación de autenticidad de la notificación)."""
    try:
        r = httpx.get(
            f"{MP_API}/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        log.exception("MP: falló consultar pago %s", payment_id)
        return None
