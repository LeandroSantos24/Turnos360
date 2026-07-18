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

# ============================================================
# Evolución (EntradaClinica): un control / consulta de seguimiento
# ============================================================


class EntradaBase(BaseModel):
    """Campos de un control. Todos opcionales salvo la fecha."""

    fecha: dt.date
    tipo: str = Field(default="control", max_length=40)  # primera_consulta/control/antropometria
    turno_id: int | None = None

    como_se_sintio: str | None = None
    noto_diferencia: str | None = None
    apetito: str | None = None
    entrenamiento: str | None = None
    descanso: str | None = None
    estres: str | None = None
    resumen_antropometria: str | None = None
    prescripcion: str | None = None
    proximo_turno: dt.date | None = None


class EntradaCrear(EntradaBase):
    """Alta de un control de seguimiento."""


class EntradaOut(EntradaBase):
    id: int
    empresa_id: int
    cliente_id: int
    creada_en: dt.datetime

    model_config = {"from_attributes": True}


# ============================================================
# Mediciones antropométricas: lo que se grafica en el tiempo
# ============================================================


class MedicionBase(BaseModel):
    """Una toma de mediciones. Se completa lo que se haya medido."""

    fecha: dt.date
    evaluador: str | None = Field(default=None, max_length=120)
    origen: str = Field(default="manual", max_length=40)  # manual / isakmetry
    entrada_id: int | None = None

    # Básicas
    peso_kg: float | None = None
    talla_cm: float | None = None
    imc: float | None = None  # si no viene, el service lo calcula (peso + talla)
    talla_sentado_cm: float | None = None
    envergadura_cm: float | None = None

    # Pliegues (mm)
    pl_triceps: float | None = None
    pl_subescapular: float | None = None
    pl_biceps: float | None = None
    pl_cresta_iliaca: float | None = None
    pl_supraespinal: float | None = None
    pl_abdominal: float | None = None
    pl_muslo: float | None = None
    pl_pierna: float | None = None
    sumatoria_pliegues: float | None = None  # si no viene, se suman los presentes

    # Perímetros (cm)
    per_cintura: float | None = None
    per_cadera: float | None = None
    per_brazo: float | None = None
    per_muslo: float | None = None
    per_pierna: float | None = None

    # Composición corporal
    masa_grasa_kg: float | None = None
    masa_grasa_pct: float | None = None
    masa_muscular_kg: float | None = None
    masa_osea_kg: float | None = None

    datos_isak: dict = Field(default_factory=dict)


class MedicionCrear(MedicionBase):
    """Alta de una medición."""


class MedicionOut(MedicionBase):
    id: int
    empresa_id: int
    cliente_id: int
    creada_en: dt.datetime

    model_config = {"from_attributes": True}


# ============================================================
# Adjuntos del paciente (PDFs ISAK, estudios, planes) — por URL
# ============================================================


class AdjuntoCrear(BaseModel):
    """Alta de un adjunto. Por ahora la 'ruta' es una URL (upload directo post-deploy)."""

    nombre_archivo: str = Field(min_length=1, max_length=255)
    ruta: str = Field(min_length=8, max_length=500)  # URL http(s)
    tipo: str | None = Field(default=None, max_length=40)  # pdf_isak/estudio/plan/otro
    entrada_clinica_id: int | None = None


class AdjuntoOut(AdjuntoCrear):
    id: int
    empresa_id: int
    cliente_id: int
    fecha: dt.datetime

    model_config = {"from_attributes": True}
