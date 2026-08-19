"""Schema de la configuración de la empresa actual (preset del rubro).

Lo consume el frontend al iniciar sesión para saber:
- qué módulos mostrar (preset["modulos"], ej. ficha_clinica),
- cómo nombrar las cosas (preset["terminologia"], ej. cliente -> paciente).
"""

import datetime as dt
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Las URLs de imagen del negocio terminan dentro de un url(...) de CSS y de un
# <img src>. Aceptamos SOLO http(s) absoluto y sin comillas ni paréntesis: sin
# esto, un PUT directo a /empresa/landing (salteando el formulario, que sí
# valida) mete cualquier string y rompe la vidriera del negocio.
_URL_IMAGEN = re.compile(r"^https?://[^\s\"'()<>]+$", re.IGNORECASE)


def _url_imagen_o_none(v: str | None) -> str | None:
    """Devuelve la URL limpia, o None si no es una URL de imagen usable."""
    if v is None:
        return None
    limpia = v.strip()
    if not limpia:
        return None
    if not _URL_IMAGEN.match(limpia):
        raise ValueError(
            "Tiene que ser un link que empiece con http:// o https:// "
            "y no contenga espacios ni comillas."
        )
    return limpia



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
    # Foto de fondo del hero de la vidriera (opcional).
    portada_url: str | None = None
    color_marca: str | None = None
    horarios_atencion: dict | None = None
    redes: dict = {}
    # Galería de la landing: lista de URLs de fotos (máx. razonable: 12).
    galeria: list[str] = []

    @field_validator("logo_url", "portada_url", mode="after")
    @classmethod
    def _validar_url_imagen(cls, v: str | None) -> str | None:
        return _url_imagen_o_none(v)

    @field_validator("galeria", mode="after")
    @classmethod
    def _validar_galeria(cls, v: list[str]) -> list[str]:
        # Descartamos en silencio lo que no sea una URL usable en vez de
        # rechazar todo el formulario: si el dueño pegó mal una de doce fotos,
        # no tiene sentido perderle las otras once.
        limpias = []
        for u in v or []:
            try:
                url = _url_imagen_o_none(u)
            except ValueError:
                continue
            if url:
                limpias.append(url)
        return limpias[:12]

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
    estado: str  # prueba | activa | prorroga | vencida | sin_vencimiento
    vence: str | None
    dias_restantes: int | None
    en_prorroga: bool
    mensaje: str
    # Hasta cuándo puede pagar sin que se corte el servicio (vencimiento + gracia).
    corte: str | None = None
    dias_hasta_corte: int | None = None


class PagoSuscripcionOut(BaseModel):
    """Una fila del historial de pagos, como la ve el NEGOCIO.

    Sin `notas` ni `registrado_por`: son apuntes internos de cobranza y no
    tienen por qué llegarle al cliente.
    """

    fecha: str | None
    monto: float
    metodo: str
    periodo_desde: str | None = None
    periodo_hasta: str | None = None


class DatosCobro(BaseModel):
    """Los datos para transferirle a Turnos360. Salen del entorno."""

    cbu: str | None = None
    alias: str | None = None
    titular: str | None = None
    cuit: str | None = None
    banco: str | None = None
    mp_link: str | None = None
    # WhatsApp al que el negocio manda el comprobante. Sin esto, "mandanos el
    # comprobante" es una instrucción sin destino.
    whatsapp: str | None = None


class MiSuscripcionOut(SuscripcionOut):
    """Todo lo que ve el dueño en "Mi suscripción"."""

    precio_mensual: float | None = None
    dias_prorroga: int = 10
    # Último monto pagado: sirve de referencia cuando todavía no se cargó la
    # cuota pactada, para no mostrarle un guion a alguien que ya pagó.
    ultimo_monto: float | None = None
    # Precio de lista vigente (config del servidor), para el aviso de la prueba.
    precio_lista: float | None = None
    pagos: list[PagoSuscripcionOut] = []
    cobro: DatosCobro = DatosCobro()


class ReglasReservaConfig(BaseModel):
    """Reglas de la reserva pública, configurables por el dueño.

    Antes vivían hardcodeadas en services/publico.py e iguales para todos los
    negocios. El GET y el PUT usan el mismo schema (como LandingConfig).
    """

    # Minutos mínimos entre "ahora" y el turno. 0 = se puede reservar para
    # dentro de un rato. Tope de 7 días: más que eso es un error de carga.
    anticipacion_min: int = Field(default=0, ge=0, le=10080)
    # Días hacia adelante. Mínimo 1 (nunca dejar la agenda en cero por error).
    dias_max: int = Field(default=180, ge=1, le=365)
    # Cierre fijo de agenda. Manda la MÁS restrictiva entre esta y dias_max.
    fecha_limite: dt.date | None = None
    permite_cancelar: bool = True
    pide_telefono: bool = True
    # Alimenta la campaña de cumpleaños que ya existe (E8).
    pide_nacimiento: bool = False


# El ID termina DENTRO de un <script> en la vidriera pública. Si aceptáramos
# cualquier string, un dueño (o alguien con su sesión) podría cerrar la comilla
# e inyectar JavaScript en su propia página: XSS que roba los datos de los
# clientes que reservan. Por eso el formato es una lista blanca cerrada.
_META_PIXEL = re.compile(r"^\d{6,20}$")                    # solo dígitos
_GOOGLE_TAG = re.compile(r"^(G|AW|GT|UA)-[A-Z0-9-]{4,30}$", re.IGNORECASE)


class SeguimientoConfig(BaseModel):
    """Meta Pixel y Google Tag del negocio, para medir sus campañas."""

    meta_pixel_id: str | None = None
    google_tag_id: str | None = None

    @field_validator("meta_pixel_id", mode="after")
    @classmethod
    def _validar_pixel(cls, v: str | None) -> str | None:
        limpio = (v or "").strip()
        if not limpio:
            return None
        if not _META_PIXEL.match(limpio):
            raise ValueError(
                "El Meta Pixel ID son solo números (entre 6 y 20 dígitos). "
                "Lo encontrás en Meta Business Suite → Administrador de eventos."
            )
        return limpio

    @field_validator("google_tag_id", mode="after")
    @classmethod
    def _validar_tag(cls, v: str | None) -> str | None:
        limpio = (v or "").strip()
        if not limpio:
            return None
        if not _GOOGLE_TAG.match(limpio):
            raise ValueError(
                "El ID de Google tiene la forma G-XXXXXXX o AW-XXXXXXXXX."
            )
        return limpio.upper()
