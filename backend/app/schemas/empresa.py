from typing import Literal

"""Schema de la configuración de la empresa actual (preset del rubro).

Lo consume el frontend al iniciar sesión para saber:
- qué módulos mostrar (preset["modulos"], ej. ficha_clinica),
- cómo nombrar las cosas (preset["terminologia"], ej. cliente -> paciente).
"""

from pydantic import BaseModel, Field


class EmpresaActualOut(BaseModel):
    id: int
    nombre: str
    slug: str
    rubro_codigo: str
    rubro_nombre: str
    # El preset del rubro (terminologia, modulos, campos_cliente...), ya con
    # los overrides de la empresa aplicados si los hubiera.
    preset: dict


class LandingConfig(BaseModel):
    """Contenido editable de la landing pública del negocio (pantalla "Mi página").

    Mismo shape para leer (GET) y guardar (PUT): el form tiene todos los campos
    y los manda todos. Todo opcional -> el dueño completa de a poco.

    - horarios_atencion: SOLO para mostrar (no calcula huecos). Estructura libre;
      la define el frontend (ej. {"lun": [["09:00","13:00"],["17:00","21:00"]], ...}).
    - redes: dict libre. Claves conocidas: instagram, facebook, tiktok, linkedin,
      sitio_web. Sumar una red nueva = agregar clave, sin migración.
    - color_marca: hex del acento, ej. "#00d4aa".
    """

    descripcion: str | None = None
    direccion: str | None = None
    telefono_publico: str | None = None
    email_publico: str | None = None
    logo_url: str | None = None
    color_marca: str | None = None
    horarios_atencion: dict | None = None
    redes: dict = {}
    # Galería de la landing: lista de URLs de fotos (máx. razonable: 12).
    galeria: list[str] = []

class SenasConfigOut(BaseModel):
    """Estado de la config de señas (el token JAMÁS se devuelve)."""

    sena_activa: bool
    sena_monto: float | None
    cobro_modo: str = "ninguno"
    mp_conectado: bool


class SenasConfigIn(BaseModel):
    """Guardado de señas. mp_access_token: solo si viene no-vacío se actualiza."""

    sena_activa: bool = False
    sena_monto: float | None = Field(default=None, ge=0)
    cobro_modo: Literal["ninguno", "sena", "total"] = "ninguno"
    mp_access_token: str | None = Field(default=None, max_length=300)


class AutomSwitch(BaseModel):
    activa: bool = False


class AutomCumple(AutomSwitch):
    dias_antes: int = Field(default=7, ge=0, le=30)
    mensaje: str = Field(default="", max_length=500)


class AutomResena(AutomSwitch):
    link: str = Field(default="", max_length=300)


class AutomInactivos(AutomSwitch):
    dias: int = Field(default=60, ge=7, le=365)
    mensaje: str = Field(default="", max_length=500)


class AutomatizacionesConfig(BaseModel):
    """La pantalla Campañas: cada automatización con su switch y su config."""

    recordatorio_24h: AutomSwitch = AutomSwitch(activa=True)
    recordatorio_2h: AutomSwitch = AutomSwitch()
    cumple: AutomCumple = AutomCumple()
    resena_google: AutomResena = AutomResena()
    inactivos: AutomInactivos = AutomInactivos()


class SuscripcionOut(BaseModel):
    plan: str
    estado: str  # activa | prorroga | vencida | sin_vencimiento
    vence: str | None
    dias_restantes: int | None
    en_prorroga: bool
    mensaje: str
