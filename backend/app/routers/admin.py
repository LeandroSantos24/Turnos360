"""Endpoints del panel de super-administración (alta de empresas y usuarios)."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DB, SuperAdminActual
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
)
from app.services import admin as svc

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=AdminToken)
def login(datos: AdminLogin, db: DB) -> AdminToken:
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