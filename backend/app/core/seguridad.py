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


def _crear_token(
    *, usuario_id: int, empresa_id: int, rol: str, tipo: str, expira: timedelta
) -> str:
    """Arma y firma un token con los claims del proyecto."""
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),       # 'subject': el JWT estándar lo quiere como string
        "empresa_id": empresa_id,
        "rol": rol,
        "type": tipo,                 # 'access' | 'refresh'
        "iat": ahora,                 # 'issued at': cuándo se emitió
        "exp": ahora + expira,        # 'expiration': cuándo vence
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algoritmo)


def crear_access_token(usuario_id: int, empresa_id: int, rol: str) -> str:
    """Token corto que viaja en cada request."""
    return _crear_token(
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        rol=rol,
        tipo="access",
        expira=timedelta(minutes=settings.access_token_minutos),
    )


def crear_refresh_token(usuario_id: int, empresa_id: int, rol: str) -> str:
    """Token largo que solo sirve para renovar el access."""
    return _crear_token(
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        rol=rol,
        tipo="refresh",
        expira=timedelta(days=settings.refresh_token_dias),
    )


def decodificar_token(token: str, tipo_esperado: str = "access") -> dict:
    """Valida la firma y el vencimiento de un token y devuelve sus claims.

    Lanza InvalidTokenError si: la firma es falsa, el token venció, o el
    tipo no es el esperado (p. ej. mandar un refresh donde va un access).
    """
    payload = jwt.decode(
        token, settings.secret_key, algorithms=[settings.jwt_algoritmo]
    )
    if payload.get("type") != tipo_esperado:
        raise InvalidTokenError(
            f"Se esperaba un token '{tipo_esperado}' y llegó '{payload.get('type')}'"
        )
    return payload