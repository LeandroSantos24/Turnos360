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
    recurso_id: int | None = None,
) -> EstadisticasFacturacion:
    """Facturación real del rango [desde, hasta).

    recurso_id opcional: filtra TODO el panel a ese profesional (sus cobros,
    sus servicios, sus horarios y su ausentismo). El servicio ya lo soportaba;
    faltaba declararlo acá, así que el filtro que mandaba el panel se
    descartaba en silencio y las tarjetas seguían mostrando el total.

    No hace falta validar que el recurso sea de la empresa: el servicio cruza
    siempre por empresa_id, así que un id ajeno devuelve vacío, nunca datos
    de otro negocio.
    """
    return svc.facturacion(db, empresa_id, desde, hasta, recurso_id)
