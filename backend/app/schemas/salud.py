"""Schemas del pack salud / nutrición (E13).

Por ahora, la ficha clínica (anamnesis). Todos los campos son opcionales:
la ficha se completa de a poco, consulta a consulta, no de una sola vez.

- FichaGuardar: lo que llega para crear o actualizar (upsert). Sin id ni empresa.
- FichaOut:     lo que la API devuelve (con id, empresa_id, cliente_id, fechas).
"""

import datetime as dt

from pydantic import BaseModel, Field


class FichaBase(BaseModel):
    """Campos de la anamnesis. Todos opcionales (se llena progresivamente)."""

    # Motivo y contexto
    motivo_consulta: str | None = None
    objetivo: str | None = None
    ocupacion: str | None = Field(default=None, max_length=200)
    horario_trabajo: str | None = Field(default=None, max_length=200)
    fum: dt.date | None = None

    # Alimentación (estructuras tabulares → dict)
    horario_comidas: dict = Field(default_factory=dict)
    recordatorio_24h: dict = Field(default_factory=dict)
    frecuencia_consumo: dict = Field(default_factory=dict)

    # Salud general
    actividad_fisica: str | None = None
    enfermedades: str | None = None
    operaciones: str | None = None
    medicacion: str | None = None
    antecedentes_familiares: str | None = None
    consume_alcohol_drogas: str | None = Field(default=None, max_length=200)
    fuma: str | None = Field(default=None, max_length=120)
    sintomas_recurrentes: str | None = None
    evacuacion: str | None = Field(default=None, max_length=200)
    sueno: str | None = Field(default=None, max_length=200)

    # Preferencias alimentarias
    alimentos_no_consume: str | None = None
    alimentos_no_tolera: str | None = None
    alimentos_gustan: str | None = None
    nutri_anterior: str | None = None

    # Cobertura
    obra_social: str | None = Field(default=None, max_length=120)
    plan_obra_social: str | None = Field(default=None, max_length=120)
    nro_afiliado: str | None = Field(default=None, max_length=60)

    datos_extra: dict = Field(default_factory=dict)


class FichaGuardar(FichaBase):
    """Lo que llega para crear o actualizar la ficha (upsert 1:1 por paciente)."""


class FichaOut(FichaBase):
    """Lo que la API devuelve."""

    id: int
    empresa_id: int
    cliente_id: int
    creada_en: dt.datetime
    actualizada_en: dt.datetime

    model_config = {"from_attributes": True}