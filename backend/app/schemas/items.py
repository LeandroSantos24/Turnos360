"""Schemas de los ítems adicionales de un turno (E10)."""

import datetime as dt

from pydantic import BaseModel, Field


class ItemCrear(BaseModel):
    """Lo que llega para agregar un ítem a un turno."""

    descripcion: str = Field(min_length=1, max_length=160)
    precio: float = Field(default=0, ge=0)
    cantidad: int = Field(default=1, ge=1)
    tipo: str = Field(default="servicio", max_length=40)  # servicio / producto


class ItemOut(BaseModel):
    """Un ítem como lo devuelve la API."""

    id: int
    turno_id: int
    descripcion: str
    precio: float
    cantidad: int
    tipo: str
    creado_en: dt.datetime

    model_config = {"from_attributes": True}