"""Regresión del fix-011: WhatsApp — teléfono, medidor de créditos y envío.

Lo que estos tests protegen, en una línea cada uno:

  · un número mal interpretado manda un mensaje pago a un desconocido
  · un crédito mal contado es plata que Turnos360 pone y no cobra
  · un envío que falla y no devuelve el crédito le cobra al negocio algo que
    nunca recibió
  · un webhook sin firma deja que cualquiera invente métricas
  · un rubro de salud que nombra el servicio manda un diagnóstico por WhatsApp
"""

import datetime as dt
import hashlib
import hmac
import json

import pytest
from sqlalchemy import select

from app.core.crypto import desencriptar_credenciales, hash_clave
from app.core.seguridad import crear_token_superadmin
from app.core.telefono import TelefonoInvalido, es_valido_ar, normalizar_ar, para_mostrar
from app.models import Cliente, Rubro, SuperAdmin, Usuario
from app.models.enums import CanalMensaje, EstadoMensaje, EstadoTurno, RolUsuario
from app.models.mensajeria import Mensaje, PlantillaMensaje
from app.models.turno import Turno
from app.models.whatsapp import MovimientoWhatsapp
from app.services import creditos_wa
from app.services import whatsapp as wa

from .conftest import token_de


# ══════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════


def _cabecera_superadmin(db) -> dict:
    sa = SuperAdmin(
        nombre="Admin WA",
        email=f"admin-wa-{dt.datetime.now().timestamp()}@turnos360.com",
        hash_clave=hash_clave("x"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


def _plantillas(db, empresa_id: int, aprobada: bool = False) -> PlantillaMensaje:
    """Las dos plantillas que crea la migración, para empresas nacidas en un test."""
    p = None
    for codigo, cuerpo in (
        ("confirmacion", "Hola {{1}}! Te confirmamos {{2}} en {{3}} para el {{4}}."),
        ("recordatorio_24h", "Hola {{1}}! Te recordamos {{2}} en {{3}}: {{4}}."),
        ("recordatorio_2h", "Hola {{1}}! {{2}} en {{3}} en un rato: {{4}}."),
    ):
        p = PlantillaMensaje(
            empresa_id=empresa_id,
            canal=CanalMensaje.WHATSAPP,
            codigo=codigo,
            nombre=codigo,
            cuerpo=cuerpo,
            aprobada_meta=aprobada,
            activa=True,
        )
        db.add(p)
    db.flush()
    return p


def _cliente_ok(db, ctx, telefono: str = "2614123456") -> Cliente:
    ctx.cliente.telefono = telefono
    ctx.cliente.acepta_whatsapp = True
    db.flush()
    return ctx.cliente


# ══════════════════════════════════════════════════════════════════════════
#  1. El teléfono
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "entrada",
    [
        "2614123456",
        "261 4123456",
        "261 412-3456",
        "0261 15 4123456",
        "(0261) 15-4123456",
        "+54 9 261 412-3456",
        "5492614123456",
        "54 261 4123456",
        "0054 9 261 4123456",
        "  2614123456  ",
    ],
)
def test_todas_estas_formas_de_escribir_el_mismo_numero_dan_lo_mismo(entrada):
    """Diez formas de escribirlo en el mostrador. Es la misma persona."""
    assert normalizar_ar(entrada) == "5492614123456"


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("11 1234-5678", "5491112345678"),      # Buenos Aires, área de 2
        ("011 15 1234-5678", "5491112345678"),  # con 0 y con 15
        ("+5491112345678", "5491112345678"),
        ("3514123456", "5493514123456"),        # Córdoba
        ("2966412345", "5492966412345"),        # área de 4
    ],
)
def test_areas_de_dos_tres_y_cuatro_digitos(entrada, esperado):
    """El 15 va después del código de área, y el área mide 2, 3 o 4."""
    assert normalizar_ar(entrada) == esperado


@pytest.mark.parametrize(
    "entrada",
    [
        None,
        "",
        "   ",
        "sin telefono",
        "123",                 # corto
        "26141234567890",      # largo
        "0000000000",          # relleno
        "1111111111",
        "261a3f2b1c",          # lo que sale de un uuid mal usado
    ],
)
def test_lo_que_no_se_puede_interpretar_falla_en_voz_alta(entrada):
    """Devolver «algo parecido» manda un mensaje pago a un desconocido."""
    with pytest.raises(TelefonoInvalido):
        normalizar_ar(entrada)
    assert es_valido_ar(entrada) is False


def test_el_error_explica_que_hacer():
    with pytest.raises(TelefonoInvalido) as e:
        normalizar_ar("123456")
    texto = str(e.value)
    assert "dígitos" in texto and "10" in texto


def test_para_mostrar_lo_deja_legible():
    assert para_mostrar("02611541234 56") == "+54 9 261 412-3456"
    # Si no lo entiende, devuelve lo que había: nunca inventa un número.
    assert para_mostrar("sin telefono") == "sin telefono"


# ══════════════════════════════════════════════════════════════════════════
#  2. El medidor de créditos
# ══════════════════════════════════════════════════════════════════════════


def test_una_empresa_nueva_arranca_sin_saldo(db, armar_empresa):
    ctx = armar_empresa()
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 0


def test_acreditar_suma_y_deja_el_precio_que_se_pago(db, armar_empresa):
    ctx = armar_empresa()
    saldo = creditos_wa.acreditar(db, ctx.empresa.id, 500, precio_ars=36500)
    assert saldo == 500

    mov = db.scalars(
        select(MovimientoWhatsapp).where(MovimientoWhatsapp.empresa_id == ctx.empresa.id)
    ).one()
    assert mov.cantidad == 500
    assert float(mov.precio_ars) == 36500
    assert mov.motivo == "pack"


def test_consumir_descuenta_uno_y_lleva_el_acumulado(db, armar_empresa):
    ctx = armar_empresa()
    creditos_wa.acreditar(db, ctx.empresa.id, 3)
    assert creditos_wa.consumir(db, ctx.empresa.id) == 2
    assert creditos_wa.consumir(db, ctx.empresa.id) == 1

    resumen = creditos_wa.resumen(db, ctx.empresa.id)
    assert resumen["disponible"] == 1
    assert resumen["consumidos"] == 2


def test_sin_saldo_no_se_puede_consumir(db, armar_empresa):
    ctx = armar_empresa()
    creditos_wa.acreditar(db, ctx.empresa.id, 1)
    creditos_wa.consumir(db, ctx.empresa.id)
    with pytest.raises(creditos_wa.SinSaldo):
        creditos_wa.consumir(db, ctx.empresa.id)


def test_devolver_repone_el_credito_y_baja_el_acumulado(db, armar_empresa):
    ctx = armar_empresa()
    creditos_wa.acreditar(db, ctx.empresa.id, 2)
    creditos_wa.consumir(db, ctx.empresa.id)
    creditos_wa.devolver(db, ctx.empresa.id)
    resumen = creditos_wa.resumen(db, ctx.empresa.id)
    assert resumen["disponible"] == 2
    assert resumen["consumidos"] == 0


def test_acreditar_cero_o_negativo_no_se_permite(db, armar_empresa):
    ctx = armar_empresa()
    for cantidad in (0, -5):
        with pytest.raises(ValueError):
            creditos_wa.acreditar(db, ctx.empresa.id, cantidad)


def test_el_libro_manda_sobre_el_contador(db, armar_empresa):
    """Si el contador se desincroniza, recalcular() lo reconstruye del libro."""
    ctx = armar_empresa()
    creditos_wa.acreditar(db, ctx.empresa.id, 100)
    creditos_wa.consumir(db, ctx.empresa.id)

    fila = creditos_wa._fila_saldo(db, ctx.empresa.id)
    fila.disponible = 9999          # simulamos la corrupción
    db.flush()

    assert creditos_wa.recalcular(db, ctx.empresa.id) == 99


def test_los_packs_nunca_se_venden_por_debajo_del_costo():
    unitario = creditos_wa.precio_mensaje_ars()
    for pack in creditos_wa.packs():
        assert pack["precio_ars"] >= pack["cantidad"] * unitario
        assert pack["precio_ars"] % 100 == 0
        assert pack["precio_por_mensaje"] >= unitario


def test_el_saldo_de_una_empresa_no_se_mezcla_con_el_de_otra(db, armar_empresa):
    a = armar_empresa("Barbería A")
    b = armar_empresa("Barbería B")
    creditos_wa.acreditar(db, a.empresa.id, 10)
    assert creditos_wa.saldo_de(db, a.empresa.id) == 10
    assert creditos_wa.saldo_de(db, b.empresa.id) == 0


# ══════════════════════════════════════════════════════════════════════════
#  3. El envío
# ══════════════════════════════════════════════════════════════════════════


def test_con_saldo_y_telefono_el_mensaje_sale_y_descuenta_uno(db, armar_empresa):
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    cliente = _cliente_ok(db, ctx)
    creditos_wa.acreditar(db, ctx.empresa.id, 5)

    mensaje = wa.enviar_plantilla(
        db, ctx.empresa, cliente, "recordatorio_24h", ["Juan", "Corte", "Barbería", "mañana"]
    )

    assert mensaje is not None
    assert mensaje.estado == EstadoMensaje.ENVIADO
    assert mensaje.externo_id.startswith("sim.")
    assert mensaje.canal == CanalMensaje.WHATSAPP
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 4


def test_sin_saldo_no_sale_nada_y_no_queda_registro(db, armar_empresa):
    """Es el corte que protege la tarjeta: sin crédito, no se toca la red."""
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    cliente = _cliente_ok(db, ctx)

    assert wa.enviar_plantilla(db, ctx.empresa, cliente, "recordatorio_24h", ["a", "b", "c", "d"]) is None
    assert db.scalars(select(Mensaje).where(Mensaje.empresa_id == ctx.empresa.id)).first() is None


def test_sin_plantilla_cargada_no_sale_nada(db, armar_empresa):
    ctx = armar_empresa()
    cliente = _cliente_ok(db, ctx)
    creditos_wa.acreditar(db, ctx.empresa.id, 5)

    assert wa.enviar_plantilla(db, ctx.empresa, cliente, "recordatorio_24h", []) is None
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 5


def test_sin_consentimiento_no_sale_nada(db, armar_empresa):
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    cliente = _cliente_ok(db, ctx)
    cliente.acepta_whatsapp = False
    db.flush()
    creditos_wa.acreditar(db, ctx.empresa.id, 5)

    assert wa.enviar_plantilla(db, ctx.empresa, cliente, "recordatorio_24h", ["a", "b", "c", "d"]) is None
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 5


def test_un_telefono_malo_queda_registrado_pero_no_cuesta_un_credito(db, armar_empresa):
    """El dueño tiene que poder ver qué teléfonos hay que arreglar."""
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    cliente = _cliente_ok(db, ctx, telefono="no tengo")
    creditos_wa.acreditar(db, ctx.empresa.id, 5)

    assert wa.enviar_plantilla(db, ctx.empresa, cliente, "recordatorio_24h", ["a", "b", "c", "d"]) is None

    fallido = db.scalars(select(Mensaje).where(Mensaje.empresa_id == ctx.empresa.id)).one()
    assert fallido.estado == EstadoMensaje.FALLIDO
    assert "no tengo" in fallido.error
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 5


def test_si_el_proveedor_falla_el_credito_vuelve(db, armar_empresa, monkeypatch):
    """Cobrarle al negocio un mensaje que nunca salió es robarle."""
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    cliente = _cliente_ok(db, ctx)
    creditos_wa.acreditar(db, ctx.empresa.id, 5)

    def explota(self, destino, plantilla, variables, texto, botones=None):
        raise wa.ErrorProveedor("Meta respondió 500")

    monkeypatch.setattr(wa.ProveedorSimulado, "enviar", explota)

    mensaje = wa.enviar_plantilla(
        db, ctx.empresa, cliente, "recordatorio_24h", ["a", "b", "c", "d"]
    )
    assert mensaje.estado == EstadoMensaje.FALLIDO
    assert "500" in mensaje.error
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 5


def test_con_meta_una_plantilla_sin_aprobar_no_se_manda(db, armar_empresa, monkeypatch):
    """Mandarla es un error garantizado; mejor no salir a la red."""
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id, aprobada=False)
    cliente = _cliente_ok(db, ctx)
    creditos_wa.acreditar(db, ctx.empresa.id, 5)

    monkeypatch.setattr(
        wa, "proveedor_de", lambda empresa: wa.ProveedorMetaCloud("tok", "123")
    )
    assert wa.enviar_plantilla(db, ctx.empresa, cliente, "recordatorio_24h", ["a", "b", "c", "d"]) is None
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 5


def test_el_texto_se_arma_con_las_variables_como_en_meta():
    cuerpo = "Hola {{1}}! Te recordamos {{2}} en {{3}}: {{4}}."
    assert wa.render(cuerpo, ["Ana", "Corte", "Barbería Sur", "mañana 15:00"]) == (
        "Hola Ana! Te recordamos Corte en Barbería Sur: mañana 15:00."
    )


# ══════════════════════════════════════════════════════════════════════════
#  4. Regla 5: en salud, el servicio no se nombra
# ══════════════════════════════════════════════════════════════════════════


def _volver_sensible(db, ctx, codigo: str = "medico"):
    """Apunta la empresa al rubro «medico», que es lo que pasa en la realidad.

    Ojo con la tentación de renombrar el rubro descartable que arma el fixture:
    `rubro.codigo` es UNIQUE y el seed ya trae un «medico», así que en una base
    sembrada —o sea, la de cualquiera que corrió `make seed`— eso explota con
    una violación de clave única. Acá se reusa el que exista y se crea solo si
    falta, para que el test dé lo mismo en una base sembrada y en una vacía.
    """
    rubro = db.scalars(select(Rubro).where(Rubro.codigo == codigo)).first()
    if rubro is None:
        rubro = Rubro(codigo=codigo, nombre="Salud", preset={})
        db.add(rubro)
        db.flush()
    ctx.empresa.rubro_id = rubro.id
    db.flush()
    db.refresh(ctx.empresa)
    return ctx


def test_en_un_consultorio_el_mensaje_no_nombra_el_servicio(db, armar_empresa):
    """«Recordatorio: Consulta ginecológica» es un diagnóstico en la pantalla
    de bloqueo del celular."""
    ctx = _volver_sensible(db, armar_empresa("Consultorio"))
    assert wa.es_sensible(ctx.empresa) is True
    assert wa.servicio_para_mensaje(ctx.empresa, "Consulta ginecológica") == "tu turno"


def test_en_una_barberia_el_servicio_se_nombra(db, armar_empresa):
    ctx = armar_empresa()
    assert wa.es_sensible(ctx.empresa) is False
    assert wa.servicio_para_mensaje(ctx.empresa, "Corte y barba") == "Corte y barba"


def test_en_salud_el_texto_del_mensaje_no_se_guarda(db, armar_empresa):
    ctx = _volver_sensible(db, armar_empresa("Consultorio"))
    _plantillas(db, ctx.empresa.id)
    cliente = _cliente_ok(db, ctx)
    creditos_wa.acreditar(db, ctx.empresa.id, 5)

    mensaje = wa.enviar_plantilla(
        db, ctx.empresa, cliente, "recordatorio_24h", ["Ana", "tu turno", "Consultorio", "mañana"]
    )
    assert mensaje.estado == EstadoMensaje.ENVIADO
    assert mensaje.contenido is None


def test_en_una_barberia_el_texto_si_se_guarda(db, armar_empresa):
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    cliente = _cliente_ok(db, ctx)
    creditos_wa.acreditar(db, ctx.empresa.id, 5)

    mensaje = wa.enviar_plantilla(
        db, ctx.empresa, cliente, "recordatorio_24h", ["Ana", "Corte", "Barbería", "mañana"]
    )
    assert "Corte" in mensaje.contenido


# ══════════════════════════════════════════════════════════════════════════
#  5. La pantalla del dueño
# ══════════════════════════════════════════════════════════════════════════


def test_el_dueno_ve_su_estado_de_whatsapp(client, db, armar_empresa):
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    _cliente_ok(db, ctx)
    creditos_wa.acreditar(db, ctx.empresa.id, 500, precio_ars=36500)

    r = client.get("/whatsapp/estado", headers=token_de(ctx.dueno))
    assert r.status_code == 200
    datos = r.json()
    assert datos["proveedor"] == "simulado"
    assert datos["conectado"] is False
    assert datos["disponible"] == 500
    assert datos["plantillas_activas"] == 3
    assert datos["precio_mensaje_ars"] > 0
    assert len(datos["packs"]) == 4


def test_el_estado_cuenta_los_telefonos_que_no_sirven(client, db, armar_empresa):
    """Es el número que le dice al dueño cuántos recordatorios no van a salir."""
    ctx = armar_empresa()
    _cliente_ok(db, ctx, telefono="2614123456")
    db.add(Cliente(empresa_id=ctx.empresa.id, nombre="Sin tel", telefono=None))
    db.add(Cliente(empresa_id=ctx.empresa.id, nombre="Mal tel", telefono="no se"))
    db.flush()

    r = client.get("/whatsapp/estado", headers=token_de(ctx.dueno))
    assert r.json()["clientes_sin_telefono_valido"] == 2


def test_recepcion_no_entra_a_whatsapp(client, db, armar_empresa):
    ctx = armar_empresa()
    recepcion = Usuario(
        empresa_id=ctx.empresa.id,
        nombre="Recepción",
        email=f"recep-{ctx.empresa.slug}@example.com",
        hash_clave=hash_clave("x"),
        rol=RolUsuario.RECEPCION,
    )
    db.add(recepcion)
    db.flush()
    assert client.get("/whatsapp/estado", headers=token_de(recepcion)).status_code == 403


def test_la_prueba_valida_el_numero_y_no_cobra(client, db, armar_empresa):
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    creditos_wa.acreditar(db, ctx.empresa.id, 10)

    r = client.post(
        "/whatsapp/prueba",
        json={"telefono": "0261 15 4123456"},
        headers=token_de(ctx.dueno),
    )
    assert r.status_code == 200
    assert r.json()["destino"] == "5492614123456"
    assert "Juan" in r.json()["texto"]
    # No cuesta un crédito: se tiene que poder probar veinte veces.
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 10


def test_la_prueba_rechaza_un_numero_que_no_entiende(client, db, armar_empresa):
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    r = client.post(
        "/whatsapp/prueba", json={"telefono": "asdasd"}, headers=token_de(ctx.dueno)
    )
    assert r.status_code == 422


def test_el_historial_es_solo_de_la_propia_empresa(client, db, armar_empresa):
    a = armar_empresa("Barbería A")
    b = armar_empresa("Barbería B")
    for ctx in (a, b):
        _plantillas(db, ctx.empresa.id)
        _cliente_ok(db, ctx)
        creditos_wa.acreditar(db, ctx.empresa.id, 5)
        wa.enviar_plantilla(
            db, ctx.empresa, ctx.cliente, "recordatorio_24h", ["x", "y", "z", "w"]
        )

    r = client.get("/whatsapp/mensajes", headers=token_de(a.dueno))
    assert r.status_code == 200
    assert len(r.json()) == 1

    r2 = client.get("/whatsapp/movimientos", headers=token_de(a.dueno))
    # una carga + un consumo
    assert len(r2.json()) == 2


# ══════════════════════════════════════════════════════════════════════════
#  6. El super-admin
# ══════════════════════════════════════════════════════════════════════════


def test_el_superadmin_carga_un_pack(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.post(
        f"/admin/whatsapp/empresas/{ctx.empresa.id}/creditos",
        json={"cantidad": 500, "precio_ars": 36500},
        headers=_cabecera_superadmin(db),
    )
    assert r.status_code == 200
    assert r.json()["disponible"] == 500
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 500


def test_el_pack_queda_registrado_con_quien_lo_cargo(client, db, armar_empresa):
    ctx = armar_empresa()
    client.post(
        f"/admin/whatsapp/empresas/{ctx.empresa.id}/creditos",
        json={"cantidad": 250, "precio_ars": 18300},
        headers=_cabecera_superadmin(db),
    )
    mov = db.scalars(
        select(MovimientoWhatsapp).where(MovimientoWhatsapp.empresa_id == ctx.empresa.id)
    ).one()
    assert "cargado por" in mov.detalle
    assert float(mov.precio_ars) == 18300


def test_las_credenciales_se_guardan_encriptadas_y_el_token_no_vuelve(
    client, db, armar_empresa
):
    ctx = armar_empresa()
    r = client.put(
        f"/admin/whatsapp/empresas/{ctx.empresa.id}/credenciales",
        json={"token": "EAAG-secreto", "phone_number_id": "123456", "numero": "+5492611111111"},
        headers=_cabecera_superadmin(db),
    )
    assert r.status_code == 200
    assert "EAAG-secreto" not in r.text

    db.refresh(ctx.empresa)
    assert ctx.empresa.wa_credenciales is not None
    assert b"EAAG-secreto" not in ctx.empresa.wa_credenciales   # está cifrado
    assert desencriptar_credenciales(ctx.empresa.wa_credenciales)["token"] == "EAAG-secreto"


def test_el_dueno_no_puede_cargarse_creditos_a_si_mismo(client, db, armar_empresa):
    ctx = armar_empresa()
    r = client.post(
        f"/admin/whatsapp/empresas/{ctx.empresa.id}/creditos",
        json={"cantidad": 100000},
        headers=token_de(ctx.dueno),
    )
    assert r.status_code == 401
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 0


def test_acreditar_a_una_empresa_que_no_existe_da_404(client, db):
    r = client.post(
        "/admin/whatsapp/empresas/999999/creditos",
        json={"cantidad": 10},
        headers=_cabecera_superadmin(db),
    )
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
#  7. El webhook
# ══════════════════════════════════════════════════════════════════════════


def _firmar(cuerpo: dict, secreto: str) -> tuple[bytes, dict]:
    crudo = json.dumps(cuerpo).encode()
    firma = hmac.new(secreto.encode(), crudo, hashlib.sha256).hexdigest()
    return crudo, {"X-Hub-Signature-256": f"sha256={firma}"}


def _evento(wamid: str, estado: str) -> dict:
    return {
        "entry": [
            {"changes": [{"value": {"statuses": [{"id": wamid, "status": estado}]}}]}
        ]
    }


def test_la_verificacion_devuelve_el_desafio(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "wa_webhook_verify_token", "secreto-verificacion")
    r = client.get(
        "/publico/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "secreto-verificacion",
                "hub.challenge": "1234"},
    )
    assert r.status_code == 200
    assert r.text == "1234"


def test_la_verificacion_con_token_equivocado_no_pasa(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "wa_webhook_verify_token", "secreto-verificacion")
    r = client.get(
        "/publico/whatsapp/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "otro", "hub.challenge": "1234"},
    )
    assert r.status_code == 403


def test_sin_firma_el_webhook_rechaza(client, db, monkeypatch):
    """Sin esto, cualquiera de internet marca mensajes como leídos."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "wa_app_secret", "app-secreto")
    r = client.post("/publico/whatsapp/webhook", json=_evento("wamid.1", "read"))
    assert r.status_code == 403


def test_con_firma_valida_el_estado_avanza(client, db, armar_empresa, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "wa_app_secret", "app-secreto")
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    _cliente_ok(db, ctx)
    creditos_wa.acreditar(db, ctx.empresa.id, 5)
    mensaje = wa.enviar_plantilla(
        db, ctx.empresa, ctx.cliente, "recordatorio_24h", ["a", "b", "c", "d"]
    )

    crudo, cabeceras = _firmar(_evento(mensaje.externo_id, "delivered"), "app-secreto")
    r = client.post("/publico/whatsapp/webhook", content=crudo, headers=cabeceras)
    assert r.status_code == 200
    assert r.json()["actualizados"] == 1

    db.refresh(mensaje)
    assert mensaje.estado == EstadoMensaje.ENTREGADO


def test_un_estado_viejo_no_pisa_uno_nuevo(client, db, armar_empresa, monkeypatch):
    """Meta reintenta y reordena: un «sent» que llega tarde no puede
    desandar un «read» que ya llegó."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "wa_app_secret", "app-secreto")
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    _cliente_ok(db, ctx)
    creditos_wa.acreditar(db, ctx.empresa.id, 5)
    mensaje = wa.enviar_plantilla(
        db, ctx.empresa, ctx.cliente, "recordatorio_24h", ["a", "b", "c", "d"]
    )

    for estado in ("read", "sent"):
        crudo, cab = _firmar(_evento(mensaje.externo_id, estado), "app-secreto")
        client.post("/publico/whatsapp/webhook", content=crudo, headers=cab)

    db.refresh(mensaje)
    assert mensaje.estado == EstadoMensaje.LEIDO


def test_un_wamid_desconocido_no_rompe_nada(client, db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "wa_app_secret", "app-secreto")
    crudo, cab = _firmar(_evento("wamid.que-no-existe", "read"), "app-secreto")
    r = client.post("/publico/whatsapp/webhook", content=crudo, headers=cab)
    assert r.status_code == 200
    assert r.json()["actualizados"] == 0


def test_un_fallo_reportado_por_meta_queda_con_el_motivo(
    client, db, armar_empresa, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "wa_app_secret", "app-secreto")
    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    _cliente_ok(db, ctx)
    creditos_wa.acreditar(db, ctx.empresa.id, 5)
    mensaje = wa.enviar_plantilla(
        db, ctx.empresa, ctx.cliente, "recordatorio_24h", ["a", "b", "c", "d"]
    )

    evento = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": mensaje.externo_id,
                                    "status": "failed",
                                    "errors": [{"title": "Número no está en WhatsApp"}],
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    crudo, cab = _firmar(evento, "app-secreto")
    client.post("/publico/whatsapp/webhook", content=crudo, headers=cab)

    db.refresh(mensaje)
    assert mensaje.estado == EstadoMensaje.FALLIDO
    assert "WhatsApp" in mensaje.error


# ══════════════════════════════════════════════════════════════════════════
#  8. El recordatorio de verdad: WhatsApp primero, email de respaldo
# ══════════════════════════════════════════════════════════════════════════


class _SesionDePrueba:
    """Envuelve la sesión del test para que la tarea de Celery la use.

    La tarea abre `with SessionLocal() as db`, que crearía una sesión nueva
    fuera de la transacción del test y dejaría basura en la base. Acá le damos
    la misma sesión y le sacamos el close.
    """

    def __init__(self, sesion):
        self.sesion = sesion

    def __call__(self):
        return self

    def __enter__(self):
        return self.sesion

    def __exit__(self, *args):
        return False


def _turno_manana(db, ctx) -> Turno:
    inicio = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=24)
    turno = Turno(
        empresa_id=ctx.empresa.id,
        cliente_id=ctx.cliente.id,
        servicio_id=ctx.servicio.id,
        recurso_id=ctx.lucas.id,
        fecha_inicio=inicio,
        fecha_fin=inicio + dt.timedelta(minutes=30),
        estado=EstadoTurno.CONFIRMADO,
    )
    db.add(turno)
    db.flush()
    return turno


def test_el_recordatorio_sale_por_whatsapp_y_no_manda_el_email(
    db, armar_empresa, monkeypatch
):
    """Si el WhatsApp salió, mandar además el mail es molestar dos veces."""
    from app.tasks import emails as emails_mod

    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    cliente = _cliente_ok(db, ctx)
    cliente.email = "juan@example.com"
    db.flush()
    creditos_wa.acreditar(db, ctx.empresa.id, 5)
    turno = _turno_manana(db, ctx)

    mails = []
    monkeypatch.setattr(emails_mod, "SessionLocal", _SesionDePrueba(db))
    monkeypatch.setattr(emails_mod, "_mandar", lambda *a, **k: mails.append(a))

    emails_mod.enviar_recordatorio(turno.id)

    assert mails == []
    assert creditos_wa.saldo_de(db, ctx.empresa.id) == 4
    mensaje = db.scalars(
        select(Mensaje).where(Mensaje.turno_id == turno.id, Mensaje.canal == CanalMensaje.WHATSAPP)
    ).one()
    assert mensaje.estado == EstadoMensaje.ENVIADO


def test_sin_saldo_el_recordatorio_cae_al_email(db, armar_empresa, monkeypatch):
    """El email es el respaldo: el cliente igual se entera."""
    from app.tasks import emails as emails_mod

    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    cliente = _cliente_ok(db, ctx)
    cliente.email = "juan@example.com"
    db.flush()
    turno = _turno_manana(db, ctx)

    mails = []
    monkeypatch.setattr(emails_mod, "SessionLocal", _SesionDePrueba(db))
    monkeypatch.setattr(emails_mod, "_mandar", lambda *a, **k: mails.append(a))

    emails_mod.enviar_recordatorio(turno.id)

    assert len(mails) == 1


def test_sin_email_y_sin_saldo_no_explota_nada(db, armar_empresa, monkeypatch):
    from app.tasks import emails as emails_mod

    ctx = armar_empresa()
    _plantillas(db, ctx.empresa.id)
    cliente = _cliente_ok(db, ctx)
    cliente.email = None
    db.flush()
    turno = _turno_manana(db, ctx)

    monkeypatch.setattr(emails_mod, "SessionLocal", _SesionDePrueba(db))
    emails_mod.enviar_recordatorio(turno.id)   # no tiene que levantar
