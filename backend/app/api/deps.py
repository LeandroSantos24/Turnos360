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

from app.core.seguridad import SCOPE_EMPRESA, SCOPE_SUPERADMIN, decodificar_token
from app.db.session import get_db
from app.models import Empresa, SuperAdmin, Usuario
from app.models.enums import RolUsuario

# Lee el header "Authorization: Bearer <token>" de cada request.
_bearer = HTTPBearer(auto_error=True)


def verificar_empresa_activa(empresa: Empresa | None) -> None:
    """Corta el acceso si la empresa fue pausada por el super-admin (E5).

    Se usa en el login (frenar sesiones nuevas) y en get_current_usuario
    (frenar tokens YA emitidos antes de la pausa). El estado se lee de la
    base en cada request a propósito: querés que pausar/reactivar tenga
    efecto al instante, no recién cuando venza el token.

    Devuelve 403 (no 401): las credenciales son válidas; lo deshabilitado
    es el servicio del tenant.
    """
    if empresa is None or not empresa.activa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El servicio de tu empresa está pausado. Contactá al administrador.",
        )


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

    # 1. Abrir y validar el token (firma, vencimiento, tipo 'access' y ÁMBITO).
    #    El scope es lo que impide que el token del panel de super-admin —que
    #    lleva el id del super-admin en 'sub'— sea aceptado acá como si fuera
    #    el Usuario que casualmente tiene ese mismo id numérico.
    try:
        payload = decodificar_token(
            credenciales.credentials,
            tipo_esperado="access",
            scope_esperado=SCOPE_EMPRESA,
        )
        usuario_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise no_autorizado

    # 2. El usuario debe existir y estar activo
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise no_autorizado

    # 2.5. La versión del token debe seguir siendo la vigente.
    #      Cambiar o restablecer la contraseña incrementa usuario.token_version,
    #      así que todas las sesiones emitidas antes (incluido el refresh de 7
    #      días guardado en otro dispositivo) dejan de valer al instante.
    if int(payload.get("tv", 0)) != int(usuario.token_version or 0):
        raise no_autorizado

    # 3. La empresa del usuario no debe estar pausada.
    #    Este es el candado que corta los tokens YA emitidos: aunque el token
    #    sea válido y no haya vencido, si pausaste la empresa deja de entrar.
    #    Todas las rutas de negocio cuelgan de get_current_usuario (directo,
    #    vía get_current_empresa o vía requiere_rol), así que con ponerlo
    #    acá queda cubierto todo el panel de una sola vez.
    empresa = db.get(Empresa, usuario.empresa_id)
    verificar_empresa_activa(empresa)

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


# --- Atajos de rol, listos para usar como guarda de ruta -------------------
#   @router.post(..., dependencies=[Depends(gate_dueno)])
#
# gate_dueno    -> SOLO el dueño. Catálogo (servicios, recursos), config del
#                  negocio y finanzas sensibles (métodos de pago, estadísticas).
# gate_gestion  -> dueño + recepción (+ admin, que queda "dormido" pero si algún
#                  día se usa hereda permisos de recepción). Es la operación del
#                  día: crear/mover turnos, cobrar, caja. Excluye al PROFESIONAL.
#                  (Cambiar estado YA NO usa este gate: el profesional puede
#                  operar SUS turnos; ver contexto_profesional + turnos.py.)
gate_dueno = requiere_rol(RolUsuario.DUENO)
gate_gestion = requiere_rol(RolUsuario.DUENO, RolUsuario.ADMIN, RolUsuario.RECEPCION)


def contexto_profesional(usuario: Usuario) -> tuple[bool, int | None]:
    """Resuelve la restricción "solo lo mío" de un profesional.

    Devuelve (es_profesional, recurso_id):
      - (False, None): NO es profesional (dueño/recepción/admin) → sin restricción.
      - (True, <id>):  profesional CON recurso asignado → restringido a ese recurso.
      - (True, None):  profesional SIN recurso asignado todavía → no debe ver ni
                       gestionar ningún turno (la ruta decide: agenda vacía / 403).

    No es una dependencia de FastAPI a propósito: es una función pura que las
    rutas llaman con el usuario ya resuelto, para tener la regla en un solo lugar.
    Usa usuario.recurso (el relationship 1-a-1 del Bloque 1); solo dispara esa
    query para los profesionales (los demás salen por el early return).
    """
    if usuario.rol != RolUsuario.PROFESIONAL:
        return (False, None)
    recurso = usuario.recurso
    return (True, recurso.id if recurso else None)


# Atajos para escribir las rutas más corto (se usan desde E2 en adelante)
def get_current_superadmin(
    credenciales: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> SuperAdmin:
    """Valida el token del panel de super-administración."""
    no_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de administrador inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decodificar_token(
            credenciales.credentials,
            tipo_esperado="access",
            scope_esperado=SCOPE_SUPERADMIN,
        )
        sa_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise no_autorizado

    sa = db.get(SuperAdmin, sa_id)
    if sa is None or not sa.activo:
        raise no_autorizado
    return sa


UsuarioActual = Annotated[Usuario, Depends(get_current_usuario)]
SuperAdminActual = Annotated[SuperAdmin, Depends(get_current_superadmin)]
EmpresaActual = Annotated[int, Depends(get_current_empresa)]
DB = Annotated[Session, Depends(get_db)]
