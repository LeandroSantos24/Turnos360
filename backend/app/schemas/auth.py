"""Schemas de autenticación: lo que entra y sale por los endpoints de login (E2)."""

from pydantic import BaseModel, Field, EmailStr


class LoginRequest(BaseModel):
    """Lo que el usuario envía para iniciar sesión."""

    email: EmailStr
    clave: str


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

    model_config = {"from_attributes": True}

class OlvidePasswordRequest(BaseModel):
    email: str = Field(max_length=200)


class RestablecerPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    clave_nueva: str = Field(min_length=8, max_length=100)


class CambiarPasswordRequest(BaseModel):
    clave_actual: str = Field(max_length=100)
    clave_nueva: str = Field(min_length=8, max_length=100)
