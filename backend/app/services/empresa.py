"""Configuración de la empresa actual: arma el preset efectivo para el front."""

from sqlalchemy.orm import Session

from app.models import Empresa, Rubro
from app.schemas.empresa import LandingConfig


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


def obtener_landing(db: Session, empresa_id: int) -> dict:
    """Contenido actual de la landing pública del negocio (para "Mi página")."""
    empresa = db.get(Empresa, empresa_id)
    return {
        "descripcion": empresa.descripcion,
        "direccion": empresa.direccion,
        "telefono_publico": empresa.telefono_publico,
        "email_publico": empresa.email_publico,
        "logo_url": empresa.logo_url,
        "color_marca": empresa.color_marca,
        "horarios_atencion": empresa.horarios_atencion,
        "redes": empresa.redes or {},
        "galeria": empresa.galeria or [],
    }


def actualizar_landing(db: Session, empresa_id: int, datos: LandingConfig) -> dict:
    """Guarda el contenido de la landing. El form manda todos los campos."""
    empresa = db.get(Empresa, empresa_id)
    empresa.descripcion = datos.descripcion
    empresa.direccion = datos.direccion
    empresa.telefono_publico = datos.telefono_publico
    empresa.email_publico = datos.email_publico
    empresa.logo_url = datos.logo_url
    empresa.color_marca = datos.color_marca
    empresa.horarios_atencion = datos.horarios_atencion
    empresa.redes = datos.redes or {}
    empresa.galeria = [u.strip() for u in (datos.galeria or []) if u and u.strip()][:12]
    db.commit()
    return obtener_landing(db, empresa_id)