"""Regresión del fix-013: botones del recordatorio y mensajes entrantes.

Lo que protege cada bloque:

  · el payload lleva el id del turno, así que se actúa sobre ESE turno y no
    sobre "el que ese teléfono tenga más o menos ahora"
  · SOLO el teléfono del cliente del turno puede cancelarlo — sin esto,
    cualquiera con un payload válido cancela turnos ajenos
  · Meta reintenta los webhooks: el mismo mensaje dos veces no cancela dos
    veces ni duplica filas
  · "BAJA" da de baja de verdad, que es un derecho y no una cortesía
  · la respuesta de servicio no descuenta crédito hasta el 1-oct-2026, porque
    hasta ese día Meta no la cobra
"""

import datetime as dt
import hashlib
import hmac
import json

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.crypto import hash_clave
from app.models import Cliente, Rubro, Usuario
from app.models.enums import (
    CanalMensaje,
    DireccionMensaje,
    EstadoMensaje,
    EstadoTurno,
    RolUsuario,
)
from app.models.mensajeria import Mensaje, PlantillaMensaje
from app.models.turno import Turno
from app.services import creditos_wa
from app.services import whatsapp as wa
from app.services import whatsapp_entrante as entrante

TELEFONO = "2614123456"
WA_ID = "5492614123456"


# ══════════════════════════════════════════════════════════════════════════
#  Armado
# ══════════════════════════════════════════════════════════════════════════


def _plantilla_con_botones(db, empresa_id: int) -> PlantillaMensaje:
    p = PlantillaMensaje(
        empresa_id=empresa_id,
        canal=CanalMensaje.WHATSAPP,
        codigo="recordatorio_24h",
        nombre="Recordatorio",
        cuerpo="Hola {{1}}! Te recordamos {{2}} en {{3}}: {{4}}. ¿Nos confirmás?",
        aprobada_meta=False,
        activa=True,
        con_botones=True,
    )
    db.add(p)
    db.flush()
    return p


def _armar(db, armar_empresa, nombre="Barbería Test", saldo=10):
    ctx = armar_empresa(nombre)
    _plantilla_con_botones(db, ctx.empresa.id)
    ctx.cliente.telefono = TELEFONO
    ctx.cliente.acepta_whatsapp = True
    ctx.empresa.wa_phone_number_id = f"pn-{ctx.empresa.id}"
    db.flush()
    if saldo:
        creditos_wa.acreditar(db, ctx.empresa.id, saldo)
    return ctx


def _turno(db, ctx, estado=EstadoTurno.PENDIENTE) -> Turno:
    inicio = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=24)
    t = Turno(
        empresa_id=ctx.empresa.id,
        cliente_id=ctx.cliente.id,
        servicio_id=ctx.servicio.id,
        recurso_id=ctx.lucas.id,
        fecha_inicio=inicio,
        fecha_fin=inicio + dt.timedelta(minutes=30),
        estado=estado,
    )
    db.add(t)
    db.flush()
    return t


def _evento_boton(turno_id, accion, wa_id=WA_ID, wamid="wamid.in1", pn="pn-x") -> dict:
    return {
        "metadata": {"phone_number_id": pn},
        "messages": [
            {
                "id": wamid,
                "from": wa_id,
                "type": "button",
                "button": {
                    "payload": wa.payload_boton(turno_id, accion),
                    "text": "No puedo ir",
                },
            }
        ],
    }


def _evento_texto(texto, wa_id=WA_ID, wamid="wamid.t1", pn="pn-x") -> dict:
    return {
        "metadata": {"phone_number_id": pn},
        "messages": [
            {"id": wamid, "from": wa_id, "type": "text", "text": {"body": texto}}
        ],
    }


# ══════════════════════════════════════════════════════════════════════════
#  1. El payload
# ══════════════════════════════════════════════════════════════════════════


def test_el_payload_lleva_el_turno_y_vuelve_entero():
    assert wa.payload_boton(481, "cancelar") == "t360:481:cancelar"
    assert wa.leer_payload("t360:481:cancelar") == (481, "cancelar")
    assert wa.leer_payload(wa.payload_boton(7, "confirmar")) == (7, "confirmar")


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "cualquier cosa",
        "otro:481:cancelar",     # no es nuestro
        "t360:481:borrar",       # acción que no existe
        "t360:abc:cancelar",     # id que no es número
        "t360:481",              # incompleto
        "t360:481:cancelar:x",   # de más
    ],
)
def test_un_payload_que_no_es_nuestro_no_se_interpreta(payload):
    assert wa.leer_payload(payload) is None


# ══════════════════════════════════════════════════════════════════════════
#  2. Los botones al mandar
# ══════════════════════════════════════════════════════════════════════════


def test_el_recordatorio_sale_con_los_dos_botones(db, armar_empresa, monkeypatch):
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx)

    capturado = {}

    def espia(self, destino, plantilla, variables, texto, botones=None):
        capturado["botones"] = botones
        return wa.Enviado(wamid="sim.x", proveedor="simulado")

    monkeypatch.setattr(wa.ProveedorSimulado, "enviar", espia)
    wa.enviar_plantilla(
        db, ctx.empresa, ctx.cliente, "recordatorio_24h", ["a", "b", "c", "d"],
        turno_id=turno.id,
    )

    assert capturado["botones"] == [
        f"t360:{turno.id}:confirmar",
        f"t360:{turno.id}:cancelar",
    ]


def test_sin_turno_no_hay_botones(db, armar_empresa, monkeypatch):
    """Un botón «No puedo ir» sin turno no sabría qué cancelar."""
    ctx = _armar(db, armar_empresa)
    capturado = {}

    def espia(self, destino, plantilla, variables, texto, botones=None):
        capturado["botones"] = botones
        return wa.Enviado(wamid="sim.x", proveedor="simulado")

    monkeypatch.setattr(wa.ProveedorSimulado, "enviar", espia)
    wa.enviar_plantilla(db, ctx.empresa, ctx.cliente, "recordatorio_24h", ["a", "b", "c", "d"])
    assert capturado["botones"] is None


def test_una_plantilla_sin_botones_no_manda_botones(db, armar_empresa, monkeypatch):
    ctx = _armar(db, armar_empresa)
    plantilla = wa.buscar_plantilla(db, ctx.empresa.id, "recordatorio_24h")
    plantilla.con_botones = False
    db.flush()
    turno = _turno(db, ctx)

    capturado = {}

    def espia(self, destino, plantilla, variables, texto, botones=None):
        capturado["botones"] = botones
        return wa.Enviado(wamid="sim.x", proveedor="simulado")

    monkeypatch.setattr(wa.ProveedorSimulado, "enviar", espia)
    wa.enviar_plantilla(
        db, ctx.empresa, ctx.cliente, "recordatorio_24h", ["a", "b", "c", "d"],
        turno_id=turno.id,
    )
    assert capturado["botones"] is None


# ══════════════════════════════════════════════════════════════════════════
#  3. El botón que cancela — el corazón del fix
# ══════════════════════════════════════════════════════════════════════════


def test_no_puedo_ir_cancela_el_turno_y_libera_el_horario(db, armar_empresa):
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx)

    actuados = entrante.procesar(db, _evento_boton(turno.id, "cancelar"))

    assert actuados == 1
    db.refresh(turno)
    assert turno.estado == EstadoTurno.CANCELADO
    assert "WhatsApp" in (turno.motivo_cancelacion or "")


def test_confirmo_confirma_el_turno(db, armar_empresa):
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx)

    entrante.procesar(db, _evento_boton(turno.id, "confirmar"))

    db.refresh(turno)
    assert turno.estado == EstadoTurno.CONFIRMADO


def test_el_toque_del_boton_queda_registrado(db, armar_empresa):
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx)
    entrante.procesar(db, _evento_boton(turno.id, "cancelar"))

    fila = db.scalars(
        select(Mensaje).where(
            Mensaje.turno_id == turno.id,
            Mensaje.direccion == DireccionMensaje.ENTRANTE,
        )
    ).one()
    assert fila.externo_id == "wamid.in1"
    assert "cancelar" in (fila.contenido or "")


def test_al_cliente_le_contestamos_que_quedo_cancelado(db, armar_empresa):
    """Tocar un botón y no recibir nada se siente como que no funcionó."""
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx)
    entrante.procesar(db, _evento_boton(turno.id, "cancelar"))

    salientes = db.scalars(
        select(Mensaje).where(
            Mensaje.empresa_id == ctx.empresa.id,
            Mensaje.direccion == DireccionMensaje.SALIENTE,
        )
    ).all()
    assert len(salientes) == 1
    assert salientes[0].estado == EstadoMensaje.ENVIADO
    assert "cancelamos" in salientes[0].contenido


def test_desde_OTRO_telefono_no_pasa_nada(db, armar_empresa):
    """LA defensa. Sin esto, un payload filtrado cancela turnos ajenos."""
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx)

    actuados = entrante.procesar(
        db, _evento_boton(turno.id, "cancelar", wa_id="5491100000000")
    )

    assert actuados == 0
    db.refresh(turno)
    assert turno.estado == EstadoTurno.PENDIENTE
    assert db.scalars(select(Mensaje).where(Mensaje.turno_id == turno.id)).first() is None


def test_un_turno_que_ya_estaba_cancelado_no_rompe(db, armar_empresa):
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx, estado=EstadoTurno.CANCELADO)

    assert entrante.procesar(db, _evento_boton(turno.id, "cancelar")) == 0
    db.refresh(turno)
    assert turno.estado == EstadoTurno.CANCELADO


def test_un_turno_ya_finalizado_no_se_cancela_por_un_boton_viejo(db, armar_empresa):
    """El cliente encontró el mensaje de la semana pasada y lo tocó."""
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx, estado=EstadoTurno.FINALIZADO)

    entrante.procesar(db, _evento_boton(turno.id, "cancelar"))

    db.refresh(turno)
    assert turno.estado == EstadoTurno.FINALIZADO


def test_un_turno_que_no_existe_no_rompe(db, armar_empresa):
    _armar(db, armar_empresa)
    assert entrante.procesar(db, _evento_boton(999999, "cancelar")) == 0


def test_meta_reintenta_y_no_pasa_dos_veces(db, armar_empresa):
    """Los webhooks se reintentan. El mismo mensaje no se procesa dos veces."""
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx)
    evento = _evento_boton(turno.id, "cancelar")

    assert entrante.procesar(db, evento) == 1
    assert entrante.procesar(db, evento) == 0

    entrantes = db.scalars(
        select(Mensaje).where(
            Mensaje.turno_id == turno.id,
            Mensaje.direccion == DireccionMensaje.ENTRANTE,
        )
    ).all()
    assert len(entrantes) == 1


def test_el_boton_interactivo_tambien_funciona(db, armar_empresa):
    """Meta manda `button` para plantillas y `interactive` para otros flujos."""
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx)

    valor = {
        "metadata": {"phone_number_id": "pn-x"},
        "messages": [
            {
                "id": "wamid.i1",
                "from": WA_ID,
                "type": "interactive",
                "interactive": {
                    "button_reply": {
                        "id": wa.payload_boton(turno.id, "cancelar"),
                        "title": "No puedo ir",
                    }
                },
            }
        ],
    }
    assert entrante.procesar(db, valor) == 1
    db.refresh(turno)
    assert turno.estado == EstadoTurno.CANCELADO


# ══════════════════════════════════════════════════════════════════════════
#  4. El texto libre y la baja
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("texto", ["BAJA", "baja", "Baja.", " baja! ", "stop", "Baja por favor"])
def test_pedir_la_baja_lo_saca_de_los_recordatorios(db, armar_empresa, texto):
    ctx = _armar(db, armar_empresa)
    ctx.empresa.wa_phone_number_id = "pn-baja"
    db.flush()

    resultado = entrante.procesar(db, _evento_texto(texto, pn="pn-baja"))

    assert resultado == 1
    db.refresh(ctx.cliente)
    assert ctx.cliente.acepta_whatsapp is False


@pytest.mark.parametrize("texto", ["hola", "voy a llegar 5 minutos tarde", "bajame el precio"])
def test_un_mensaje_cualquiera_no_da_de_baja(db, armar_empresa, texto):
    ctx = _armar(db, armar_empresa)
    ctx.empresa.wa_phone_number_id = "pn-baja"
    db.flush()

    entrante.procesar(db, _evento_texto(texto, pn="pn-baja"))

    db.refresh(ctx.cliente)
    assert ctx.cliente.acepta_whatsapp is True


def test_un_mensaje_de_un_cliente_conocido_queda_registrado(db, armar_empresa):
    ctx = _armar(db, armar_empresa)
    ctx.empresa.wa_phone_number_id = "pn-reg"
    db.flush()

    entrante.procesar(db, _evento_texto("voy a llegar tarde", pn="pn-reg"))

    fila = db.scalars(
        select(Mensaje).where(
            Mensaje.empresa_id == ctx.empresa.id,
            Mensaje.direccion == DireccionMensaje.ENTRANTE,
        )
    ).one()
    assert fila.contenido == "voy a llegar tarde"


def test_un_numero_desconocido_no_deja_rastro(db, armar_empresa):
    """En coexistencia por acá pasan también los chats privados del dueño."""
    ctx = _armar(db, armar_empresa)
    ctx.empresa.wa_phone_number_id = "pn-desc"
    db.flush()

    entrante.procesar(db, _evento_texto("hola", wa_id="5491199999999", pn="pn-desc"))

    assert db.scalars(
        select(Mensaje).where(Mensaje.empresa_id == ctx.empresa.id)
    ).first() is None


def test_sin_numero_de_la_empresa_no_se_guarda_nada(db, armar_empresa):
    """Si no se sabe de qué negocio es, no se archiva la conversación de nadie."""
    _armar(db, armar_empresa)
    assert entrante.procesar(db, _evento_texto("hola", pn=None)) == 0
    assert db.scalars(select(Mensaje).where(Mensaje.externo_id == "wamid.t1")).first() is None


def test_en_salud_el_texto_entrante_no_se_guarda(db, armar_empresa):
    """«me duele desde el martes» es una consulta clínica, no un mensaje."""
    ctx = _armar(db, armar_empresa, nombre="Consultorio")
    rubro = db.scalars(select(Rubro).where(Rubro.codigo == "medico")).first()
    if rubro is None:
        rubro = Rubro(codigo="medico", nombre="Salud", preset={})
        db.add(rubro)
        db.flush()
    ctx.empresa.rubro_id = rubro.id
    ctx.empresa.wa_phone_number_id = "pn-salud"
    db.flush()
    db.refresh(ctx.empresa)

    entrante.procesar(db, _evento_texto("me duele desde el martes", pn="pn-salud"))

    fila = db.scalars(
        select(Mensaje).where(
            Mensaje.empresa_id == ctx.empresa.id,
            Mensaje.direccion == DireccionMensaje.ENTRANTE,
        )
    ).one()
    assert fila.contenido is None


# ══════════════════════════════════════════════════════════════════════════
#  5. La respuesta de servicio y el 1 de octubre
# ══════════════════════════════════════════════════════════════════════════


def test_hoy_contestar_no_descuenta_credito(db, armar_empresa):
    """Meta no lo cobra hasta el 1-oct-2026: cobrarlo sería inventar un costo."""
    ctx = _armar(db, armar_empresa, saldo=5)
    turno = _turno(db, ctx)
    entrante.procesar(db, _evento_boton(turno.id, "cancelar"))
    # El recordatorio no se mandó en este test, así que el saldo está entero.
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 5


def test_desde_el_1_de_octubre_contestar_si_descuenta(db, armar_empresa, monkeypatch):
    monkeypatch.setattr(settings, "wa_cobrar_servicio", True)
    ctx = _armar(db, armar_empresa, saldo=5)
    turno = _turno(db, ctx)

    entrante.procesar(db, _evento_boton(turno.id, "cancelar"))

    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 4


def test_si_la_respuesta_falla_el_credito_vuelve(db, armar_empresa, monkeypatch):
    monkeypatch.setattr(settings, "wa_cobrar_servicio", True)

    def explota(self, destino, texto):
        raise wa.ErrorProveedor("Meta respondió 400")

    monkeypatch.setattr(wa.ProveedorSimulado, "enviar_texto", explota)
    ctx = _armar(db, armar_empresa, saldo=5)
    turno = _turno(db, ctx)

    entrante.procesar(db, _evento_boton(turno.id, "cancelar"))

    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 5
    db.refresh(turno)
    # La cancelación se hizo igual: la respuesta es un extra, no la operación.
    assert turno.estado == EstadoTurno.CANCELADO


def test_sin_saldo_y_cobrando_no_se_contesta_pero_se_cancela(db, armar_empresa, monkeypatch):
    monkeypatch.setattr(settings, "wa_cobrar_servicio", True)
    ctx = _armar(db, armar_empresa, saldo=0)
    turno = _turno(db, ctx)

    entrante.procesar(db, _evento_boton(turno.id, "cancelar"))

    db.refresh(turno)
    assert turno.estado == EstadoTurno.CANCELADO
    assert db.scalars(
        select(Mensaje).where(
            Mensaje.empresa_id == ctx.empresa.id,
            Mensaje.direccion == DireccionMensaje.SALIENTE,
        )
    ).first() is None


# ══════════════════════════════════════════════════════════════════════════
#  6. De punta a punta, por el webhook real
# ══════════════════════════════════════════════════════════════════════════


def _firmar(cuerpo: dict, secreto: str):
    crudo = json.dumps(cuerpo).encode()
    firma = hmac.new(secreto.encode(), crudo, hashlib.sha256).hexdigest()
    return crudo, {"X-Hub-Signature-256": f"sha256={firma}"}


def test_el_cliente_toca_no_puedo_ir_y_el_horario_queda_libre(
    client, db, armar_empresa, monkeypatch
):
    """El camino completo: webhook firmado -> turno cancelado."""
    monkeypatch.setattr(settings, "wa_app_secret", "app-secreto")
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx)

    cuerpo = {"entry": [{"changes": [{"value": _evento_boton(turno.id, "cancelar")}]}]}
    crudo, cabeceras = _firmar(cuerpo, "app-secreto")

    r = client.post("/publico/whatsapp/webhook", content=crudo, headers=cabeceras)

    assert r.status_code == 200
    assert r.json()["entrantes"] == 1
    db.refresh(turno)
    assert turno.estado == EstadoTurno.CANCELADO


def test_el_webhook_sin_firma_no_cancela_nada(client, db, armar_empresa, monkeypatch):
    monkeypatch.setattr(settings, "wa_app_secret", "app-secreto")
    ctx = _armar(db, armar_empresa)
    turno = _turno(db, ctx)

    cuerpo = {"entry": [{"changes": [{"value": _evento_boton(turno.id, "cancelar")}]}]}
    r = client.post("/publico/whatsapp/webhook", json=cuerpo)

    assert r.status_code == 403
    db.refresh(turno)
    assert turno.estado == EstadoTurno.PENDIENTE


def test_recepcion_no_puede_ver_el_whatsapp_de_otra_empresa(client, db, armar_empresa):
    """Control de que el fix no abrió ninguna puerta nueva."""
    ctx = _armar(db, armar_empresa)
    otro = Usuario(
        empresa_id=ctx.empresa.id,
        nombre="Recepción",
        email=f"recep13-{ctx.empresa.slug}@example.com",
        hash_clave=hash_clave("x"),
        rol=RolUsuario.RECEPCION,
    )
    db.add(otro)
    db.flush()
    from .conftest import token_de

    assert client.get("/whatsapp/estado", headers=token_de(otro)).status_code == 403


def test_un_cliente_de_otra_empresa_con_el_mismo_telefono_no_se_mezcla(db, armar_empresa):
    """Dos negocios distintos pueden tener al mismo cliente cargado."""
    a = _armar(db, armar_empresa, "Barbería A")
    b = _armar(db, armar_empresa, "Barbería B")
    a.empresa.wa_phone_number_id = "pn-a"
    b.empresa.wa_phone_number_id = "pn-b"
    db.add(Cliente(empresa_id=b.empresa.id, nombre="Juan", telefono=TELEFONO))
    db.flush()

    entrante.procesar(db, _evento_texto("baja", pn="pn-a"))

    db.refresh(a.cliente)
    db.refresh(b.cliente)
    assert a.cliente.acepta_whatsapp is False
    assert b.cliente.acepta_whatsapp is True
