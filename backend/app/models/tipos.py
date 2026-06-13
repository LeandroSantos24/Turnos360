"""Helpers de tipos para los modelos."""

import enum

from sqlalchemy import Enum as SAEnum


def enum_pg(enum_cls: type[enum.Enum], nombre: str) -> SAEnum:
    """Enum nativo de PostgreSQL usando los .value (minúsculas) del Enum de Python."""
    return SAEnum(
        enum_cls,
        name=nombre,
        values_callable=lambda e: [m.value for m in e],
    )