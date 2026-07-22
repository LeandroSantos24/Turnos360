"""Schemas del panel de super-administración."""

from pydantic import BaseModel, Field
import datetime as dt

from app.models.enums import RolUsuario


class AdminLogin(BaseModel):
    email: str
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
    email: str
    clave: str = Field(min_length=8, max_length=100)


class EmpresaCrear(BaseModel):
    nombre: str = Field(min_length=2)
    slug: str = Field(min_length=2)
    rubro_id: int
    dueno: DuenoCrear


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

    model_config = {"from_attributes": True}


class EmpresaPausar(BaseModel):
    activa: bool


class SuscripcionAdminIn(BaseModel):
    """Setear la suscripción de una empresa desde el super-admin."""

    plan: str | None = None            # gratuito | pro
    suscripcion_vence: dt.date | None = None
    renovar_30: bool = False           # atajo: vence hoy + 30 días


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=2)
    email: str
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

    semaforo_color: str  # verde | amarillo | rojo | gris
    semaforo_dias_restantes: int | None = None
    semaforo_fin_prorroga: str | None = None
    semaforo_en_prorroga: bool = False
    semaforo_detalle: str


class MetodoTotal(BaseModel):
    metodo: str
    total: float


class ResumenCobranzaOut(BaseModel):
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
