"""Endpoints del panel de super-administración (alta de empresas y usuarios)."""

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
)
from app.services import admin as svc

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=AdminToken)
@limiter.limit("5/minute")
def login(request: Request, datos: AdminLogin, db: DB) -> AdminToken:
    # Rate limit estricto: es el endpoint más sensible del sistema (controla
    # todos los tenants) y hay un solo operador legítimo. Detrás de Nginx,
    # configurar el proxy para pasar la IP real (X-Forwarded-For) o todos los
    # clientes caen en el mismo bucket.
    sa = svc.autenticar_admin(db, datos.email, datos.clave)
    if sa is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Email o contraseña incorrectos"
        )
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
