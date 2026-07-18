"""Endpoints públicos de la landing (SIN login), scopeados por slug.

Los consume la página pública del negocio (turnos360.com/<slug>). El tenant sale
del slug (no hay token). La reserva va con rate limit (anti-spam de v1); detrás de
Nginx hay que pasar la IP real (X-Forwarded-For) o todos caen en el mismo bucket.
"""

import datetime as dt

from anyio import to_thread
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from app.api.deps import DB
from app.core.rate_limit import limiter
from app.schemas.cupon import CuponValidarIn, CuponValidarOut
from app.schemas.publico import (
    HuecosDia,
    ReservaPublicaCrear,
    ReservaPublicaOut,
    VidrieraOut,
)
from app.models import Turno
from app.models.enums import EstadoTurno
from app.services import mercadopago as mp
from app.services import publico as svc

router = APIRouter(prefix="/publico", tags=["publico"])


@router.post("/mp/webhook/{slug}")
async def mp_webhook(slug: str, request: Request, db: DB) -> dict:
    """Notificaciones de Mercado Pago (pagos de señas).

    MP reintenta ante non-200, así que SIEMPRE devolvemos ok. La autenticidad
    se valida consultando el pago a la API con el token del propio negocio:
    si el payment_id no existe en SU cuenta, no hay pago que marcar.
    """
    params = request.query_params
    tipo = params.get("type") or params.get("topic") or ""
    payment_id = params.get("data.id") or params.get("id")
    if not payment_id:
        try:
            body = await request.json()
            tipo = body.get("type", tipo)
            payment_id = (body.get("data") or {}).get("id")
        except Exception:
            payment_id = None
    if "payment" not in tipo or not payment_id:
        return {"ok": True}  # topic que no manejamos (merchant_order, etc.)

    try:
        empresa = svc.resolver_empresa(db, slug)
    except HTTPException:
        return {"ok": True}

    # Idempotencia: MP reintenta la misma notificación varias veces. Si este
    # pago ya quedó registrado en un turno de la empresa, cortamos acá y nos
    # ahorramos la llamada saliente a la API de MP en cada reintento.
    ya_procesado = db.scalar(
        select(Turno).where(
            Turno.empresa_id == empresa.id,
            Turno.mp_payment_id == str(payment_id),
        )
    )
    if ya_procesado is not None:
        return {"ok": True}

    token = mp.token_de(empresa)
    if not token:
        return {"ok": True}

    # El cliente de MP es httpx sincrónico y este endpoint es async: la llamada
    # va al threadpool para no frenar el event loop mientras responde MP.
    pago = await to_thread.run_sync(mp.consultar_pago, token, str(payment_id))
    if not pago or pago.get("status") != "approved":
        return {"ok": True}

    ref = pago.get("external_reference")
    turno = db.get(Turno, int(ref)) if ref and str(ref).isdigit() else None
    if turno is None or turno.empresa_id != empresa.id:
        return {"ok": True}

    turno.sena_estado = "pagada"
    turno.mp_payment_id = str(pago.get("id", payment_id))
    if turno.estado == EstadoTurno.PENDIENTE:
        # Pagó la seña => el turno se confirma solo (transición válida).
        turno.estado = EstadoTurno.CONFIRMADO
    db.commit()
    return {"ok": True}


@router.get("/slugs", response_model=list[str])
def slugs(db: DB) -> list[str]:
    """Slugs de las empresas activas (para el sitemap).

    OJO: registrado ANTES de /{slug} para que "slugs" no se tome como empresa.
    """
    return svc.slugs_activos(db)


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

@router.post("/{slug}/cupon/validar", response_model=CuponValidarOut)
@limiter.limit("20/minute")
def validar_cupon_publico(
    request: Request, slug: str, datos: CuponValidarIn, db: DB
) -> CuponValidarOut:
    """El wizard valida el código ANTES de reservar, para mostrar el descuento.

    Con rate limit: sin él, este endpoint permite fuerza bruta de códigos de
    cupón (descubrir promociones probando "PROMO10", "VERANO", etc.).
    """
    from app.services import cupones as svc_cupones
    from app.services.publico import resolver_empresa

    empresa = resolver_empresa(db, slug)  # 404 si no existe o está pausada
    cupon, descuento, mensaje = svc_cupones.validar_cupon(
        db, empresa.id, datos.codigo, datos.servicio_id
    )
    if cupon is None:
        return CuponValidarOut(valido=False, mensaje=mensaje)
    # precio final estimado (sobre el precio del servicio)
    from app.models.agenda import Servicio
    servicio = db.scalar(
        select(Servicio).where(Servicio.id == datos.servicio_id, Servicio.empresa_id == empresa.id)
    )
    precio = float(servicio.precio) if servicio and servicio.precio else 0.0
    return CuponValidarOut(
        valido=True,
        mensaje=mensaje,
        descuento=descuento,
        precio_final=round(precio - descuento, 2),
    )
