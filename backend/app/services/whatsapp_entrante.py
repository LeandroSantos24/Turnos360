"""Lo que llega DESDE el cliente por WhatsApp.

Qué resuelve
------------
Hasta acá el recordatorio era un aviso de una sola dirección: salía, y si el
cliente contestaba "no puedo ir", eso caía en un teléfono que nadie mira o en
un canal que el sistema no escucha. El horario quedaba ocupado igual y el
negocio se comía el ausente.

Con los botones del recordatorio el cliente toca "No puedo ir", esto lo recibe,
**cancela el turno y libera el horario solo**. Nadie leyó nada, nadie escribió
nada, y esa silla se puede vender de nuevo.

Las tres defensas, porque este es un endpoint público
-----------------------------------------------------
1. La firma HMAC del webhook (eso lo hace el router, antes de llegar acá).
2. El payload del botón lo generamos NOSOTROS al mandar el mensaje, con el id
   del turno adentro. No se adivina de afuera.
3. **El teléfono que contesta tiene que ser el del cliente de ese turno.** Sin
   esto, cualquiera con un payload válido podría cancelarle el turno a otro.
   Esta es la que de verdad importa: las dos primeras se pueden filtrar, esta
   ata la acción a la persona.

Y la cuarta, que no es seguridad sino sanidad: Meta reintenta los webhooks.
Cada mensaje entrante trae su propio id; si ya lo procesamos, se ignora.
"""

import logging
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.telefono import TelefonoInvalido, normalizar_ar
from app.models.cliente import Cliente
from app.models.enums import CanalMensaje, DireccionMensaje, EstadoMensaje, EstadoTurno
from app.models.mensajeria import Mensaje
from app.models.organizacion import Empresa
from app.models.turno import Turno
from app.schemas.turno import TurnoCambiarEstado
from app.services import whatsapp as wa

log = logging.getLogger("turnos360.whatsapp")

# Lo que escribe alguien que no quiere más mensajes. Se compara en minúsculas
# y sin acentos ni signos, porque nadie escribe "BAJA" prolijo: escribe
# "baja.", "Baja!", "dar de baja".
PALABRAS_BAJA = ("baja", "stop", "cancelar suscripcion", "no molestar", "unsubscribe")

MOTIVO_CANCELA = "El cliente avisó por WhatsApp que no puede venir"


def _texto_normalizado(texto: str) -> str:
    limpio = (texto or "").strip().lower()
    limpio = re.sub(r"[^\w\s]", "", limpio)
    return re.sub(r"\s+", " ", limpio).strip()


def es_pedido_de_baja(texto: str) -> bool:
    limpio = _texto_normalizado(texto)
    return any(limpio == p or limpio.startswith(p + " ") for p in PALABRAS_BAJA)


def _ya_procesado(db: Session, wamid: str | None) -> bool:
    if not wamid:
        return False
    return db.scalar(select(Mensaje.id).where(Mensaje.externo_id == wamid).limit(1)) is not None


def _empresa_por_numero(db: Session, phone_number_id: str | None) -> Empresa | None:
    """De qué negocio es el número al que le escribieron.

    `wa_phone_number_id` se guarda en claro (no es un secreto: el secreto es el
    token, que va cifrado al lado) justamente para poder hacer esta búsqueda
    con un índice en vez de desencriptar las credenciales de todas las
    empresas en cada mensaje que entra.
    """
    if not phone_number_id:
        return None
    return db.scalars(
        select(Empresa).where(Empresa.wa_phone_number_id == phone_number_id)
    ).first()


def _mismo_telefono(cliente: Cliente, wa_id: str) -> bool:
    try:
        return normalizar_ar(cliente.telefono) == wa_id
    except TelefonoInvalido:
        return False


def _registrar_entrante(
    db: Session,
    empresa: Empresa,
    cliente: Cliente | None,
    wamid: str | None,
    texto: str | None,
    turno_id: int | None = None,
) -> Mensaje:
    mensaje = Mensaje(
        empresa_id=empresa.id,
        cliente_id=cliente.id if cliente else None,
        turno_id=turno_id,
        canal=CanalMensaje.WHATSAPP,
        direccion=DireccionMensaje.ENTRANTE,
        # Regla 5: en salud no se guarda el texto de lo que escribe un
        # paciente. "me duele desde el martes" es una consulta clínica.
        contenido=None if wa.es_sensible(empresa) else texto,
        estado=EstadoMensaje.ENTREGADO,
        externo_id=wamid,
    )
    db.add(mensaje)
    db.flush()
    return mensaje


# ══════════════════════════════════════════════════════════════════════════
#  Los botones
# ══════════════════════════════════════════════════════════════════════════


def _accion_sobre_turno(db: Session, turno: Turno, accion: str) -> str | None:
    """Aplica confirmar/cancelar reusando el service de turnos.

    Se llama a `turno.cambiar_estado` y no se toca `turno.estado` a mano para
    que valgan las mismas reglas de transición que en el panel: no se cancela
    un turno ya finalizado, no se confirma uno ausente. Si la transición no es
    válida el service tira 409 y acá se traduce en "no hago nada", que es lo
    correcto: el cliente tocó un botón de un mensaje viejo.
    """
    from app.services import turno as svc_turno

    nuevo = EstadoTurno.CONFIRMADO if accion == "confirmar" else EstadoTurno.CANCELADO
    if turno.estado == nuevo:
        return None  # ya estaba: el webhook vino repetido o tocó dos veces

    datos = TurnoCambiarEstado(
        estado=nuevo,
        motivo_cancelacion=MOTIVO_CANCELA if nuevo == EstadoTurno.CANCELADO else None,
    )
    try:
        svc_turno.cambiar_estado(db, turno.empresa_id, turno.id, datos)
    except HTTPException as e:
        log.info(
            "botón de WhatsApp sobre un turno que ya no lo admite",
            extra={"turno_id": turno.id, "accion": accion, "detalle": e.detail},
        )
        return None
    return accion


def _respuesta(accion: str, nombre: str) -> str:
    if accion == "confirmar":
        return f"¡Genial {nombre}! Quedó confirmado. Te esperamos."
    return (
        f"Listo {nombre}, cancelamos tu turno y liberamos el horario. "
        "Cuando quieras sacás otro."
    )


def procesar_boton(db: Session, payload: str, wa_id: str, wamid: str | None) -> str | None:
    """Un botón del recordatorio. Devuelve la acción aplicada, o None."""
    datos = wa.leer_payload(payload)
    if datos is None:
        return None
    turno_id, accion = datos

    turno = db.get(Turno, turno_id)
    if turno is None:
        return None
    cliente = db.get(Cliente, turno.cliente_id)
    empresa = db.get(Empresa, turno.empresa_id)
    if cliente is None or empresa is None:
        return None

    # LA defensa: el que toca el botón tiene que ser el dueño del turno.
    if not _mismo_telefono(cliente, wa_id):
        log.warning(
            "botón de WhatsApp desde un teléfono que no es el del turno",
            extra={"turno_id": turno.id, "empresa_id": empresa.id},
        )
        return None

    _registrar_entrante(db, empresa, cliente, wamid, f"[botón] {accion}", turno_id=turno.id)
    aplicada = _accion_sobre_turno(db, turno, accion)
    db.commit()

    if aplicada:
        wa.responder_texto(db, empresa, cliente, _respuesta(aplicada, cliente.nombre))
    return aplicada


# ══════════════════════════════════════════════════════════════════════════
#  El texto libre
# ══════════════════════════════════════════════════════════════════════════


def procesar_texto(
    db: Session,
    empresa: Empresa | None,
    wa_id: str,
    texto: str,
    wamid: str | None,
) -> str | None:
    """Un mensaje escrito. Hoy solo actúa sobre la baja; el resto se registra.

    Deliberadamente NO se contesta nada automático a un mensaje cualquiera. El
    dueño ve la conversación en su propio WhatsApp (es su número) y contesta
    él. Un bot que responde por el negocio sin que el negocio lo pida es la
    forma más rápida de que un cliente se sienta atendido por una máquina.
    """
    if empresa is None:
        # No sabemos de qué negocio es: sin phone_number_id no hay forma de
        # atribuirlo. No se guarda nada — en coexistencia por acá pasan también
        # las conversaciones privadas del dueño con su proveedor de toallas.
        return None

    cliente = None
    for c in db.scalars(
        select(Cliente).where(Cliente.empresa_id == empresa.id, Cliente.telefono.isnot(None))
    ):
        if _mismo_telefono(c, wa_id):
            cliente = c
            break

    if cliente is None:
        # Alguien que no es cliente del negocio. Se cuenta, no se guarda.
        return None

    _registrar_entrante(db, empresa, cliente, wamid, texto)

    if es_pedido_de_baja(texto):
        cliente.acepta_whatsapp = False
        db.commit()
        wa.responder_texto(
            db,
            empresa,
            cliente,
            "Listo, no te mandamos más recordatorios por acá. "
            "Si querés volver a recibirlos, avisale al negocio.",
        )
        return "baja"

    db.commit()
    return "registrado"


# ══════════════════════════════════════════════════════════════════════════
#  La entrada
# ══════════════════════════════════════════════════════════════════════════


def procesar(db: Session, valor: dict) -> int:
    """Procesa el bloque `value` de un webhook. Devuelve cuántos mensajes actuó."""
    mensajes = valor.get("messages") or []
    if not mensajes:
        return 0

    phone_number_id = (valor.get("metadata") or {}).get("phone_number_id")
    empresa = _empresa_por_numero(db, phone_number_id)
    actuados = 0

    for msg in mensajes:
        wamid = msg.get("id")
        wa_id = (msg.get("from") or "").strip()
        if not wa_id:
            continue
        if _ya_procesado(db, wamid):
            continue  # Meta reintenta: esto ya lo hicimos

        tipo = msg.get("type")
        resultado = None

        if tipo == "button":
            payload = (msg.get("button") or {}).get("payload")
            if payload:
                resultado = procesar_boton(db, payload, wa_id, wamid)
        elif tipo == "interactive":
            respuesta = (msg.get("interactive") or {}).get("button_reply") or {}
            if respuesta.get("id"):
                resultado = procesar_boton(db, respuesta["id"], wa_id, wamid)
        elif tipo == "text":
            cuerpo = (msg.get("text") or {}).get("body") or ""
            resultado = procesar_texto(db, empresa, wa_id, cuerpo, wamid)

        if resultado:
            actuados += 1

    return actuados
