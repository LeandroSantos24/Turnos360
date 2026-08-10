"""Endpoints del panel de super-administración (alta de empresas y usuarios)."""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import DB, SuperAdminActual
from app.core.rate_limit import limiter
from app.core.seguridad import crear_token_superadmin
from app.schemas.admin import (
    AdminLogin,
    AdminToken,
    EmpresaAdminOut,
    EmpresaCrear,
    EmpresaPausar,
    RubroOut,
    UsuarioActualizar,
    UsuarioAdminOut,
    UsuarioCrear,
    SuscripcionAdminIn,
    EmpresaCobranzaOut,
    ResumenCobranzaOut,
    PagoSuscripcionIn,
    PagoSuscripcionOut,
    ProrrogaIn,
    FichaComercialIn,
)
from app.models import Empresa
from app.services import admin as svc
from app.services import cobranza

router = APIRouter(prefix="/admin", tags=["admin"])


def _ip_real(request: Request) -> str:
    """IP del cliente, mirando primero el header del proxy.

    Detrás de Nginx, request.client.host es SIEMPRE la IP del proxy (172.x
    dentro de Docker). El primer valor de X-Forwarded-For es el visitante
    real; los siguientes son los proxies intermedios.
    """
    reenviada = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if reenviada:
        return reenviada
    return request.client.host if request.client else "desconocida"


def _avisar_acceso(request: Request, *, email: str, exito: bool, nombre: str | None) -> None:
    """Encola el aviso de acceso al panel. Nunca rompe el login.

    Todo lo de acá adentro es best-effort: si Redis está caído, el operador
    tiene que poder entrar igual a su panel. Por eso el except amplio.
    """
    from app.core.config import settings

    if not settings.avisar_acceso_admin:
        return
    if not exito and not settings.admin_alerta_fallidos:
        return
    try:
        import datetime as _dt
        from zoneinfo import ZoneInfo

        from app.tasks.emails import avisar_acceso_admin

        ahora = _dt.datetime.now(ZoneInfo(settings.zona_horaria))
        avisar_acceso_admin.delay(
            email_intentado=email,
            exito=exito,
            ip=_ip_real(request),
            agente=(request.headers.get("user-agent") or "desconocido")[:200],
            cuando=ahora.strftime("%d/%m/%Y a las %H:%M") + " (hora de Argentina)",
            nombre=nombre,
        )
    except Exception:  # pragma: no cover - el login no depende de esto
        logging.getLogger(__name__).exception(
            "No se pudo encolar el aviso de acceso al panel de admin"
        )


@router.post("/login", response_model=AdminToken)
@limiter.limit("5/minute")
def login(request: Request, datos: AdminLogin, db: DB) -> AdminToken:
    # Rate limit estricto: es el endpoint más sensible del sistema (controla
    # todos los tenants) y hay un solo operador legítimo. Detrás de Nginx,
    # configurar el proxy para pasar la IP real (X-Forwarded-For) o todos los
    # clientes caen en el mismo bucket.
    sa = svc.autenticar_admin(db, datos.email, datos.clave)
    if sa is None:
        _avisar_acceso(request, email=datos.email, exito=False, nombre=None)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Email o contraseña incorrectos"
        )
    _avisar_acceso(request, email=sa.email, exito=True, nombre=sa.nombre)
    return AdminToken(access_token=crear_token_superadmin(sa.id), nombre=sa.nombre)


@router.get("/rubros", response_model=list[RubroOut])
def rubros(admin: SuperAdminActual, db: DB):
    return svc.listar_rubros(db)


@router.get("/empresas", response_model=list[EmpresaAdminOut])
def empresas(admin: SuperAdminActual, db: DB):
    return svc.listar_empresas(db)


@router.post(
    "/empresas", response_model=EmpresaAdminOut, status_code=status.HTTP_201_CREATED
)
def crear_empresa(datos: EmpresaCrear, admin: SuperAdminActual, db: DB):
    return svc.crear_empresa(db, datos)


@router.patch("/empresas/{empresa_id}", response_model=EmpresaAdminOut)
def pausar_empresa(
    empresa_id: int, datos: EmpresaPausar, admin: SuperAdminActual, db: DB
):
    return svc.pausar_empresa(db, empresa_id, datos.activa)


@router.get(
    "/empresas/{empresa_id}/usuarios", response_model=list[UsuarioAdminOut]
)
def usuarios(empresa_id: int, admin: SuperAdminActual, db: DB):
    return svc.listar_usuarios(db, empresa_id)


@router.post(
    "/empresas/{empresa_id}/usuarios",
    response_model=UsuarioAdminOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_usuario(
    empresa_id: int, datos: UsuarioCrear, admin: SuperAdminActual, db: DB
):
    return svc.crear_usuario(db, empresa_id, datos)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioAdminOut)
def actualizar_usuario(
    usuario_id: int, datos: UsuarioActualizar, admin: SuperAdminActual, db: DB
):
    return svc.actualizar_usuario(db, usuario_id, datos.activo)

@router.patch("/empresas/{empresa_id}/suscripcion", response_model=EmpresaAdminOut)
def setear_suscripcion(
    empresa_id: int,
    datos: SuscripcionAdminIn,
    admin: SuperAdminActual,
    db: DB,
):
    """Setea el plan y/o el vencimiento de la suscripción (solo super-admin)."""
    return svc.setear_suscripcion(
        db, empresa_id, datos.plan, datos.suscripcion_vence, datos.renovar_30
    )


# ═══════════════════════════════════════════════════════════════════════
# Cobranza del SaaS: semáforo, resumen, pagos y prórrogas
# ═══════════════════════════════════════════════════════════════════════


@router.get("/cobranza/empresas", response_model=list[EmpresaCobranzaOut])
def cobranza_empresas(
    admin: SuperAdminActual,
    db: DB,
    buscar: str | None = None,
    color: str | None = None,
    plan: str | None = None,
    activa: bool | None = None,
):
    """Listado con semáforo de cobranza.

    color: verde (al día) · amarillo (vence en <=7 días) · rojo (vencida,
    incluye prórroga) · gris (sin vencimiento).
    """
    return cobranza.listar_empresas(db, buscar=buscar, color=color, plan=plan, activa=activa)


@router.get("/cobranza/resumen", response_model=ResumenCobranzaOut)
def cobranza_resumen(admin: SuperAdminActual, db: DB):
    """Tarjetas de balance: cobrado del mes, pendiente estimado, deuda y MRR."""
    return cobranza.resumen_cobranza(db)


@router.get(
    "/empresas/{empresa_id}/pagos", response_model=list[PagoSuscripcionOut]
)
def historial_pagos(empresa_id: int, admin: SuperAdminActual, db: DB):
    _empresa_o_404(db, empresa_id)
    return cobranza.historial_pagos(db, empresa_id)


@router.post(
    "/empresas/{empresa_id}/pagos",
    response_model=PagoSuscripcionOut,
    status_code=status.HTTP_201_CREATED,
)
def registrar_pago(
    empresa_id: int, datos: PagoSuscripcionIn, admin: SuperAdminActual, db: DB
):
    """Registra una cuota cobrada. Por defecto empuja el vencimiento 30 días."""
    empresa = _empresa_o_404(db, empresa_id)
    pago = cobranza.registrar_pago(
        db,
        empresa,
        monto=datos.monto,
        metodo=datos.metodo,
        fecha=datos.fecha,
        notas=datos.notas,
        registrado_por=admin.email,
        renovar=datos.renovar,
    )
    db.commit()
    return {
        "id": pago.id,
        "fecha": str(pago.fecha),
        "monto": float(pago.monto),
        "metodo": pago.metodo,
        "periodo_desde": str(pago.periodo_desde) if pago.periodo_desde else None,
        "periodo_hasta": str(pago.periodo_hasta) if pago.periodo_hasta else None,
        "notas": pago.notas,
    }


@router.post("/empresas/{empresa_id}/prorroga", response_model=EmpresaCobranzaOut)
def dar_prorroga(
    empresa_id: int, datos: ProrrogaIn, admin: SuperAdminActual, db: DB
):
    """Suma días de gracia al vencimiento (o extiende una prueba)."""
    empresa = _empresa_o_404(db, empresa_id)
    cobranza.prorrogar(db, empresa, datos.dias)
    db.commit()
    return _fila_de(db, empresa_id)


@router.put("/empresas/{empresa_id}/ficha", response_model=EmpresaCobranzaOut)
def guardar_ficha(
    empresa_id: int, datos: FichaComercialIn, admin: SuperAdminActual, db: DB
):
    """Guarda los datos comerciales (razón social, CUIT, contacto, precio)."""
    empresa = _empresa_o_404(db, empresa_id)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(empresa, campo, valor)
    db.commit()
    return _fila_de(db, empresa_id)


def _empresa_o_404(db, empresa_id: int) -> Empresa:
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")
    return empresa


def _fila_de(db, empresa_id: int) -> dict:
    """Devuelve la fila del listado (con semáforo recalculado) de UNA empresa."""
    filas = cobranza.listar_empresas(db)
    fila = next((f for f in filas if f["id"] == empresa_id), None)
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empresa no encontrada")
    return fila
