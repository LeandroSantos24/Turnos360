"""Endpoints de autenticación: login y refresh (E2)."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select

from app.api.deps import DB, UsuarioActual
from app.core.seguridad import (
    crear_access_token,
    crear_refresh_token,
    decodificar_token,
)
from app.core.crypto import verificar_clave
from app.models import Usuario
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UsuarioMe

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(datos: LoginRequest, db: DB) -> TokenResponse:
    """Valida email + clave y devuelve un par de tokens (access + refresh).

    El login NO filtra por empresa: el email es único dentro de cada empresa,
    pero el usuario aún no nos dijo quién es. Buscamos por email y, si la clave
    coincide, el empresa_id queda fijado en los tokens que emitimos.
    """
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email o contraseña incorrectos",
    )

    # 1. Buscar el usuario por email
    usuario = db.scalar(select(Usuario).where(Usuario.email == datos.email))

    # 2. Verificar que exista, esté activo y la clave coincida con el hash.
    #    Verificamos la clave SIEMPRE (aunque el usuario no exista) para no
    #    revelar por el tiempo de respuesta si un email está registrado o no.
    hash_guardado = usuario.hash_clave if usuario else "pbkdf2$1$00$00"
    clave_ok = verificar_clave(datos.clave, hash_guardado)

    if usuario is None or not usuario.activo or not clave_ok:
        raise credenciales_invalidas

    # 3. Emitir los tokens con el empresa_id y rol fijados adentro
    return TokenResponse(
        access_token=crear_access_token(usuario.id, usuario.empresa_id, usuario.rol.value),
        refresh_token=crear_refresh_token(usuario.id, usuario.empresa_id, usuario.rol.value),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(datos: RefreshRequest, db: DB) -> TokenResponse:
    """Recibe un refresh token válido y emite un par nuevo de tokens."""
    token_invalido = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token inválido o vencido",
    )

    # 1. Validar el refresh token (firma, vencimiento, tipo 'refresh')
    try:
        payload = decodificar_token(datos.refresh_token, tipo_esperado="refresh")
        usuario_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise token_invalido

    # 2. El usuario debe seguir existiendo y activo
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise token_invalido

    # 3. Emitir tokens frescos
    return TokenResponse(
        access_token=crear_access_token(usuario.id, usuario.empresa_id, usuario.rol.value),
        refresh_token=crear_refresh_token(usuario.id, usuario.empresa_id, usuario.rol.value),
    )

@router.get("/me", response_model=UsuarioMe)
def me(usuario: UsuarioActual) -> Usuario:
    """Devuelve los datos del usuario autenticado.

    Ruta protegida: sin un access token válido en el header, FastAPI corta
    con 401 antes de entrar acá (lo hace el guardián get_current_usuario).
    """
    return usuario