"""Endpoints de estadísticas de facturación."""

import datetime as dt

from fastapi import APIRouter

from app.api.deps import DB, EmpresaActual
from app.schemas.estadisticas import EstadisticasFacturacion
from app.services import estadisticas as svc

router = APIRouter(prefix="/estadisticas", tags=["estadisticas"])


@router.get("/facturacion", response_model=EstadisticasFacturacion)
def facturacion(
    desde: dt.datetime,
    hasta: dt.datetime,
    empresa_id: EmpresaActual,
    db: DB,
) -> EstadisticasFacturacion:
    """Facturación real del rango [desde, hasta)."""
    return svc.facturacion(db, empresa_id, desde, hasta)