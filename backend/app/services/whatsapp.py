"""Envío de WhatsApp: proveedores, plantillas y la orquestación de un envío.

Cómo está partido
-----------------
`ProveedorSimulado` y `ProveedorMetaCloud` hacen UNA sola cosa: poner el
mensaje en la red (o fingir que lo hacen). No saben de saldos, ni de clientes,
ni de la base.

`enviar_plantilla()` es el que sabe: valida, descuenta el crédito, registra la
fila en `mensaje`, llama al proveedor y arregla el desastre si falla.

Por qué existe el proveedor simulado
------------------------------------
Es el default. Sin credenciales de Meta —que hoy no tenemos— todo el circuito
corre igual: se descuenta el saldo, se escribe el `mensaje`, se ve el texto
final en el log. Se puede probar el producto entero, con turnos de verdad,
antes de gastar un peso y antes de que Meta apruebe una sola plantilla.

Y cuando lleguen las credenciales, cambia UNA variable de entorno.
"""

import hashlib
import json
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import desencriptar_credenciales
from app.core.telefono import TelefonoInvalido, normalizar_ar
from app.models.cliente import Cliente
from app.models.enums import CanalMensaje, DireccionMensaje, EstadoMensaje
from app.models.mensajeria import Mensaje, PlantillaMensaje
from app.models.organizacion import Empresa
from app.services import creditos_wa

log = logging.getLogger("turnos360.whatsapp")

# Rubros donde el CONTENIDO del turno es dato de salud. En estos, el mensaje
# no nombra el servicio y no se guarda el texto: "Consulta ginecológica" en un
# WhatsApp y en una tabla de logs es exactamente lo que la Regla 5 prohíbe.
RUBROS_SENSIBLES = {"medico", "nutricion", "psicologia", "odontologia", "kinesiologia"}

TIMEOUT = httpx.Timeout(15.0, connect=8.0)


class ErrorProveedor(RuntimeError):
    """Falló el envío del lado del proveedor. El crédito se devuelve."""


class SinPlantilla(RuntimeError):
    """La empresa no tiene esa plantilla cargada o aprobada."""


@dataclass(frozen=True)
class Enviado:
    wamid: str
    proveedor: str


# ══════════════════════════════════════════════════════════════════════════
#  Proveedores
# ══════════════════════════════════════════════════════════════════════════


class ProveedorSimulado:
    """No sale a la red. Registra lo que HABRÍA mandado."""

    nombre = "simulado"

    def enviar(
        self,
        destino: str,
        plantilla: str,
        variables: list[str],
        texto: str,
        botones: list[str] | None = None,
    ) -> Enviado:
        semilla = f"{destino}|{plantilla}|{'|'.join(variables)}"
        wamid = "sim." + hashlib.sha256(semilla.encode()).hexdigest()[:24]
        log.info(
            "whatsapp simulado",
            extra={
                "destino": destino,
                "plantilla": plantilla,
                "wamid": wamid,
                "texto": texto,
                "botones": botones or [],
            },
        )
        return Enviado(wamid=wamid, proveedor=self.nombre)

    def enviar_texto(self, destino: str, texto: str) -> Enviado:
        wamid = "sim." + hashlib.sha256(f"{destino}|{texto}".encode()).hexdigest()[:24]
        log.info(
            "whatsapp simulado (respuesta)",
            extra={"destino": destino, "wamid": wamid, "texto": texto},
        )
        return Enviado(wamid=wamid, proveedor=self.nombre)


class ProveedorMetaCloud:
    """Cloud API de Meta, directo, sin intermediario.

    El token es de la empresa y va encriptado en `empresa.wa_credenciales`.
    Nunca se loguea: si aparece en un log, aparece en cualquier backup de logs.
    """

    nombre = "meta"

    def __init__(self, token: str, phone_number_id: str, version: str = "v21.0"):
        self.token = token
        self.phone_number_id = phone_number_id
        self.version = version

    @property
    def url(self) -> str:
        return f"https://graph.facebook.com/{self.version}/{self.phone_number_id}/messages"

    def enviar(
        self,
        destino: str,
        plantilla: str,
        variables: list[str],
        texto: str,
        botones: list[str] | None = None,
    ) -> Enviado:
        componentes: list[dict] = []
        if variables:
            componentes.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": v} for v in variables],
                }
            )
        # Los botones EXISTEN en la plantilla aprobada en Meta; lo que se manda
        # acá es el payload de cada uno, que es lo que vuelve por el webhook
        # cuando el cliente lo toca. Por eso podemos meterle el id del turno.
        for i, payload in enumerate(botones or []):
            componentes.append(
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": str(i),
                    "parameters": [{"type": "payload", "payload": payload}],
                }
            )

        cuerpo = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": destino,
            "type": "template",
            "template": {
                "name": plantilla,
                "language": {"code": settings.wa_idioma_plantillas},
            },
        }
        if componentes:
            cuerpo["template"]["components"] = componentes

        try:
            with httpx.Client(timeout=TIMEOUT) as cli:
                r = cli.post(
                    self.url,
                    headers={"Authorization": f"Bearer {self.token}"},
                    json=cuerpo,
                )
        except httpx.HTTPError as e:
            raise ErrorProveedor(f"No pude hablar con Meta: {e}") from e

        if r.status_code >= 400:
            # El cuerpo de error de Meta trae el motivo real (plantilla no
            # aprobada, número inválido, cuenta sin saldo). Se recorta porque
            # va a una columna de 300 y porque puede venir enorme.
            raise ErrorProveedor(f"Meta respondió {r.status_code}: {r.text[:400]}")

        datos = r.json()
        try:
            wamid = datos["messages"][0]["id"]
        except (KeyError, IndexError, TypeError):
            raise ErrorProveedor(f"Respuesta inesperada de Meta: {json.dumps(datos)[:300]}") from None
        return Enviado(wamid=wamid, proveedor=self.nombre)

    def enviar_texto(self, destino: str, texto: str) -> Enviado:
        """Mensaje libre. SOLO vale dentro de la ventana de 24 h de servicio.

        Se usa para contestarle a alguien que acaba de tocar un botón, que es
        justo cuando la ventana está abierta. Fuera de la ventana Meta lo
        rechaza, y está bien que lo haga: mandar texto libre a alguien que no
        te escribió es exactamente lo que la ventana existe para impedir.
        """
        cuerpo = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": destino,
            "type": "text",
            "text": {"body": texto},
        }
        try:
            with httpx.Client(timeout=TIMEOUT) as cli:
                r = cli.post(
                    self.url,
                    headers={"Authorization": f"Bearer {self.token}"},
                    json=cuerpo,
                )
        except httpx.HTTPError as e:
            raise ErrorProveedor(f"No pude hablar con Meta: {e}") from e
        if r.status_code >= 400:
            raise ErrorProveedor(f"Meta respondió {r.status_code}: {r.text[:400]}")
        try:
            wamid = r.json()["messages"][0]["id"]
        except (KeyError, IndexError, TypeError):
            raise ErrorProveedor("Respuesta inesperada de Meta al contestar") from None
        return Enviado(wamid=wamid, proveedor=self.nombre)


def credenciales_de(empresa: Empresa) -> dict | None:
    """Credenciales de WhatsApp de la empresa, o None si no tiene."""
    if not empresa.wa_credenciales:
        return None
    try:
        return desencriptar_credenciales(empresa.wa_credenciales)
    except Exception:
        # Clave Fernet rotada, blob corrupto. No podemos mandar, pero tampoco
        # queremos voltear el proceso entero de recordatorios por una empresa.
        log.exception("no pude desencriptar las credenciales de WhatsApp",
                      extra={"empresa_id": empresa.id})
        return None


def proveedor_de(empresa: Empresa):
    """Elige el proveedor de esta empresa.

    Meta solo si la empresa TIENE credenciales completas y el modo global no
    es "simulado". El modo global es el freno de mano: con
    WA_PROVEEDOR=simulado no sale un mensaje a la calle aunque todas las
    empresas tengan sus tokens cargados.
    """
    if settings.wa_proveedor == "simulado":
        return ProveedorSimulado()
    cred = credenciales_de(empresa)
    if not cred or not cred.get("token") or not cred.get("phone_number_id"):
        return ProveedorSimulado()
    return ProveedorMetaCloud(
        token=cred["token"],
        phone_number_id=cred["phone_number_id"],
        version=cred.get("version") or settings.wa_api_version,
    )


def esta_activo(db: Session, empresa: Empresa) -> bool:
    """¿Esta empresa manda WhatsApp hoy? Saldo + al menos una plantilla activa."""
    if creditos_wa.saldo_de(db, empresa.id) < 1:
        return False
    return db.scalar(
        select(PlantillaMensaje.id)
        .where(
            PlantillaMensaje.empresa_id == empresa.id,
            PlantillaMensaje.canal == CanalMensaje.WHATSAPP,
            PlantillaMensaje.activa.is_(True),
        )
        .limit(1)
    ) is not None


# ══════════════════════════════════════════════════════════════════════════
#  Plantillas
# ══════════════════════════════════════════════════════════════════════════


def es_sensible(empresa: Empresa) -> bool:
    rubro = getattr(empresa, "rubro", None)
    return bool(rubro and (rubro.codigo or "").lower() in RUBROS_SENSIBLES)


def servicio_para_mensaje(empresa: Empresa, nombre_servicio: str | None) -> str:
    """El nombre del servicio, o «tu turno» si nombrarlo sería un dato de salud.

    "Recordatorio: mañana tenés Consulta ginecológica" es un diagnóstico
    viajando por WhatsApp, visible en la pantalla de bloqueo del celular. En
    un consultorio el mensaje dice «tu turno» y listo: el paciente sabe a qué
    va, y el que le mira el teléfono no.
    """
    if es_sensible(empresa):
        return "tu turno"
    return nombre_servicio or "tu turno"


def buscar_plantilla(db: Session, empresa_id: int, codigo: str) -> PlantillaMensaje | None:
    return db.scalars(
        select(PlantillaMensaje).where(
            PlantillaMensaje.empresa_id == empresa_id,
            PlantillaMensaje.canal == CanalMensaje.WHATSAPP,
            PlantillaMensaje.codigo == codigo,
            PlantillaMensaje.activa.is_(True),
        )
    ).first()


# ══════════════════════════════════════════════════════════════════════════
#  Los botones del recordatorio
# ══════════════════════════════════════════════════════════════════════════
#
# El orden de esta tupla ES el orden de los botones en la plantilla aprobada
# en Meta: el índice 0 es el primero. Si algún día se reordenan allá, hay que
# reordenar acá o el cliente va a confirmar cuando quiso cancelar.

ACCIONES_BOTON = ("confirmar", "cancelar")

PREFIJO_PAYLOAD = "t360"


def payload_boton(turno_id: int, accion: str) -> str:
    """`t360:481:cancelar` — lo que vuelve por el webhook cuando lo tocan.

    El id del turno viaja adentro del payload en vez de resolverse después por
    teléfono y fecha. Es la diferencia entre "el turno que este número tiene
    más o menos ahora" y "ESTE turno". Con dos turnos el mismo día, lo segundo
    es lo único que no se equivoca.
    """
    return f"{PREFIJO_PAYLOAD}:{turno_id}:{accion}"


def leer_payload(payload: str) -> tuple[int, str] | None:
    """Al revés. None si no es nuestro o si viene deformado."""
    partes = (payload or "").split(":")
    if len(partes) != 3 or partes[0] != PREFIJO_PAYLOAD:
        return None
    if partes[2] not in ACCIONES_BOTON:
        return None
    try:
        return int(partes[1]), partes[2]
    except ValueError:
        return None


def render(cuerpo: str, variables: list[str]) -> str:
    """`{{1}}` → primer variable, como las plantillas de Meta.

    Se usa el mismo formato que Meta a propósito: el texto que ves en el log
    del simulado es exactamente el que va a mandar Meta cuando conectes.
    """
    salida = cuerpo
    for i, valor in enumerate(variables, start=1):
        salida = salida.replace("{{%d}}" % i, valor)
    return salida


# ══════════════════════════════════════════════════════════════════════════
#  El envío
# ══════════════════════════════════════════════════════════════════════════


def enviar_plantilla(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    codigo: str,
    variables: list[str],
    turno_id: int | None = None,
) -> Mensaje | None:
    """Manda una plantilla a un cliente. Devuelve el Mensaje, o None si no se mandó.

    Devuelve None —sin explotar— cuando el motivo es de negocio y el llamador
    tiene que poder seguir con el email: sin plantilla, sin teléfono usable,
    sin consentimiento, sin saldo. Los recordatorios corren en lote y una
    empresa mal configurada no puede frenar a las otras cien.

    El orden importa y no es casual:
      1. validaciones que NO cuestan plata
      2. descontar el crédito
      3. mandar
      4. si falló, devolver el crédito
    """
    plantilla = buscar_plantilla(db, empresa.id, codigo)
    if plantilla is None:
        return None

    if not getattr(cliente, "acepta_whatsapp", False):
        return None

    try:
        destino = normalizar_ar(cliente.telefono)
    except TelefonoInvalido as e:
        # Se registra como fallido SIN consumir crédito: es un dato malo del
        # cliente, no un envío. Así el dueño puede ver la lista de teléfonos
        # que hay que corregir en vez de preguntarse por qué no llegan.
        db.add(
            Mensaje(
                empresa_id=empresa.id,
                cliente_id=cliente.id,
                turno_id=turno_id,
                canal=CanalMensaje.WHATSAPP,
                direccion=DireccionMensaje.SALIENTE,
                plantilla_id=plantilla.id,
                estado=EstadoMensaje.FALLIDO,
                error=str(e)[:300],
            )
        )
        db.commit()
        return None

    proveedor = proveedor_de(empresa)
    texto = render(plantilla.cuerpo, variables)
    # Lo que se puede escribir en un log. En rubros de salud, nada.
    texto_visible = "(oculto: rubro sensible)" if es_sensible(empresa) else texto

    # Los botones solo tienen sentido si hay un turno sobre el cual actuar.
    # Un mensaje sin turno con un botón "No puedo ir" no sabría qué cancelar.
    botones = (
        [payload_boton(turno_id, accion) for accion in ACCIONES_BOTON]
        if plantilla.con_botones and turno_id
        else None
    )

    # Meta exige que la plantilla esté aprobada. Mandar una sin aprobar es un
    # error garantizado que igual consume una llamada; mejor no salir.
    if proveedor.nombre == "meta" and not plantilla.aprobada_meta:
        log.warning(
            "plantilla sin aprobar en Meta, no se manda",
            extra={"empresa_id": empresa.id, "plantilla": codigo},
        )
        return None

    try:
        creditos_wa.consumir(db, empresa.id, detalle=f"{codigo} turno={turno_id or '-'}")
    except creditos_wa.SinSaldo:
        # A propósito NO se hace rollback: lo único pendiente en la sesión es
        # la creación del renglón de saldo en cero, que es idempotente y que
        # queremos conservar. Un rollback acá se llevaría puesto lo que el
        # llamador hubiera hecho antes en la misma transacción.
        return None

    mensaje = Mensaje(
        empresa_id=empresa.id,
        cliente_id=cliente.id,
        turno_id=turno_id,
        canal=CanalMensaje.WHATSAPP,
        direccion=DireccionMensaje.SALIENTE,
        plantilla_id=plantilla.id,
        # Regla 5: en rubros de salud no se guarda el texto, porque el texto
        # nombra el servicio y el servicio es el diagnóstico.
        contenido=None if es_sensible(empresa) else texto,
        estado=EstadoMensaje.PENDIENTE,
    )
    db.add(mensaje)
    db.flush()

    try:
        resultado = proveedor.enviar(
            destino, plantilla.codigo, variables, texto_visible, botones
        )
    except ErrorProveedor as e:
        mensaje.estado = EstadoMensaje.FALLIDO
        mensaje.error = str(e)[:300]
        creditos_wa.devolver(db, empresa.id, mensaje.id, detalle=f"falló {codigo}")
        db.commit()
        log.warning("envío de WhatsApp fallido",
                    extra={"empresa_id": empresa.id, "mensaje_id": mensaje.id})
        return mensaje

    mensaje.estado = EstadoMensaje.ENVIADO
    mensaje.externo_id = resultado.wamid
    db.commit()
    return mensaje


def responder_texto(
    db: Session,
    empresa: Empresa,
    cliente: Cliente,
    texto: str,
) -> Mensaje | None:
    """Contesta con un mensaje libre. Solo vale dentro de la ventana de 24 h.

    SOBRE EL COSTO, Y ES UNA FECHA EN EL CALENDARIO
    ------------------------------------------------
    Hoy (agosto 2026) un mensaje de servicio dentro de la ventana de 24 h es
    GRATIS para Meta, así que por defecto esto NO descuenta crédito: cobrarle
    al negocio algo que no nos cuesta sería mentirle.

    **El 1 de octubre de 2026 Meta empieza a cobrarlos.** Ese día hay que poner
    WA_COBRAR_SERVICIO=true en el .env y estas respuestas pasan a descontar
    como cualquier otro mensaje. Está como interruptor y no como constante
    justamente para que ese día sea una línea del .env y no un deploy.
    """
    try:
        destino = normalizar_ar(cliente.telefono)
    except TelefonoInvalido:
        return None

    cobra = bool(settings.wa_cobrar_servicio)
    if cobra:
        try:
            creditos_wa.consumir(db, empresa.id, detalle="respuesta de servicio")
        except creditos_wa.SinSaldo:
            return None

    mensaje = Mensaje(
        empresa_id=empresa.id,
        cliente_id=cliente.id,
        canal=CanalMensaje.WHATSAPP,
        direccion=DireccionMensaje.SALIENTE,
        contenido=None if es_sensible(empresa) else texto,
        estado=EstadoMensaje.PENDIENTE,
    )
    db.add(mensaje)
    db.flush()

    try:
        resultado = proveedor_de(empresa).enviar_texto(destino, texto)
    except ErrorProveedor as e:
        mensaje.estado = EstadoMensaje.FALLIDO
        mensaje.error = str(e)[:300]
        if cobra:
            creditos_wa.devolver(db, empresa.id, mensaje.id, detalle="falló la respuesta")
        db.commit()
        return mensaje

    mensaje.estado = EstadoMensaje.ENVIADO
    mensaje.externo_id = resultado.wamid
    db.commit()
    return mensaje
