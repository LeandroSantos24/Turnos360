"""Endpoints de estadísticas de facturación.

Toda esta sección es finanzas sensibles -> dueño únicamente. El candado va a
nivel de router (dependencies), así cualquier endpoint de estadísticas que se
agregue en el futuro queda dueño-only por defecto, sin tener que acordarse.
"""

import datetime as dt

from fastapi import APIRouter, Depends

from app.api.deps import DB, EmpresaActual, gate_dueno
from app.schemas.estadisticas import EstadisticasFacturacion
from app.services import estadisticas as svc

router = APIRouter(
    prefix="/estadisticas",
    tags=["estadisticas"],
    dependencies=[Depends(gate_dueno)],
)


@router.get("/facturacion", response_model=EstadisticasFacturacion)
def facturacion(
    desde: dt.datetime,
    hasta: dt.datetime,
    empresa_id: EmpresaActual,
    db: DB,
) -> EstadisticasFacturacion:
    """Facturación real del rango [desde, hasta)."""
    return svc.facturacion(db, empresa_id, desde, hasta)
