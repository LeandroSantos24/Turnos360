"""Encriptación de credenciales por empresa (Regla 7) y hash de claves.

Las credenciales de MP/WhatsApp/email se guardan como BYTEA encriptado con
Fernet. La clave Fernet sale de FERNET_KEY (propia, separada de la firma de
los JWT); en desarrollo, si FERNET_KEY está vacía, se deriva de SECRET_KEY
como siempre para no romper el entorno local. Las claves de usuario usan
PBKDF2-HMAC-SHA256 con salt aleatorio.
"""

import base64
import hashlib
import json
import secrets

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    # FERNET_KEY propia si está configurada; si no (dev), deriva de SECRET_KEY.
    # En producción, config.py exige FERNET_KEY, así que el fallback nunca corre.
    origen = settings.fernet_key.strip() or settings.secret_key
    key = hashlib.sha256(origen.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encriptar_credenciales(datos: dict) -> bytes:
    """dict → bytes encriptados (para empresa.wa_credenciales / email_credenciales)."""
    return _fernet().encrypt(json.dumps(datos).encode())


def desencriptar_credenciales(blob: bytes) -> dict:
    return json.loads(_fernet().decrypt(blob))


# --- hash de claves de usuario ---

_ITERACIONES = 390_000


def hash_clave(clave: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(salt), _ITERACIONES)
    return f"pbkdf2${_ITERACIONES}${salt}${dk.hex()}"


def verificar_clave(clave: str, almacenada: str) -> bool:
    try:
        _, iters, salt, esperado = almacenada.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", clave.encode(), bytes.fromhex(salt), int(iters))
        return secrets.compare_digest(dk.hex(), esperado)
    except (ValueError, AttributeError):
        return False
