"""Schemas del panel de super-administración."""

from pydantic import BaseModel, Field

from app.models.enums import RolUsuario


class AdminLogin(BaseModel):
    email: str
    clave: str


class AdminToken(BaseModel):
    access_token: str
    nombre: str


class RubroOut(BaseModel):
    id: int
    codigo: str
    nombre: str

    model_config = {"from_attributes": True}


class DuenoCrear(BaseModel):
    nombre: str = Field(min_length=2)
    email: str
    clave: str = Field(min_length=6)


class EmpresaCrear(BaseModel):
    nombre: str = Field(min_length=2)
    slug: str = Field(min_length=2)
    rubro_id: int
    dueno: DuenoCrear


class EmpresaAdminOut(BaseModel):
    id: int
    nombre: str
    slug: str
    rubro_nombre: str | None = None
    activa: bool
    cantidad_usuarios: int = 0

    model_config = {"from_attributes": True}


class EmpresaPausar(BaseModel):
    activa: bool


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=2)
    email: str
    clave: str = Field(min_length=6)
    rol: RolUsuario


class UsuarioAdminOut(BaseModel):
    id: int
    nombre: str
    email: str
    rol: RolUsuario
    activo: bool

    model_config = {"from_attributes": True}


class UsuarioActualizar(BaseModel):
    activo: bool