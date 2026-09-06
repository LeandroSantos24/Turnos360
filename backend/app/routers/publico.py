"""Endpoints públicos de la landing (SIN login), scopeados por slug.

Los consume la página pública del negocio (turnos360.com/<slug>). El tenant sale
del slug (no hay token). La reserva va con rate limit (anti-spam de v1); detrás de
Nginx hay que pasar la IP real (X-Forwarded-For) o todos caen en el mismo bucket.
"""

import datetime as dt

from anyio import to_thread
from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from app.api.deps import DB
import logging

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.reloj import hoy_de_pared
from app.schemas.cupon import CuponValidarIn, CuponValidarOut
from app.core.seguridad import crear_access_token, crear_refresh_token
from app.schemas.publico import (
    RegistroIn,
    RegistroOut,
    RubroPublicoOut,
    HuecosDia,
    ReservaPublicaCrear,
    ReservaPublicaOut,
    VidrieraOut,
)
from app.models import Turno
from app.models.enums import EstadoTurno
from app.services import finanzas as svc_fin
from app.core import firma_mp
from app.services import mercadopago as mp
from app.services import mp_debito
from app.services import mp_suscripcion as mp_sus
from app.services import publico as svc
from app.services import visitas
from app.services import registro as svc_registro

log = logging.getLogger("turnos360.mp")

router = APIRouter(prefix="/publico", tags=["publico"])


def _es_id_numerico(ident: str) -> bool:
    """Los ids de pagos y de cobros mensuales son números."""
    return ident.isdigit() and len(ident) <= 24


def _es_id_de_suscripcion(ident: str) -> bool:
    """Los ids de preapproval NO son números: son hexadecimal.

    Se ven así: `2c938084726fca480172750000000000`. La primera versión de
    este despacho les aplicaba el mismo `.isdigit()` que a los pagos, y eso
    habría descartado en silencio TODAS las notificaciones de suscripciones:
    el débito automático se habría activado en Mercado Pago y el panel nunca
    se habría enterado.
    """
    return ident.isalnum() and 8 <= len(ident) <= 64


# Qué hacer con cada tipo de aviso de la cuenta de Turnos360, y cómo se ve un
# id válido para ese tipo.
#
# Es un dict y no una cadena de `if` a propósito: el tipo se compara por
# IGUALDAD contra las claves. Con `in`/`startswith`, `subscription_authorized_
# payment` cae en la rama de "payment" —ya pasó— y el cobro del mes se busca
# en el endpoint equivocado.
#
# El validador va acá y no adentro del handler porque es lo que frena el
# tráfico saliente: un id inventado distinto en cada request se saltearía la
# idempotencia y dispararía una llamada a la API de MP por cada uno.
#
# `subscription_preapproval_plan` no está: son avisos sobre PLANES guardados
# en la cuenta de Mercado Pago, y acá las suscripciones se crean sin plan
# asociado (ver services/mp_debito.py). Si algún día llega uno, se ignora.
_TIPOS_DE_AVISO = {
    "payment": (_es_id_numerico, lambda db, ident: mp_sus.acreditar(db, ident)),
    "subscription_authorized_payment": (
        _es_id_numerico,
        lambda db, ident: mp_debito.acreditar_cobro(db, ident),
    ),
    "subscription_preapproval": (
        _es_id_de_suscripcion,
        lambda db, ident: mp_debito.sincronizar(db, ident),
    ),
}


@router.get("/marca")
@limiter.limit("120/minute")
def marca_publica(request: Request, db: DB) -> dict:
    """El logo de Turnos360, para la landing y el panel.

    Público y sin login a propósito: es el logo de la marca, lo ve cualquiera
    que abra la página. No expone nada más que eso.

    Devuelve `{"logo_url": null}` cuando no hay override, que es el caso
    normal — y el frontend ya está mostrando el archivo del repo, así que un
    null no cambia nada en pantalla.
    """
    from app.services import marca

    return {"logo_url": marca.logo_url(db)}


@router.post("/mp/webhook-suscripcion")
@limiter.limit("120/minute")
async def mp_webhook_suscripcion(request: Request, db: DB) -> dict:
    """Notificaciones de Mercado Pago de las CUOTAS del SaaS.

    Este webhook es de la cuenta de Turnos360, no de la de un negocio, y por
    eso no lleva slug: la cuenta es una sola para todos. La empresa a la que
    corresponde el pago sale del external_reference ("sus:<empresa_id>"), que
    puso la propia preferencia al crearse.

    POR ESTA MISMA PUERTA ENTRAN TRES COSAS DISTINTAS
    ─────────────────────────────────────────────────
    Mercado Pago avisa el tipo en `type` (o `topic`), y hay que despacharlo
    por el valor EXACTO:

      · `payment`                        → un pago suelto (link o checkout).
      · `subscription_authorized_payment`→ el cobro mensual de un débito
                                           automático. El id NO es un pago:
                                           es la "factura" del mes.
      · `subscription_preapproval`       → cambió el estado de una suscripción
                                           (el dueño puso la tarjeta, la
                                           canceló, o MP la dio de baja).

    El filtro era `if "payment" not in tipo`, y eso es una trampa que se
    activó sola al agregar el débito automático: `subscription_authorized_
    payment` CONTIENE la palabra "payment", así que pasaba el filtro y se lo
    trataba como un pago suelto. El id de una factura mensual buscado en
    /v1/payments no existe: la consulta volvía 404, la función devolvía None
    sin quejarse, y el cobro del mes no se acreditaba nunca. Todo en silencio.

    Igual que el de las señas: a Mercado Pago SIEMPRE se le contesta 200, o
    reintenta la misma notificación para siempre.
    """
    if not mp_sus.esta_activo():
        # Sin token configurado no hay nada que acreditar, y sobre todo no hay
        # con qué verificar el pago contra la API. Se responde ok igual para
        # no dejar a MP reintentando contra una instalación que no lo usa.
        return {"ok": True}

    params = request.query_params
    tipo = params.get("type") or params.get("topic") or ""
    recurso_id = params.get("data.id") or params.get("id")
    if not recurso_id:
        try:
            body = await request.json()
            tipo = body.get("type", tipo) or body.get("topic", tipo)
            recurso_id = (body.get("data") or {}).get("id")
        except Exception:
            recurso_id = None

    tipo = str(tipo or "").strip()
    if not recurso_id or tipo not in _TIPOS_DE_AVISO:
        return {"ok": True}

    # Mismo blindaje que el webhook de señas: un id con forma rara muere acá,
    # sin tocar la red ni la base. La forma válida depende del tipo: los pagos
    # y los cobros mensuales son números, los preapproval son hexadecimal.
    valida, manejar = _TIPOS_DE_AVISO[tipo]
    recurso_id = str(recurso_id)
    if not valida(recurso_id):
        return {"ok": True}

    # Ojo: el secreto es el de LA CUENTA DE TURNOS360, distinto del de las
    # señas. El modo de rollout (off/log/enforce) sí se comparte.
    if not firma_mp.acepta(request, recurso_id, settings.mp_saas_webhook_secret):
        return {"ok": True}

    await to_thread.run_sync(manejar, db, recurso_id)
    return {"ok": True}


@router.post("/mp/webhook/{slug}")
@limiter.limit("120/minute")
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

    # El corte de idempotencia de más abajo solo frena IDs que YA vimos. Con
    # IDs inventados distintos, cada request se lo saltaba y disparaba una
    # llamada saliente a la API de MP: un amplificador gratis para tumbar el
    # backend. Los payment_id de MP son enteros; lo que no lo sea muere acá,
    # sin tocar la red ni la base.
    payment_id = str(payment_id)
    if not payment_id.isdigit() or len(payment_id) > 24:
        return {"ok": True}

    # La firma de MP. Con MP_FIRMA_MODO=off (default) esto devuelve True
    # siempre y el comportamiento es idéntico al de antes. Ver
    # app/core/firma_mp.py: el rollout va off -> log -> enforce.
    if not firma_mp.acepta(request, payment_id):
        return {"ok": True}

    # Todo lo que sigue es sincrónico (base + llamada a MP) y va al
    # threadpool en UNA sola pasada. Antes las consultas a la base corrían
    # en el event loop y frenaban a todos los demás usuarios mientras
    # Postgres respondía.
    await to_thread.run_sync(_procesar_notificacion_mp, db, slug, payment_id)
    return {"ok": True}


def _procesar_notificacion_mp(db, slug: str, payment_id: str) -> None:
    """Valida el pago contra MP y lo registra. Corre fuera del event loop.

    Nunca levanta: el webhook siempre tiene que responder 200 o MP reintenta
    para siempre.
    """
    try:
        empresa = svc.resolver_empresa(db, slug)
    except HTTPException:
        return

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
        return

    token = mp.token_de(empresa)
    if not token:
        return

    pago = mp.consultar_pago(token, str(payment_id))
    if not pago or pago.get("status") != "approved":
        return

    ref = pago.get("external_reference")
    turno = db.get(Turno, int(ref)) if ref and str(ref).isdigit() else None
    if turno is None or turno.empresa_id != empresa.id:
        return

    # El pago puede llegar sobre un turno que ya no está en pie: el cliente
    # lo canceló, el negocio lo canceló, o venció el plazo de la seña y el
    # horario se soltó. La plata ENTRÓ igual —está en la cuenta de Mercado
    # Pago del negocio— así que se registra: esconderla haría que el arqueo
    # del día diera diferencia y nada explicara por qué.
    #
    # Lo que NO se hace es revivir el turno en silencio. El horario puede
    # estar vendido a otra persona, y confirmarlo sería crear la silla doble
    # por la puerta de atrás. Queda anotado en el turno y en el log para que
    # el negocio lo vea y decida: devolver o reprogramar.
    if turno.estado not in (EstadoTurno.PENDIENTE, EstadoTurno.CONFIRMADO):
        log.warning(
            "pago de Mercado Pago sobre un turno que ya no está vigente",
            extra={
                "turno_id": turno.id,
                "estado": turno.estado.value,
                "payment_id": str(pago.get("id", payment_id)),
            },
        )
        turno.motivo_cancelacion = (
            (turno.motivo_cancelacion or "")
            + " · OJO: después de esto entró el pago de la seña. Revisá si"
            " corresponde devolverlo o reprogramar."
        )[:300]

    turno.sena_estado = "pagada"
    turno.mp_payment_id = str(pago.get("id", payment_id))
    if turno.estado == EstadoTurno.PENDIENTE:
        # Pagó la seña => el turno se confirma solo (transición válida).
        turno.estado = EstadoTurno.CONFIRMADO

    # La seña ENTRA a la caja y a las estadísticas. Antes solo se marcaba el
    # turno como señado: la plata estaba de verdad en la cuenta de Mercado
    # Pago del negocio, pero para el sistema no existía. El arqueo del día
    # daba diferencia y nada explicaba por qué.
    #
    # Se usa el monto que MP confirmó como aprobado, no el que la empresa
    # tenía configurado: si alguien cambió el monto de la seña entre la
    # reserva y el pago, lo que vale es lo que entró.
    monto_pagado = float(
        pago.get("transaction_amount") or turno.sena_monto or 0
    )
    svc_fin.registrar_sena_cobrada(
        db, turno, monto_pagado, mp_payment_id=str(pago.get("id", payment_id))
    )
    db.commit()


@router.get("/rubros", response_model=list[RubroPublicoOut])
@limiter.limit("30/minute")
def rubros_publicos(request: Request, db: DB) -> list[RubroPublicoOut]:
    """Los rubros para elegir en el formulario de registro."""
    from app.models import Rubro

    filas = db.scalars(select(Rubro).order_by(Rubro.nombre)).all()
    return [RubroPublicoOut(codigo=r.codigo, nombre=r.nombre) for r in filas]


@router.post(
    "/registro", response_model=RegistroOut, status_code=status.HTTP_201_CREATED
)
@limiter.limit("3/hour")
def registro(request: Request, datos: RegistroIn, db: DB) -> RegistroOut:
    """Alta de un negocio desde la landing, sin intervención humana.

    Devuelve los tokens ya emitidos: quien se registra entra derecho al panel,
    sin tener que loguearse de nuevo ni esperar el email. Lo que SÍ espera al
    email es la vidriera pública, que es el candado anti-spam (ver
    services/registro.py).

    3 registros por hora y por IP. Un negocio real se da de alta una vez; el
    que necesita más de tres por hora no es un negocio real.
    """
    if not settings.registro_publico_abierto:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El registro está cerrado por el momento. Escribinos y te damos "
            "de alta nosotros.",
        )

    empresa, dueno, token = svc_registro.registrar(db, datos)

    # encolar() y no .delay(): sin un worker escuchando, el mensaje se quedaba
    # en la cola y el alta terminaba «bien» con un email que no salía nunca.
    # Sin ese email la vidriera del negocio no se enciende: es el paso que
    # separa a alguien que se registró de alguien que puede empezar a vender.
    from app.core.cola import Resultado, encolar
    from app.tasks.emails import enviar_verificacion_email

    if encolar(enviar_verificacion_email, dueno.id, token) is Resultado.FALLO:
        # El alta ya está hecha y el usuario está adentro: no se le puede
        # devolver un error por esto. Pero tiene que quedar en los logs,
        # porque sin el email su vidriera no se enciende nunca y va a
        # escribir preguntando por qué. Desde el panel puede pedir el reenvío.
        log.error("No se pudo mandar el email de verificación (usuario %s)", dueno.id)

    tv = int(dueno.token_version or 0)
    return RegistroOut(
        access_token=crear_access_token(dueno.id, dueno.empresa_id, dueno.rol.value, tv),
        refresh_token=crear_refresh_token(dueno.id, dueno.empresa_id, dueno.rol.value, tv),
        empresa_slug=empresa.slug,
        empresa_nombre=empresa.nombre,
        email_verificado=False,
    )


@router.post("/verificar-email")
@limiter.limit("10/minute")
def verificar_email(request: Request, token: str, db: DB) -> dict:
    """Confirma el email con el token del link. Sirve una sola vez."""
    usuario = svc_registro.verificar(db, token)
    return {
        "ok": True,
        "detalle": (
            f"Listo, {usuario.nombre}. Tu email quedó verificado y tu página "
            "pública ya está online."
        ),
    }


@router.get("/slugs", response_model=list[str])
@limiter.limit("20/minute")
def slugs(request: Request, db: DB) -> list[str]:
    """Slugs de las empresas activas (para el sitemap).

    OJO: registrado ANTES de /{slug} para que "slugs" no se tome como empresa.
    """
    return svc.slugs_activos(db)


@router.get("/{slug}", response_model=VidrieraOut)
@limiter.limit("60/minute")
def vidriera(
    request: Request,
    slug: str,
    db: DB,
    sucursal_id: int | None = Query(
        default=None, description="Local elegido: acota servicios, equipo y precios"
    ),
) -> VidrieraOut:
    """Datos de la página del negocio: info + servicios + equipo.

    Era el único endpoint público que quedaba sin límite, y es el más golpeado:
    tres consultas por llamada. 60/min por IP no molesta a nadie navegando la
    vidriera (se pide una vez al abrir) y corta el polleo automatizado.
    """
    datos = svc.vidriera(db, slug, sucursal_id)

    # Contar la visita va DESPUÉS de armar la respuesta y nunca puede tumbarla:
    # `registrar` se traga cualquier error. Romper la página que ve el cliente
    # del negocio —la que usa para reservar— por una estadística sería el peor
    # intercambio posible.
    #
    # Solo cuenta la apertura de la página, no los pedidos de horarios ni el
    # resto del wizard: si contara todo, un cliente indeciso que mira cinco
    # días valdría lo mismo que cinco personas distintas.
    visitas.registrar_por_slug(db, slug)

    return datos


@router.get("/{slug}/horarios", response_model=list[HuecosDia])
@limiter.limit("30/minute")
def horarios(
    request: Request,
    slug: str,
    db: DB,
    servicio_id: int = Query(...),
    recurso_id: int | None = Query(default=None),
    sucursal_id: int | None = Query(
        default=None, description="Local elegido. Obligatorio si el negocio tiene varios."
    ),
    desde: dt.date | None = Query(default=None),
    dias: int = Query(default=14, ge=1, le=31),
) -> list[HuecosDia]:
    """Horarios de inicio libres por día. recurso_id vacío = cualquiera.

    CON rate limit y tope de 31 días: es el endpoint más caro del sistema y no
    pide login. Cada día consultado recorre a todos los profesionales que hacen
    el servicio, así que un pedido de 60 días con varios barberos disparaba
    cientos de consultas SQL — repetirlo en bucle bastaba para voltear la base
    sin necesidad de ninguna credencial.
    """
    # hoy_de_pared y no date.today(): a las 21:30 de Argentina el servidor
    # (UTC) ya está en el día siguiente, y la vidriera arrancaba mostrando
    # mañana sin que nadie se lo pidiera.
    return svc.huecos(
        db, slug, servicio_id, recurso_id, desde or hoy_de_pared(), dias, sucursal_id
    )


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
