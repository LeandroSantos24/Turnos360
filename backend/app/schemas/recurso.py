"""Schemas de Recurso: lo reservable (persona/box/equipo) y sus datos (E2).

Regla 2: un Recurso generaliza a barbero, médico, box de lavado o equipo.
Las especialidades se manejan como una lista de ids (puente N:M con especialidad).
"""

from pydantic import BaseModel, Field

from app.models.enums import RolUsuario, TipoRecurso


class RecursoBase(BaseModel):
    """Campos comunes a crear y editar."""

    nombre: str = Field(min_length=1, max_length=120)
    tipo: TipoRecurso = TipoRecurso.PERSONA
    color: str | None = Field(default=None, max_length=9)  # para la agenda visual
    foto_url: str | None = Field(default=None, max_length=300)  # foto para la landing
    sucursal_id: int | None = None
    usuario_id: int | None = None  # si la persona tiene login
    especialidad_ids: list[int] = Field(default_factory=list)


class RecursoCrear(RecursoBase):
    """Lo que llega al crear un recurso."""


class RecursoEditar(BaseModel):
    """Lo que llega al editar: todos los campos opcionales."""

    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: TipoRecurso | None = None
    color: str | None = Field(default=None, max_length=9)
    foto_url: str | None = Field(default=None, max_length=300)
    sucursal_id: int | None = None
    usuario_id: int | None = None
    especialidad_ids: list[int] | None = None
    activo: bool | None = None


class EspecialidadOut(BaseModel):
    """Especialidad embebida en la respuesta de un recurso."""

    id: int
    nombre: str

    model_config = {"from_attributes": True}


class RecursoOut(BaseModel):
    """Lo que la API devuelve. Incluye las especialidades resueltas (no solo ids)."""

    id: int
    empresa_id: int
    nombre: str
    tipo: TipoRecurso
    color: str | None
    foto_url: str | None
    sucursal_id: int | None
    usuario_id: int | None
    activo: bool
    especialidades: list[EspecialidadOut]

    model_config = {"from_attributes": True}


class RecursosPagina(BaseModel):
    """Lista de recursos con total."""

    total: int
    items: list[RecursoOut]


class UsuarioVinculable(BaseModel):
    """Un usuario de la empresa que el dueño puede vincular a un recurso.

    recurso_id/recurso_nombre indican si YA está vinculado a algún recurso
    (para que la UI lo muestre y respete el 1-a-1). None = está libre.
    """

    id: int
    nombre: str
    email: str
    rol: RolUsuario
    recurso_id: int | None = None
    recurso_nombre: str | None = None

    model_config = {"from_attributes": True}
