"""Configuración de la empresa actual: arma el preset efectivo para el front."""

from sqlalchemy.orm import Session

from app.models import Empresa, Rubro


def obtener_config(db: Session, empresa_id: int) -> dict:
    """Devuelve los datos de la empresa + el preset de su rubro.

    El preset sale del rubro; si la empresa tiene config_pack con overrides,
    se aplican encima (la empresa puede pisar partes del preset de su rubro).
    """
    empresa = db.get(Empresa, empresa_id)
    rubro = db.get(Rubro, empresa.rubro_id) if empresa else None

    preset = dict(rubro.preset) if rubro and rubro.preset else {}
    overrides = empresa.config_pack if empresa and empresa.config_pack else {}
    if overrides:
        preset.update(overrides)

    return {
        "id": empresa.id,
        "nombre": empresa.nombre,
        "slug": empresa.slug,
        "rubro_codigo": rubro.codigo if rubro else "",
        "rubro_nombre": rubro.nombre if rubro else "",
        "preset": preset,
    }