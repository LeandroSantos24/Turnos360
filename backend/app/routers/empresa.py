"""Endpoint de la configuración de la empresa actual (preset del rubro)."""

from fastapi import APIRouter

from app.api.deps import DB, EmpresaActual
from app.schemas.empresa import EmpresaActualOut
from app.services import empresa as svc

router = APIRouter(prefix="/empresa", tags=["empresa"])


@router.get("/actual", response_model=EmpresaActualOut)
def empresa_actual(empresa_id: EmpresaActual, db: DB) -> EmpresaActualOut:
    """Datos de la empresa logueada + el preset de su rubro (módulos, terminología)."""
    return svc.obtener_config(db, empresa_id)