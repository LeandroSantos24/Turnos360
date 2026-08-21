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


class TokenInvalido(ValueError):
    """El token no sirve. El mensaje está escrito para mostrárselo al dueño."""


def validar_token(access_token: str) -> dict:
    """Le pregunta a Mercado Pago de quién es este token. Levanta si no sirve.

    POR QUÉ ESTO ES EL FIX MÁS IMPORTANTE DE MERCADO PAGO
    -----------------------------------------------------
    Antes el token se guardaba sin mirarlo. El panel decía «Cuenta de Mercado
    Pago conectada ✓» y el dueño se iba tranquilo. Si había pegado la Public
    Key en vez del Access Token —están una al lado de la otra en la misma
    pantalla de MP, es EL error clásico— o el token de prueba en vez del de
    producción, no pasaba nada visible.

    Se enteraba días después: un cliente real reserva, no le aparece el botón
    de pagar, el turno queda «pendiente», y nadie sabe por qué.
    `crear_preferencia` devuelve None y el sistema sigue como si el negocio
    nunca hubiera conectado Mercado Pago.

    Una llamada de 200 ms al guardar convierte eso en un error inmediato y con
    nombre y apellido.
    """
    token = (access_token or "").strip()
    if not token:
        raise TokenInvalido("Pegá el Access Token de tu cuenta de Mercado Pago.")

    if token.startswith("TEST-"):
        raise TokenInvalido(
            "Ese es el token de PRUEBA (empieza con TEST-). Con ese los pagos no "
            "son reales. Copiá el de Credenciales de PRODUCCIÓN, que empieza "
            "con APP_USR-."
        )

    try:
        r = httpx.get(
            f"{MP_API}/users/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except Exception as e:
        raise TokenInvalido(
            "No pude comunicarme con Mercado Pago para verificar el token. "
            "Probá de nuevo en un minuto."
        ) from e

    if r.status_code in (401, 403):
        raise TokenInvalido(
            "Mercado Pago rechazó ese token. Fijate que estés copiando el "
            "«Access Token» y no la «Public Key»: están juntas en la misma "
            "pantalla y se confunden todo el tiempo."
        )
    if r.status_code >= 400:
        raise TokenInvalido(
            f"Mercado Pago respondió {r.status_code} al verificar el token."
        )

    datos = r.json()
    return {
        "id": datos.get("id"),
        "nombre": datos.get("nickname") or datos.get("first_name") or "",
        "email": datos.get("email") or "",
        "pais": datos.get("site_id") or "",
    }


def guardar_token(empresa: Empresa, access_token: str, cuenta: dict | None = None) -> None:
    """Encripta y guarda el access token de la cuenta MP del negocio.

    `cuenta` se guarda al lado del token, adentro del mismo blob cifrado (así
    que no hace falta migración), para poder mostrarle al dueño A QUÉ CUENTA
    quedó conectado. «Conectado ✓» a secas no dice nada: podría ser la cuenta
    personal del sobrino que ayudó a configurarlo.
    """
    blob = {"access_token": access_token.strip()}
    if cuenta:
        blob["cuenta"] = cuenta
    empresa.mp_credenciales = encriptar_credenciales(blob)


def cuenta_de(empresa: Empresa) -> dict | None:
    """Los datos de la cuenta MP conectada, o None."""
    if not empresa.mp_credenciales:
        return None
    try:
        return desencriptar_credenciales(empresa.mp_credenciales).get("cuenta")
    except Exception:
        return None


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
