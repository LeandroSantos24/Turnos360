"""Schemas del panel de super-administración."""

import re
import unicodedata

from pydantic import BaseModel, EmailStr, Field, field_validator
import datetime as dt

from app.core.planes import Plan
from app.models.enums import RolUsuario


class AdminLogin(BaseModel):
    email: EmailStr = Field(max_length=200)
    clave: str = Field(min_length=1, max_length=100)


class AdminToken(BaseModel):
    access_token: str
    nombre: str


class RubroOut(BaseModel):
    id: int
    codigo: str
    nombre: str

    model_config = {"from_attributes": True}


class DuenoCrear(BaseModel):
    nombre: str = Field(min_length=2)
    # EmailStr y normalizado, igual que UsuarioCrear. Acá había quedado un
    # `str` pelado: se podía dar de alta una empresa cuyo dueño tuviera email
    # "pepe", y esa persona NO podía recuperar su contraseña nunca porque el
    # link de reseteo no tenía a dónde llegar. Y sin el .lower(), "Pepe@Gmail"
    # entraba al índice único de emails sin normalizar, con riesgo de colisión
    # inconsistente. La corrección se le había hecho a UsuarioCrear y a este
    # se le pasó por alto — justo el que crea al usuario más importante.
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def _normalizar_email(cls, v: str) -> str:
        return v.strip().lower()

    clave: str = Field(min_length=8, max_length=100)


# Slugs que NO se pueden usar como identificador de un negocio.
#
# La vidriera pública se sirve en /{slug}, que en Next convive con las rutas
# estáticas del propio sistema. Y Next resuelve la estática ANTES que la
# dinámica: una empresa con slug "login" quedaría con su página pública
# permanentemente inalcanzable, sin ningún error que lo avise. Peor todavía,
# no hay endpoint para editar el slug después: se arregla tocando la base.
#
# Se listan las rutas que existen hoy más las obvias que van a existir. Es
# barato reservar de más y carísimo reservar de menos.
SLUGS_RESERVADOS = frozenset({
    # Rutas reales del frontend
    "login", "admin", "restablecer", "terminos", "privacidad",
    "olvide-password", "imprimir", "registro", "signup", "crear-cuenta",
    "agenda", "clientes", "caja", "recursos", "servicios", "equipo",
    "inicio", "cuenta", "suscripcion", "campanas", "cupones", "membresias",
    "gift-cards", "estadisticas", "metodos-pago", "mi-pagina", "mi-dia",
    "reglas-reserva", "seguimiento", "whatsapp",
    # Rutas del backend y assets
    "api", "publico", "health", "ready", "docs", "static", "_next",
    "favicon.ico", "robots.txt", "sitemap.xml", "icon.png",
    # Nombres que confundirían a un cliente o servirían para hacerse pasar
    # por nosotros.
    "turnos360", "turnos", "turno360", "soporte", "ayuda", "app", "www",
})


class EmpresaCrear(BaseModel):
    nombre: str = Field(min_length=2)
    # max_length además del min: la columna es String(80), y sin esto un slug
    # de 200 caracteres pasaba Pydantic y explotaba con DataError en el INSERT.
    slug: str = Field(min_length=2, max_length=80)

    @field_validator("slug", mode="after")
    @classmethod
    def _normalizar_slug(cls, v: str) -> str:
        """El slug es parte de la URL pública: se normaliza acá, no se confía
        en que el formulario lo haya hecho. Un PUT directo con "Mi Negocio!"
        dejaba una vidriera en una URL rota e irrecuperable sin tocar la base.
        """
        sin_tildes = "".join(
            c
            for c in unicodedata.normalize("NFD", v.lower())
            if unicodedata.category(c) != "Mn"
        )
        limpio = re.sub(r"[^a-z0-9]+", "-", sin_tildes).strip("-")
        if len(limpio) < 2:
            raise ValueError(
                "El identificador tiene que tener al menos 2 letras o números."
            )
        if limpio in SLUGS_RESERVADOS:
            raise ValueError(
                f'"{limpio}" no se puede usar como identificador: es una '
                "dirección reservada del sistema. Probá con otra."
            )
        return limpio
    rubro_id: int
    dueno: DuenoCrear
    # Días de prueba con los que arranca el negocio. 0 = sin prueba (cliente
    # que ya paga). 14 es el valor que ofrece la landing.
    dias_prueba: int = Field(default=14, ge=0, le=90)


class EmpresaAdminOut(BaseModel):
    id: int
    nombre: str
    slug: str
    rubro_nombre: str | None = None
    activa: bool
    cantidad_usuarios: int = 0
    plan: str = "gratuito"
    suscripcion_vence: str | None = None
    estado_suscripcion: str = "sin_vencimiento"  # activa | prorroga | vencida | ...
    prueba_hasta: str | None = None

    model_config = {"from_attributes": True}


class EmpresaPausar(BaseModel):
    activa: bool


class SuscripcionAdminIn(BaseModel):
    """Setear la suscripción de una empresa desde el super-admin."""

    # Plan y no str libre: la columna estuvo meses aceptando cualquier cosa y
    # ahí es donde se apoyan los límites. Un typo en el plan sería un cupo
    # equivocado, y el fallback silencioso es al plan más restrictivo.
    plan: Plan | None = None
    suscripcion_vence: dt.date | None = None
    renovar_30: bool = False           # atajo: vence hoy + 30 días


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=2)
    # EmailStr y no str: antes se podía crear un usuario con email
    # "barbero1", y esa persona no podía recuperar su contraseña nunca
    # porque el link no tenía a dónde llegar.
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def _normalizar(cls, v: str) -> str:
        """A minúsculas: la unicidad no distingue mayúsculas."""
        return v.strip().lower()
    clave: str = Field(min_length=8, max_length=100)
    rol: RolUsuario


class UsuarioAdminOut(BaseModel):
    id: int
    nombre: str
    email: str
    rol: RolUsuario
    activo: bool

    model_config = {"from_attributes": True}


class UsuarioActualizar(BaseModel):
    activo: bool

# ═══════════════════════════════════════════════════════════════════════
# Cobranza del SaaS (tanda 1 del panel de super-admin)
# ═══════════════════════════════════════════════════════════════════════


class EmpresaCobranzaOut(BaseModel):
    """Fila del listado con semáforo, uso y ficha comercial."""

    id: int
    nombre: str
    slug: str
    activa: bool
    plan: str
    suscripcion_vence: str | None = None
    precio_mensual: float | None = None

    razon_social: str | None = None
    cuit: str | None = None
    contacto_nombre: str | None = None
    contacto_email: str | None = None
    contacto_telefono: str | None = None
    notas_admin: str | None = None

    cantidad_usuarios: int = 0
    cantidad_recursos: int = 0
    limite_recursos: int | None = None
    capacidad_excedida: bool = False
    ultimo_pago: str | None = None

    semaforo_color: str  # azul | verde | amarillo | rojo | gris
    semaforo_dias_restantes: int | None = None
    semaforo_fin_prorroga: str | None = None
    semaforo_en_prorroga: bool = False
    semaforo_detalle: str


class MetodoTotal(BaseModel):
    metodo: str
    total: float


class ResumenCobranzaOut(BaseModel):
    # Cuántas cuentas están en prueba ahora. Es el número que dice si el
    # embudo se está moviendo; no suma a ninguna de las tarjetas de plata.
    empresas_en_prueba: int = 0
    cobrado_mes: float
    por_metodo: list[MetodoTotal] = Field(default_factory=list)
    pendiente_estimado: float
    empresas_por_vencer: int
    por_vencer_sin_precio: int
    deuda_vencida: float
    empresas_vencidas: int
    mrr: float
    dias_aviso: int


class PagoSuscripcionIn(BaseModel):
    monto: float = Field(gt=0)
    metodo: str = Field(default="transferencia", max_length=40)
    fecha: dt.date | None = None
    notas: str | None = Field(default=None, max_length=500)
    # False = anotar el pago SIN mover el vencimiento (pago parcial, ajuste).
    renovar: bool = True


class PagoSuscripcionOut(BaseModel):
    id: int
    fecha: str
    monto: float
    metodo: str
    periodo_desde: str | None = None
    periodo_hasta: str | None = None
    notas: str | None = None


class ProrrogaIn(BaseModel):
    dias: int = Field(gt=0, le=90, description="Días de gracia a sumar")


class FichaComercialIn(BaseModel):
    """Datos comerciales del negocio (solo los ve el super-admin)."""

    razon_social: str | None = Field(default=None, max_length=160)
    cuit: str | None = Field(default=None, max_length=20)
    contacto_nombre: str | None = Field(default=None, max_length=120)
    contacto_email: str | None = Field(default=None, max_length=160)
    contacto_telefono: str | None = Field(default=None, max_length=40)
    notas_admin: str | None = Field(default=None, max_length=2000)
    precio_mensual: float | None = Field(default=None, ge=0)
    limite_recursos: int | None = Field(default=None, ge=0, le=999)
    # Igual que limite_recursos: pisa el tope del plan. Vacío = manda la grilla.
    limite_sucursales: int | None = Field(default=None, ge=1, le=99)
