"""Creación y validación de tokens JWT (E2).

Dos tipos de token:
- access (corto): viaja en cada request en el header Authorization.
- refresh (largo): solo sirve para pedir un access nuevo.

Ambos llevan en su interior (claims):
- sub: el usuario_id (estándar JWT, "subject")
- empresa_id: el tenant — lo que get_current_empresa() leerá (Regla 1)
- rol: para el control de permisos
- type: "access" o "refresh", para no aceptar uno donde va el otro
- exp: vencimiento (lo completa PyJWT)
"""

from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


# Ámbitos de token. Un token de empresa NO sirve en el panel de super-admin
# y viceversa: sin esto, ambos tokens llevan solo `sub` y `get_current_usuario`
# aceptaba el del super-admin como si fuera el usuario con ese mismo id.
SCOPE_EMPRESA = "empresa"
SCOPE_SUPERADMIN = "superadmin"


def _crear_token(
    *,
    usuario_id: int,
    empresa_id: int,
    rol: str,
    tipo: str,
    expira: timedelta,
    token_version: int = 0,
) -> str:
    """Arma y firma un token con los claims del proyecto."""
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),       # 'subject': el JWT estándar lo quiere como string
        "scope": SCOPE_EMPRESA,       # panel del negocio (NO el de super-admin)
        "empresa_id": empresa_id,
        "rol": rol,
        "type": tipo,                 # 'access' | 'refresh'
        "tv": token_version,          # 'token version': permite revocar sesiones
        "iat": ahora,                 # 'issued at': cuándo se emitió
        "exp": ahora + expira,        # 'expiration': cuándo vence
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algoritmo)


def crear_access_token(
    usuario_id: int, empresa_id: int, rol: str, token_version: int = 0
) -> str:
    """Token corto que viaja en cada request."""
    return _crear_token(
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        rol=rol,
        tipo="access",
        expira=timedelta(minutes=settings.access_token_minutos),
        token_version=token_version,
    )


def crear_refresh_token(
    usuario_id: int, empresa_id: int, rol: str, token_version: int = 0
) -> str:
    """Token largo que solo sirve para renovar el access."""
    return _crear_token(
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        rol=rol,
        tipo="refresh",
        expira=timedelta(days=settings.refresh_token_dias),
        token_version=token_version,
    )


def crear_token_superadmin(superadmin_id: int) -> str:
    """Token para el panel de super-administración (no pertenece a ninguna empresa)."""
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(superadmin_id),
        "scope": SCOPE_SUPERADMIN,
        "type": "access",
        "iat": ahora,
        "exp": ahora + timedelta(hours=12),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algoritmo)


def decodificar_token(
    token: str, tipo_esperado: str = "access", scope_esperado: str | None = None
) -> dict:
    """Valida la firma y el vencimiento de un token y devuelve sus claims.

    Lanza InvalidTokenError si: la firma es falsa, el token venció, el tipo no
    es el esperado (p. ej. mandar un refresh donde va un access), o el ámbito
    no coincide (mandar un token de super-admin donde va uno de empresa).

    scope_esperado es obligatorio de facto en las dependencias: se pasa siempre.
    Queda opcional solo para no romper llamadas internas que ya validan aparte.
    """
    payload = jwt.decode(
        token, settings.secret_key, algorithms=[settings.jwt_algoritmo]
    )
    if payload.get("type") != tipo_esperado:
        raise InvalidTokenError(
            f"Se esperaba un token '{tipo_esperado}' y llegó '{payload.get('type')}'"
        )
    if scope_esperado is not None and payload.get("scope") != scope_esperado:
        # Los tokens viejos (sin claim 'scope') caen acá y quedan rechazados:
        # es lo correcto, hay que volver a loguearse una vez tras el deploy.
        raise InvalidTokenError(
            f"Se esperaba un token de ámbito '{scope_esperado}' y llegó "
            f"'{payload.get('scope')}'"
        )
    return payload