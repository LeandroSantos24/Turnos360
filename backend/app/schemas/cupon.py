"""Schemas de cupones de descuento."""

import datetime as dt
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CuponBase(BaseModel):
    codigo: str = Field(min_length=3, max_length=30)
    tipo: Literal["porcentaje", "monto"] = "porcentaje"
    valor: float = Field(gt=0)
    vence_el: dt.date | None = None
    max_usos: int | None = Field(default=None, ge=1)
    servicios_ids: list[int] = Field(default_factory=list)  # vacío = todos
    activo: bool = True

    @field_validator("codigo")
    @classmethod
    def _codigo_limpio(cls, v: str) -> str:
        """MAYÚSCULAS, sin espacios: 'verano 10' → 'VERANO10'."""
        v = re.sub(r"\s+", "", v.strip().upper())
        if not re.fullmatch(r"[A-Z0-9\-_]{3,30}", v):
            raise ValueError("Solo letras, números, guiones (3 a 30 caracteres)")
        return v

    @field_validator("valor")
    @classmethod
    def _valor_razonable(cls, v: float, info) -> float:
        if info.data.get("tipo") == "porcentaje" and v > 100:
            raise ValueError("Un porcentaje no puede superar 100")
        return v


class CuponCrear(CuponBase):
    pass


class CuponEditar(CuponBase):
    pass


class CuponOut(CuponBase):
    id: int
    usos: int

    model_config = {"from_attributes": True}


# ── Validación desde la reserva pública ─────────────────────────────────────

class CuponValidarIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=40)
    servicio_id: int


class CuponValidarOut(BaseModel):
    valido: bool
    mensaje: str
    descuento: float = 0.0      # en pesos, ya calculado sobre el servicio
    precio_final: float | None = None
