"""Configuración de la empresa actual: arma el preset efectivo para el front."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.services import mercadopago as mp
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
        "portada_url": empresa.portada_url,
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
    empresa.portada_url = datos.portada_url
    empresa.color_marca = datos.color_marca
    empresa.horarios_atencion = datos.horarios_atencion
    empresa.redes = datos.redes or {}
    empresa.galeria = [u.strip() for u in (datos.galeria or []) if u and u.strip()][:12]
    db.commit()
    return obtener_landing(db, empresa_id)

def probar_mp(db: Session, empresa_id: int) -> dict:
    """Revalida el token guardado. Para el botón «Probar conexión».

    Existe porque un token que andaba puede dejar de andar: el dueño lo
    revoca desde Mercado Pago, cambia de cuenta, o da de baja la
    aplicación. Sin esto, la única forma de enterarse es que un cliente no
    pueda pagar.
    """
    empresa = db.get(Empresa, empresa_id)
    token = mp.token_de(empresa)
    if not token:
        raise mp.TokenInvalido("Todavía no conectaste Mercado Pago.")
    cuenta = mp.validar_token(token)
    # Se re-guarda por si la cuenta cambió de nombre.
    mp.guardar_token(empresa, token, cuenta)
    db.commit()
    return cuenta


def config_senas(db: Session, empresa_id: int) -> dict:
    """Estado de señas para el panel (sin exponer el token)."""
    empresa = db.get(Empresa, empresa_id)
    return {
        "sena_activa": empresa.sena_activa,
        "sena_monto": float(empresa.sena_monto) if empresa.sena_monto else None,
        "cobro_modo": empresa.cobro_modo or "ninguno",
        "mp_conectado": empresa.mp_credenciales is not None,
        "mp_cuenta": mp.cuenta_de(empresa),
    }


def guardar_senas(db: Session, empresa_id: int, datos) -> dict:
    """Guarda switch + monto; el token solo si vino uno nuevo (no se pisa con vacío)."""
    empresa = db.get(Empresa, empresa_id)
    empresa.cobro_modo = datos.cobro_modo
    # sena_activa queda sincronizado (compatibilidad con lo ya construido).
    empresa.sena_activa = datos.cobro_modo != "ninguno"
    empresa.sena_monto = datos.sena_monto
    if datos.mp_access_token and datos.mp_access_token.strip():
        # Se valida ANTES de guardar. Si el token no sirve, no se guarda
        # nada y el dueño ve el motivo — en vez de un tilde verde mentiroso
        # y un cliente que dentro de tres días no puede pagar.
        cuenta = mp.validar_token(datos.mp_access_token)
        mp.guardar_token(empresa, datos.mp_access_token, cuenta)
    db.commit()
    return config_senas(db, empresa_id)


# ============================================================
# Automatizaciones (campañas): defaults + get/put
# ============================================================

AUTOMS_DEFAULTS: dict = {
    "recordatorio_24h": {"activa": True},
    "recordatorio_2h": {"activa": False},
    "cumple": {"activa": False, "dias_antes": 7, "mensaje": ""},
    "resena_google": {"activa": False, "link": ""},
    "inactivos": {"activa": False, "dias": 60, "mensaje": ""},
}


def automs_de(empresa) -> dict:
    """Config de automatizaciones de la empresa, con defaults completados."""
    guardado = empresa.automatizaciones or {}
    resultado = {}
    for clave, defaults in AUTOMS_DEFAULTS.items():
        resultado[clave] = {**defaults, **(guardado.get(clave) or {})}
    return resultado


def config_automatizaciones(db: Session, empresa_id: int) -> dict:
    empresa = db.get(Empresa, empresa_id)
    return automs_de(empresa)


def guardar_automatizaciones(db: Session, empresa_id: int, datos: dict) -> dict:
    empresa = db.get(Empresa, empresa_id)
    empresa.automatizaciones = datos
    db.commit()
    return automs_de(empresa)


# ===== REGLAS DE LA RESERVA PÚBLICA =====

_CAMPOS_REGLAS = (
    "anticipacion_min",
    "dias_max",
    "fecha_limite",
    "permite_cancelar",
    "pide_telefono",
    "pide_nacimiento",
)


def obtener_reglas_reserva(db: Session, empresa_id: int) -> dict:
    """Reglas actuales del negocio (pantalla de configuración)."""
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")
    return {c: getattr(empresa, f"reserva_{c}") for c in _CAMPOS_REGLAS}


def actualizar_reglas_reserva(db: Session, empresa_id: int, datos) -> dict:
    """Guarda las reglas. El schema ya validó los rangos."""
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")
    for c in _CAMPOS_REGLAS:
        setattr(empresa, f"reserva_{c}", getattr(datos, c))
    db.commit()
    db.refresh(empresa)
    return {c: getattr(empresa, f"reserva_{c}") for c in _CAMPOS_REGLAS}


# ===== SEGUIMIENTO PUBLICITARIO =====

def obtener_seguimiento(db: Session, empresa_id: int) -> dict:
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")
    return {
        "meta_pixel_id": empresa.meta_pixel_id,
        "google_tag_id": empresa.google_tag_id,
        "google_conversion_label": empresa.google_conversion_label,
    }


def actualizar_seguimiento(db: Session, empresa_id: int, datos) -> dict:
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")
    empresa.meta_pixel_id = datos.meta_pixel_id
    empresa.google_tag_id = datos.google_tag_id
    # La etiqueta solo sirve con un tag de Ads. Si el negocio pasó a un
    # G- de Analytics, se limpia sola: dejarla colgada haría que el día
    # que vuelva a Ads dispare contra una conversión que ya no existe.
    empresa.google_conversion_label = (
        datos.google_conversion_label
        if (datos.google_tag_id or "").upper().startswith("AW-")
        else None
    )
    db.commit()
    db.refresh(empresa)
    return {
        "meta_pixel_id": empresa.meta_pixel_id,
        "google_tag_id": empresa.google_tag_id,
        "google_conversion_label": empresa.google_conversion_label,
    }
