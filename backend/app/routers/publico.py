"""Endpoints públicos de la landing (SIN login), scopeados por slug.

Los consume la página pública del negocio (turnos360.com/<slug>). El tenant sale
del slug (no hay token). La reserva va con rate limit (anti-spam de v1); detrás de
Nginx hay que pasar la IP real (X-Forwarded-For) o todos caen en el mismo bucket.
"""

import datetime as dt

from fastapi import APIRouter, Query, Request

from app.api.deps import DB
from app.core.rate_limit import limiter
from app.schemas.publico import (
    HuecosDia,
    ReservaPublicaCrear,
    ReservaPublicaOut,
    VidrieraOut,
)
from app.services import publico as svc

router = APIRouter(prefix="/publico", tags=["publico"])


@router.get("/{slug}", response_model=VidrieraOut)
def vidriera(slug: str, db: DB) -> VidrieraOut:
    """Datos de la página del negocio: info + servicios + equipo."""
    return svc.vidriera(db, slug)


@router.get("/{slug}/horarios", response_model=list[HuecosDia])
def horarios(
    slug: str,
    db: DB,
    servicio_id: int = Query(...),
    recurso_id: int | None = Query(default=None),
    desde: dt.date | None = Query(default=None),
    dias: int = Query(default=14, ge=1, le=60),
) -> list[HuecosDia]:
    """Horarios de inicio libres por día. recurso_id vacío = cualquiera."""
    return svc.huecos(db, slug, servicio_id, recurso_id, desde or dt.date.today(), dias)


@router.post("/{slug}/reservar", response_model=ReservaPublicaOut)
@limiter.limit("10/minute")
def reservar(
    request: Request, slug: str, datos: ReservaPublicaCrear, db: DB
) -> ReservaPublicaOut:
    """Crea la reserva (estado PENDIENTE) y busca-o-crea el cliente por teléfono."""
    return svc.reservar(db, slug, datos)