"""WhatsApp: lo que ve el dueño, lo que carga el super-admin, y el webhook.

Tres routers en un archivo porque son tres puertas del mismo tema:

  /whatsapp        el dueño de un negocio  (gate_dueno)
  /admin/whatsapp  el super-admin: carga packs y credenciales
  /publico/whatsapp/webhook   Meta, sin token nuestro, con firma HMAC
"""

import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.deps import DB, EmpresaActual, SuperAdminActual, UsuarioActual, gate_dueno
from app.core.config import settings
from app.core.crypto import encriptar_credenciales
from app.core.rate_limit import limiter
from app.core.telefono import TelefonoInvalido, es_valido_ar, normalizar_ar
from app.models.cliente import Cliente
from app.models.enums import CanalMensaje, EstadoMensaje
from app.models.mensajeria import Mensaje, PlantillaMensaje
from app.models.organizacion import Empresa
from app.schemas.whatsapp import (
    AcreditarIn,
    CredencialesIn,
    EstadoWhatsappOut,
    MensajeOut,
    MovimientoOut,
    PruebaIn,
    PruebaOut,
)
from app.services import creditos_wa
from app.services import whatsapp as svc

log = logging.getLogger("turnos360.whatsapp")

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"], dependencies=[Depends(gate_dueno)])
router_admin = APIRouter(prefix="/admin/whatsapp", tags=["admin"])
router_webhook = APIRouter(prefix="/publico/whatsapp", tags=["publico"])


# ══════════════════════════════════════════════════════════════════════════
#  El dueño
# ══════════════════════════════════════════════════════════════════════════


@router.get("/estado", response_model=EstadoWhatsappOut)
def estado(empresa_id: EmpresaActual, db: DB) -> EstadoWhatsappOut:
    """Todo lo que necesita la pantalla de WhatsApp, en un pedido."""
    empresa = db.get(Empresa, empresa_id)
    cred = svc.credenciales_de(empresa) or {}
    resumen = creditos_wa.resumen(db, empresa_id)

    plantillas = db.scalars(
        select(PlantillaMensaje).where(
            PlantillaMensaje.empresa_id == empresa_id,
            PlantillaMensaje.canal == CanalMensaje.WHATSAPP,
            PlantillaMensaje.activa.is_(True),
        )
    ).all()

    telefonos = db.scalars(
        select(Cliente.telefono).where(
            Cliente.empresa_id == empresa_id,
            Cliente.activo.is_(True),
        )
    ).all()
    sin_valido = sum(1 for t in telefonos if not es_valido_ar(t))

    return EstadoWhatsappOut(
        proveedor=svc.proveedor_de(empresa).nombre,
        conectado=bool(cred.get("token") and cred.get("phone_number_id")),
        numero=cred.get("numero"),
        disponible=resumen["disponible"],
        consumidos=resumen["consumidos"],
        precio_mensaje_ars=resumen["precio_mensaje_ars"],
        packs=resumen["packs"],
        plantillas_activas=len(plantillas),
        clientes_sin_telefono_valido=sin_valido,
    )


@router.get("/mensajes", response_model=list[MensajeOut])
def mensajes(empresa_id: EmpresaActual, db: DB, limite: int = 50) -> list[MensajeOut]:
    """Los últimos envíos, para poder responder «¿le llegó o no?»."""
    filas = db.execute(
        select(Mensaje, Cliente, PlantillaMensaje)
        .join(Cliente, Cliente.id == Mensaje.cliente_id, isouter=True)
        .join(PlantillaMensaje, PlantillaMensaje.id == Mensaje.plantilla_id, isouter=True)
        .where(
            Mensaje.empresa_id == empresa_id,
            Mensaje.canal == CanalMensaje.WHATSAPP,
        )
        .order_by(Mensaje.fecha.desc(), Mensaje.id.desc())
        .limit(min(limite, 200))
    ).all()
    return [
        MensajeOut(
            id=m.id,
            cliente=(f"{c.nombre} {c.apellido or ''}".strip() if c else None),
            telefono=(c.telefono if c else None),
            plantilla=(p.codigo if p else None),
            estado=m.estado.value,
            error=m.error,
            fecha=m.fecha,
        )
        for m, c, p in filas
    ]


@router.get("/movimientos", response_model=list[MovimientoOut])
def movimientos(empresa_id: EmpresaActual, db: DB, limite: int = 50) -> list[MovimientoOut]:
    """El libro de créditos: cada carga y cada consumo, con fecha."""
    return [
        MovimientoOut.model_validate(m)
        for m in creditos_wa.movimientos(db, empresa_id, min(limite, 200))
    ]


@router.post("/prueba", response_model=PruebaOut)
@limiter.limit("10/hour")
def prueba(
    request: Request,
    datos: PruebaIn,
    empresa_id: EmpresaActual,
    usuario: UsuarioActual,
    db: DB,
) -> PruebaOut:
    """Diagnóstico: valida un número y muestra el mensaje que saldría.

    NO consume crédito y NO deja fila en `mensaje`. Es a propósito: sirve para
    probar veinte veces un número que no estás seguro de cómo se escribe, sin
    que eso le cueste plata al negocio ni le ensucie el historial.
    """
    empresa = db.get(Empresa, empresa_id)
    try:
        destino = normalizar_ar(datos.telefono)
    except TelefonoInvalido as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e

    plantilla = svc.buscar_plantilla(db, empresa_id, "recordatorio_24h")
    if plantilla is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Todavía no hay una plantilla de recordatorio cargada para WhatsApp.",
        )

    variables = [
        "Juan",
        svc.servicio_para_mensaje(empresa, "Corte de pelo"),
        empresa.nombre,
        "mañana a las 15:00",
    ]
    texto = svc.render(plantilla.cuerpo, variables)
    proveedor = svc.proveedor_de(empresa)

    return PruebaOut(
        enviado=False,
        proveedor=proveedor.nombre,
        destino=destino,
        texto=texto,
        detalle=(
            "Modo simulado: no sale nada a la calle. El número quedó bien "
            "interpretado y este es el texto exacto que se mandaría."
            if proveedor.nombre == "simulado"
            else "Conectado a Meta. Este es el texto que se manda; la prueba no lo envía."
        ),
    )


# ══════════════════════════════════════════════════════════════════════════
#  El super-admin: cargar packs y credenciales
# ══════════════════════════════════════════════════════════════════════════


@router_admin.post("/empresas/{empresa_id}/creditos")
def cargar_creditos(
    empresa_id: int,
    datos: AcreditarIn,
    admin: SuperAdminActual,
    db: DB,
) -> dict:
    """Acredita mensajes a una empresa. Esto se corre cuando el negocio pagó.

    El `precio_ars` que se guarda es lo que efectivamente pagó, no el precio de
    lista: el precio de lista se mueve con el dólar y sin este dato no se puede
    reconstruir la facturación de un mes ya cerrado.
    """
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa empresa.")
    if datos.cantidad <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La cantidad tiene que ser positiva.")

    saldo = creditos_wa.acreditar(
        db,
        empresa_id,
        datos.cantidad,
        motivo=datos.motivo,
        precio_ars=datos.precio_ars,
        detalle=datos.detalle or f"cargado por {admin.email}",
    )
    db.commit()
    return {"empresa": empresa.nombre, "acreditados": datos.cantidad, "disponible": saldo}


@router_admin.put("/empresas/{empresa_id}/credenciales")
def guardar_credenciales(
    empresa_id: int,
    datos: CredencialesIn,
    admin: SuperAdminActual,
    db: DB,
) -> dict:
    """Guarda el token de Meta de una empresa, encriptado (Regla 7).

    El token NO vuelve nunca en ninguna respuesta. Si alguien lo pierde, se
    genera uno nuevo en Meta; no se recupera desde acá.
    """
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa empresa.")

    empresa.wa_credenciales = encriptar_credenciales(
        {
            "token": datos.token,
            "phone_number_id": datos.phone_number_id,
            "numero": datos.numero,
            "waba_id": datos.waba_id,
            "version": settings.wa_api_version,
        }
    )
    db.commit()
    return {"empresa": empresa.nombre, "conectado": True, "numero": datos.numero}


@router_admin.get("/empresas/{empresa_id}")
def ver_empresa(empresa_id: int, admin: SuperAdminActual, db: DB) -> dict:
    empresa = db.get(Empresa, empresa_id)
    if empresa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe esa empresa.")
    cred = svc.credenciales_de(empresa) or {}
    resumen = creditos_wa.resumen(db, empresa_id)
    return {
        "empresa": empresa.nombre,
        "conectado": bool(cred.get("token")),
        "numero": cred.get("numero"),
        "phone_number_id": cred.get("phone_number_id"),
        "disponible": resumen["disponible"],
        "consumidos": resumen["consumidos"],
    }


# ══════════════════════════════════════════════════════════════════════════
#  El webhook de Meta
# ══════════════════════════════════════════════════════════════════════════
#
# Meta pega acá para avisar "entregado" y "leído". Es un endpoint PÚBLICO: no
# hay token nuestro, cualquiera de internet puede golpearlo. Por eso las dos
# defensas:
#
#   GET  -> el challenge de verificación, contra WA_WEBHOOK_VERIFY_TOKEN
#   POST -> firma HMAC-SHA256 del cuerpo crudo con el App Secret
#
# Sin la firma, cualquiera podría marcar como "leídos" mensajes que nunca
# salieron, y las métricas del producto pasarían a ser ficción.


@router_webhook.get("/webhook")
def verificar_webhook(request: Request) -> Response:
    params = request.query_params
    esperado = settings.wa_webhook_verify_token
    if not esperado:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook sin configurar.")
    if params.get("hub.mode") == "subscribe" and hmac.compare_digest(
        params.get("hub.verify_token") or "", esperado
    ):
        return Response(content=params.get("hub.challenge") or "", media_type="text/plain")
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Verificación fallida.")


def firma_valida(cuerpo: bytes, cabecera: str | None) -> bool:
    """HMAC-SHA256 del cuerpo CRUDO con el App Secret."""
    secreto = settings.wa_app_secret
    if not secreto or not cabecera or not cabecera.startswith("sha256="):
        return False
    esperada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    # compare_digest: comparar con == filtra el secreto por tiempo de respuesta.
    return hmac.compare_digest(esperada, cabecera[7:])


_ESTADOS = {
    "sent": EstadoMensaje.ENVIADO,
    "delivered": EstadoMensaje.ENTREGADO,
    "read": EstadoMensaje.LEIDO,
    "failed": EstadoMensaje.FALLIDO,
}

# El estado solo puede AVANZAR. Meta reintenta y reordena: sin esto, un
# "sent" que llega tarde pisa un "read" que ya había llegado.
_ORDEN = {
    EstadoMensaje.PENDIENTE: 0,
    EstadoMensaje.ENVIADO: 1,
    EstadoMensaje.ENTREGADO: 2,
    EstadoMensaje.LEIDO: 3,
    EstadoMensaje.FALLIDO: 4,
}


@router_webhook.post("/webhook")
async def recibir_webhook(request: Request, db: DB) -> dict:
    crudo = await request.body()
    if not firma_valida(crudo, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Firma inválida.")

    try:
        datos = await request.json()
    except Exception:
        return {"ok": True}  # cuerpo raro: no es nuestro problema, no reintentar

    actualizados = 0
    for entrada in datos.get("entry") or []:
        for cambio in entrada.get("changes") or []:
            for estado in (cambio.get("value") or {}).get("statuses") or []:
                nuevo = _ESTADOS.get(estado.get("status"))
                wamid = estado.get("id")
                if not nuevo or not wamid:
                    continue
                mensaje = db.scalars(
                    select(Mensaje).where(Mensaje.externo_id == wamid)
                ).first()
                if mensaje is None:
                    continue
                if _ORDEN[nuevo] <= _ORDEN[mensaje.estado] and nuevo != EstadoMensaje.FALLIDO:
                    continue
                mensaje.estado = nuevo
                if nuevo == EstadoMensaje.FALLIDO:
                    detalle = (estado.get("errors") or [{}])[0]
                    mensaje.error = str(detalle.get("title") or detalle)[:300]
                actualizados += 1
    if actualizados:
        db.commit()
    # Siempre 200: si devolvemos error, Meta reintenta el lote entero durante
    # días y termina desactivando el webhook.
    return {"ok": True, "actualizados": actualizados}
