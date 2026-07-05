"""Endpoints de la empresa actual: preset del rubro + landing pública editable."""

from fastapi import APIRouter, Depends

from app.api.deps import DB, EmpresaActual, gate_dueno
from app.schemas.empresa import EmpresaActualOut, LandingConfig
from app.services import empresa as svc

router = APIRouter(prefix="/empresa", tags=["empresa"])


@router.get("/actual", response_model=EmpresaActualOut)
def empresa_actual(empresa_id: EmpresaActual, db: DB) -> EmpresaActualOut:
    """Datos de la empresa logueada + el preset de su rubro (módulos, terminología)."""
    return svc.obtener_config(db, empresa_id)


@router.get("/landing", response_model=LandingConfig)
def leer_landing(empresa_id: EmpresaActual, db: DB) -> LandingConfig:
    """Contenido actual de la landing pública (pantalla "Mi página")."""
    return svc.obtener_landing(db, empresa_id)


@router.put(
    "/landing",
    response_model=LandingConfig,
    dependencies=[Depends(gate_dueno)],
)
def guardar_landing(datos: LandingConfig, empresa_id: EmpresaActual, db: DB) -> LandingConfig:
    """Guarda el contenido de la landing. Solo el dueño (config del negocio)."""
    return svc.actualizar_landing(db, empresa_id, datos)