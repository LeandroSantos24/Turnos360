"""Schemas de Cliente: qué entra y sale por los endpoints del CRM (E2).

Tres schemas de entrada/salida más uno paginado:
- ClienteCrear:  lo que se manda para crear (sin id, sin empresa_id).
- ClienteEditar: como Crear pero TODO opcional (para editar solo lo que cambia).
- ClienteOut:    lo que la API devuelve (con id, empresa_id, fechas).
- ClientesPagina: una página de resultados + el total (para listar).
"""

import datetime as dt

from pydantic import BaseModel, EmailStr, Field


class ClienteBase(BaseModel):
    """Campos comunes a crear y editar. Acá viven las validaciones."""

    nombre: str = Field(min_length=1, max_length=120)
    apellido: str | None = Field(default=None, max_length=120)
    dni: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    telefono: str | None = Field(default=None, max_length=40)
    fecha_nacimiento: dt.date | None = None
    canal_adquisicion: str | None = Field(default=None, max_length=60)
    campos_rubro: dict = Field(default_factory=dict)
    preferencias: dict = Field(default_factory=dict)
    etiquetas: list[str] = Field(default_factory=list)
    observaciones: str | None = None
    # Consentimiento para campañas promocionales (Ley 25.326).
    acepta_marketing: bool = False


class ClienteCrear(ClienteBase):
    """Lo que llega al crear un cliente. Hereda todo de ClienteBase."""


class ClienteEditar(BaseModel):
    """Lo que llega al editar: TODOS los campos son opcionales.

    Solo se actualiza lo que venga en el body; lo que no venga, queda igual.
    """

    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    apellido: str | None = Field(default=None, max_length=120)
    dni: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    telefono: str | None = Field(default=None, max_length=40)
    fecha_nacimiento: dt.date | None = None
    canal_adquisicion: str | None = Field(default=None, max_length=60)
    campos_rubro: dict | None = None
    preferencias: dict | None = None
    etiquetas: list[str] | None = None
    observaciones: str | None = None


class ClienteOut(ClienteBase):
    """Lo que la API devuelve: los campos del cliente + los que pone el sistema.

    email se relaja a str: la validación EmailStr es para la ENTRADA (crear /
    editar). Al LEER, un dato viejo mal guardado no puede tumbar el listado.
    """

    email: str | None = None
    id: int
    empresa_id: int
    activo: bool
    creado_en: dt.datetime

    model_config = {"from_attributes": True}


class ClientesPagina(BaseModel):
    """Una página de resultados al listar, con el total para la paginación."""

    total: int
    items: list[ClienteOut]