"""Schemas de la capa pública (landing): vidriera, huecos y reserva.

Todo esto lo consume la página pública del negocio (turnos360.com/<slug>),
sin login. Ver app/routers/publico.py.
"""

import datetime as dt

from pydantic import BaseModel, Field


class ServicioPublico(BaseModel):
    id: int
    nombre: str
    precio: float | None = None
    duracion_min: int


class RecursoPublico(BaseModel):
    id: int
    nombre: str
    foto_url: str | None = None


class VidrieraOut(BaseModel):
    """Datos para pintar la página del negocio."""

    nombre: str
    slug: str
    descripcion: str | None = None
    direccion: str | None = None
    telefono_publico: str | None = None
    email_publico: str | None = None
    logo_url: str | None = None
    color_marca: str | None = None
    horarios_atencion: dict | None = None
    redes: dict = {}
    galeria: list[str] = []
    servicios: list[ServicioPublico]
    recursos: list[RecursoPublico]


class HuecosDia(BaseModel):
    """Los horarios de inicio libres de un día."""

    fecha: dt.date
    horas: list[dt.datetime]


class ClientePublico(BaseModel):
    """Datos que carga el cliente al reservar. Teléfono obligatorio (D-13)."""

    nombre: str = Field(min_length=1, max_length=120)
    telefono: str = Field(min_length=5, max_length=40)
    email: str | None = Field(default=None, max_length=200)


class ReservaPublicaCrear(BaseModel):
    servicio_id: int
    recurso_id: int | None = None  # None = "sin preferencia" (cualquiera libre)
    inicio: dt.datetime
    cliente: ClientePublico


class ReservaPublicaOut(BaseModel):
    turno_id: int
    servicio: str
    recurso: str
    inicio: dt.datetime
    estado: str
    mensaje: str