"""Dependencias de FastAPI: el guardián del multi-tenancy (E2).

get_current_empresa() es el corazón de la Regla 1: extrae el empresa_id
del token firmado y se lo entrega a la ruta. Ninguna ruta de negocio
debe obtener el empresa_id de otra forma (jamás de un query param o del body,
que el usuario podría manipular).
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.seguridad import decodificar_token
from app.db.session import get_db
from app.models import Usuario
from app.models.enums import RolUsuario

# Lee el header "Authorization: Bearer <token>" de cada request.
_bearer = HTTPBearer(auto_error=True)


def get_current_usuario(
    credenciales: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> Usuario:
    """Valida el access token y devuelve el Usuario activo correspondiente."""
    no_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Abrir y validar el token (firma, vencimiento, tipo 'access')
    try:
        payload = decodificar_token(credenciales.credentials, tipo_esperado="access")
        usuario_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise no_autorizado

    # 2. El usuario debe existir y estar activo
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise no_autorizado

    return usuario


def get_current_empresa(
    usuario: Annotated[Usuario, Depends(get_current_usuario)],
) -> int:
    """Devuelve el empresa_id del usuario autenticado.

    ESTE es el valor que toda ruta de negocio usa para filtrar sus queries.
    Viene del usuario (que vino del token firmado): el cliente no puede
    elegir a qué empresa pertenece.
    """
    return usuario.empresa_id


def requiere_rol(*roles_permitidos: RolUsuario):
    """Fábrica de dependencias que exige uno de los roles dados.

    Uso futuro en una ruta:
        usuario = Depends(requiere_rol(RolUsuario.DUENO, RolUsuario.ADMIN))
    """

    def verificador(
        usuario: Annotated[Usuario, Depends(get_current_usuario)],
    ) -> Usuario:
        if usuario.rol not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés permisos para esta acción",
            )
        return usuario

    return verificador


# Atajos para escribir las rutas más corto (se usan desde E2 en adelante)
UsuarioActual = Annotated[Usuario, Depends(get_current_usuario)]
EmpresaActual = Annotated[int, Depends(get_current_empresa)]
DB = Annotated[Session, Depends(get_db)]