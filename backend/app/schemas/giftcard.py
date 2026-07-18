"""Schemas de gift cards."""

import datetime as dt

from pydantic import BaseModel, Field, field_validator


class GiftCardCrear(BaseModel):
    """Alta de una gift card. El código lo genera el backend."""

    monto: float = Field(gt=0)
    beneficiario: str | None = Field(default=None, max_length=120)
    de_parte_de: str | None = Field(default=None, max_length=120)
    mensaje: str | None = Field(default=None, max_length=300)
    concepto: str | None = Field(default=None, max_length=120)
    vence: dt.date | None = None

    @field_validator("vence")
    @classmethod
    def _no_nacer_vencida(cls, v: dt.date | None) -> dt.date | None:
        if v is not None and v < dt.date.today():
            raise ValueError("La fecha de vencimiento ya pasó — poné una futura o dejala vacía.")
        return v


class GiftCardOut(BaseModel):
    id: int
    empresa_id: int
    codigo: str
    beneficiario: str | None
    de_parte_de: str | None
    mensaje: str | None
    monto: float
    concepto: str | None
    estado: str
    vence: dt.date | None
    canjeada_en: dt.datetime | None
    canjeada_por: str | None
    creada_en: dt.datetime

    model_config = {"from_attributes": True}


class GiftCardVerificar(BaseModel):
    """Consulta por código (para el escáner): dice si es válida y sus datos."""

    codigo: str = Field(min_length=1, max_length=40)


class GiftCardVerificacion(BaseModel):
    """Resultado de verificar/consultar una gift card sin canjearla."""

    valida: bool
    motivo: str | None = None  # "vencida" / "ya canjeada" / "no existe"
    gift_card: GiftCardOut | None = None
