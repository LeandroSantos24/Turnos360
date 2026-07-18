"""Endpoints de autenticación: login y refresh (E2)."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select

from app.api.deps import DB, UsuarioActual, verificar_empresa_activa
from app.core.seguridad import (
    crear_access_token,
    crear_refresh_token,
    decodificar_token,
)
from app.core.crypto import verificar_clave
from app.core.rate_limit import limiter
import datetime as dt
import hashlib
import logging
import secrets

from app.core.crypto import hash_clave, verificar_clave as _verificar_clave
from app.models import Empresa, Usuario
from app.schemas.auth import CambiarPasswordRequest, OlvidePasswordRequest, RestablecerPasswordRequest, LoginRequest, RefreshRequest, TokenResponse, UsuarioMe

router = APIRouter(prefix="/auth", tags=["auth"])

log = logging.getLogger(__name__)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, datos: LoginRequest, db: DB) -> TokenResponse:
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

    # 3. La empresa no debe estar pausada por el super-admin.
    #    Va DESPUÉS de validar la clave a propósito: solo un usuario legítimo
    #    (que ya probó email + contraseña) se entera de que el servicio está
    #    pausado. A un atacante le seguimos respondiendo "credenciales inválidas"
    #    y no le revelamos nada sobre la empresa.
    empresa = db.get(Empresa, usuario.empresa_id)
    verificar_empresa_activa(empresa)

    # 4. Emitir los tokens con el empresa_id y rol fijados adentro
    return TokenResponse(
        access_token=crear_access_token(usuario.id, usuario.empresa_id, usuario.rol.value),
        refresh_token=crear_refresh_token(usuario.id, usuario.empresa_id, usuario.rol.value),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh(request: Request, datos: RefreshRequest, db: DB) -> TokenResponse:
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

    # 3. La empresa no debe estar pausada: si no, no minteamos tokens nuevos.
    #    Sin esto, un usuario de una empresa pausada podría seguir refrescando
    #    su sesión para siempre (aunque cada access token resultante igual
    #    moriría en get_current_usuario, mejor cortarlo de raíz acá).
    empresa = db.get(Empresa, usuario.empresa_id)
    verificar_empresa_activa(empresa)

    # 4. Emitir tokens frescos
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

# ============================================================
# Recuperación y cambio de contraseña
# ============================================================

@router.post("/olvide-password")
@limiter.limit("3/minute")
def olvide_password(request: Request, datos: OlvidePasswordRequest, db: DB) -> dict:
    """Pide el email y manda un link de restablecimiento (si la cuenta existe).

    SIEMPRE responde lo mismo: no revelamos si un email está registrado o no.
    El token viaja por email; acá solo guardamos su hash, con 60 min de vida.
    """
    usuario = db.scalar(
        select(Usuario).where(Usuario.email == datos.email, Usuario.activo.is_(True))
    )
    if usuario is not None:
        token = secrets.token_urlsafe(32)
        usuario.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
        usuario.reset_token_expira = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
            minutes=60
        )
        db.commit()
        try:
            from app.tasks.emails import enviar_reset_password

            enviar_reset_password.delay(usuario.id, token)
        except Exception:
            # La respuesta al usuario no cambia (no revelamos nada), pero esto
            # TIENE que quedar en los logs: si el broker está caído, el email
            # nunca se encoló y alguien se tiene que enterar.
            log.exception(
                "No se pudo encolar el email de restablecimiento (usuario %s)",
                usuario.id,
            )
    return {"detalle": "Si el email está registrado, te enviamos un link para restablecer la contraseña."}


@router.post("/restablecer-password")
@limiter.limit("5/minute")
def restablecer_password(
    request: Request, datos: RestablecerPasswordRequest, db: DB
) -> dict:
    """Cambia la clave usando el token del email. Un solo uso, expira en 60 min."""
    token_hash = hashlib.sha256(datos.token.encode()).hexdigest()
    usuario = db.scalar(
        select(Usuario).where(
            Usuario.reset_token_hash == token_hash,
            Usuario.reset_token_expira > dt.datetime.now(dt.timezone.utc),
            Usuario.activo.is_(True),
        )
    )
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El link no es válido o ya venció. Pedí uno nuevo desde el login.",
        )
    usuario.hash_clave = hash_clave(datos.clave_nueva)
    usuario.reset_token_hash = None
    usuario.reset_token_expira = None
    db.commit()
    return {"detalle": "Contraseña actualizada. Ya podés entrar con la nueva."}


@router.post("/cambiar-password")
def cambiar_password(
    datos: CambiarPasswordRequest, usuario: UsuarioActual, db: DB
) -> dict:
    """Cambio de clave estando logueado: pide la actual y setea la nueva."""
    if not _verificar_clave(datos.clave_actual, usuario.hash_clave):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta",
        )
    usuario.hash_clave = hash_clave(datos.clave_nueva)
    usuario.reset_token_hash = None
    usuario.reset_token_expira = None
    db.commit()
    return {"detalle": "Contraseña actualizada"}
