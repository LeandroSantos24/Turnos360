"""Schemas de autenticación: lo que entra y sale por los endpoints de login (E2)."""

from pydantic import BaseModel, Field, EmailStr


class LoginRequest(BaseModel):
    """Lo que el usuario envía para iniciar sesión."""

    email: EmailStr
    # Con tope: sin él se puede mandar una "contraseña" de varios MB y hacer
    # trabajar al servidor de gordo por cada intento.
    clave: str = Field(min_length=1, max_length=100)


class RefreshRequest(BaseModel):
    """Lo que se envía para renovar el access token vencido."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Lo que la API devuelve tras un login o refresh exitoso."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """El contenido que viaja DENTRO del token (lo usaremos al validarlo)."""

    usuario_id: int
    empresa_id: int
    rol: str

class UsuarioMe(BaseModel):
    """Datos del usuario autenticado que la API puede devolver (sin hash_clave)."""

    id: int
    nombre: str
    email: EmailStr
    rol: str
    empresa_id: int
    # A qué local pertenece. El panel lo usa para abrir la agenda en el local
    # de quien entra en vez de mezclar los de todos.
    sucursal_id: int | None = None
    # Lo necesita el panel para mostrar el aviso de "confirmá tu email": sin
    # eso, la página pública del negocio no aparece y el dueño no tiene forma
    # de saber por qué.
    email_verificado: bool = True
    # Para «Mi cuenta»: a qué negocio y a qué local pertenece esta persona,
    # con nombre. Recepción y el profesional no pueden listar locales, así que
    # sin esto no tendrían forma de ver el suyo.
    empresa_nombre: str | None = None
    sucursal_nombre: str | None = None

    model_config = {"from_attributes": True}


class PerfilActualizar(BaseModel):
    """Lo único que una persona puede cambiar de su propio usuario.

    Va con lista cerrada a propósito: ni email (es el usuario para entrar y
    pide verificación), ni rol, ni local (los decide el dueño desde Equipo).
    """

    nombre: str = Field(min_length=2, max_length=120)


class CerrarSesionesRequest(BaseModel):
    clave_actual: str = Field(min_length=1, max_length=100)


class SesionRenovada(TokenResponse):
    """Respuesta de las acciones que cortan las demás sesiones: un par nuevo
    para ESTE dispositivo, así quien hizo el cambio no queda afuera."""

    detalle: str

class OlvidePasswordRequest(BaseModel):
    email: str = Field(max_length=200)


class RestablecerPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    clave_nueva: str = Field(min_length=8, max_length=100)


class CambiarPasswordRequest(BaseModel):
    clave_actual: str = Field(max_length=100)
    clave_nueva: str = Field(min_length=8, max_length=100)
