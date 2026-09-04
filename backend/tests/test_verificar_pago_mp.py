"""Preguntarle a Mercado Pago qué pasó DE VERDAD con una cuota ya acreditada.

EL CASO, TAL CUAL LO PLANTEÓ LEANDRO
    «capaz no entro a mercado pago y se había marcado como cobrado»

El webhook acredita solo, y eso está bien. El agujero no es que el webhook
falle: es que lo que el webhook escribió NO SE REVISA NUNCA MÁS. Si el pago se
devolvió, se disputó o terminó en contracargo, Mercado Pago lo sabe y el panel
sigue mostrando «cobrado» para siempre. Nadie se entera hasta que el dinero no
está.

LA DECISIÓN DE DISEÑO QUE ESTOS TESTS PROTEGEN
La verificación es de SOLO LECTURA. Informa y deja decidir a una persona.
Anular una cuota automáticamente porque una consulta HTTP volvió mal —token
vencido, timeout, MP caído— borraría plata cobrada de verdad sin que nadie lo
pida, y ese error es mucho más caro que el que intenta evitar.
"""

import datetime as dt
import uuid

import pytest

from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import PagoSuscripcion, SuperAdmin
from app.services import mp_suscripcion as mp_sus


@pytest.fixture()
def admin(db) -> dict:
    sa = SuperAdmin(
        nombre="Admin MP",
        email=f"sa-{uuid.uuid4().hex}@turnos360.test",
        hash_clave=hash_clave("clave1234"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


def _pago(db, ctx, monto=19900, mp_id="123456789"):
    p = PagoSuscripcion(
        empresa_id=ctx.empresa.id,
        fecha=dt.date.today(),
        monto=monto,
        metodo="mercadopago",
        mp_payment_id=mp_id,
    )
    db.add(p)
    db.flush()
    return p


# ══════════════════════════════════════════════════════════════════════
#  Los casos donde NO hay nada que consultar se explican, no se ocultan
# ══════════════════════════════════════════════════════════════════════

def test_una_transferencia_dice_que_se_verifica_en_el_banco(db, armar_empresa):
    """Un «no se pudo consultar» genérico haría pensar que algo falló. No
    falló nada: esta cuota nunca pasó por Mercado Pago."""
    ctx = armar_empresa()
    pago = _pago(db, ctx, mp_id=None)
    pago.metodo = "transferencia"
    db.flush()

    r = mp_sus.verificar(db, pago)
    assert r["consultable"] is False
    assert r["motivo"] == "sin_id"
    assert "banco" in r["detalle"].lower()


def test_sin_token_configurado_lo_dice_en_vez_de_fallar(db, armar_empresa, monkeypatch):
    """En local no hay token de MP. La pantalla tiene que poder decir por qué
    no puede consultar, no mostrar un error rojo que no significa nada."""
    ctx = armar_empresa()
    pago = _pago(db, ctx)
    monkeypatch.setattr(mp_sus, "esta_activo", lambda: False)

    r = mp_sus.verificar(db, pago)
    assert r["consultable"] is False
    assert r["motivo"] == "mp_apagado"


def test_si_mp_no_responde_no_se_concluye_nada(db, armar_empresa, monkeypatch):
    """LA regla de seguridad. Un timeout NO puede leerse como «no está pago»:
    si de eso se dedujera algo, un rato de MP caído borraría cuotas buenas."""
    ctx = armar_empresa()
    pago = _pago(db, ctx)
    monkeypatch.setattr(mp_sus, "esta_activo", lambda: True)
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda _id: None)

    r = mp_sus.verificar(db, pago)
    assert r["consultable"] is False
    assert r["motivo"] == "sin_respuesta"
    assert r["acreditado"] is None, "None = no sabemos. Nunca False por un error de red."


# ══════════════════════════════════════════════════════════════════════
#  Lo que dice Mercado Pago
# ══════════════════════════════════════════════════════════════════════

def _con_respuesta(monkeypatch, estado, monto=19900):
    monkeypatch.setattr(mp_sus, "esta_activo", lambda: True)
    monkeypatch.setattr(
        mp_sus,
        "consultar_pago",
        lambda _id: {"status": estado, "transaction_amount": monto},
    )


def test_un_pago_aprobado_y_por_el_monto_correcto(db, armar_empresa, monkeypatch):
    ctx = armar_empresa()
    pago = _pago(db, ctx, monto=19900)
    _con_respuesta(monkeypatch, "approved", 19900)

    r = mp_sus.verificar(db, pago)
    assert r["acreditado"] is True
    assert r["coincide"] is True
    assert r["color"] == "verde"


@pytest.mark.parametrize("estado", ["refunded", "charged_back", "in_mediation"])
def test_la_plata_que_volvio_no_sigue_figurando_en_verde(
    db, armar_empresa, monkeypatch, estado
):
    """EL caso que motivó todo esto.

    Devuelto, contracargo y disputa son plata que ESTUVO y ya no está (o está
    por irse). Si se pintaran igual que «pendiente», el que mira el panel los
    trataría como «ya se va a acreditar» — y son exactamente lo contrario.
    """
    ctx = armar_empresa()
    pago = _pago(db, ctx)
    _con_respuesta(monkeypatch, estado)

    r = mp_sus.verificar(db, pago)
    assert r["acreditado"] is False
    assert r["color"] == "rojo", f"{estado} tiene que gritar, no informar."


@pytest.mark.parametrize("estado", ["pending", "in_process", "authorized"])
def test_lo_que_todavia_puede_acreditarse_se_distingue_de_lo_perdido(
    db, armar_empresa, monkeypatch, estado
):
    """Un `pending` puede aprobarse solo en unas horas; un `rejected` no se
    aprueba nunca. Tratarlos igual manda a perseguir a alguien que ya pagó."""
    ctx = armar_empresa()
    pago = _pago(db, ctx)
    _con_respuesta(monkeypatch, estado)

    r = mp_sus.verificar(db, pago)
    assert r["acreditado"] is False
    assert r["color"] == "ambar"


def test_aprobado_pero_por_otro_monto_se_marca(db, armar_empresa, monkeypatch):
    """El que nadie mira, porque el estado está en verde: MP aprobó $5.000 y
    nosotros anotamos $19.900. Cobrado sí; completo no."""
    ctx = armar_empresa()
    pago = _pago(db, ctx, monto=19900)
    _con_respuesta(monkeypatch, "approved", 5000)

    r = mp_sus.verificar(db, pago)
    assert r["acreditado"] is True
    assert r["coincide"] is False
    assert r["monto_mp"] == 5000
    assert r["monto_registrado"] == 19900


def test_un_estado_desconocido_no_rompe_la_pantalla(db, armar_empresa, monkeypatch):
    """Mercado Pago puede agregar estados. Uno nuevo tiene que salir gris y
    con su nombre, no tumbar el panel de cobranza."""
    ctx = armar_empresa()
    pago = _pago(db, ctx)
    _con_respuesta(monkeypatch, "un_estado_nuevo")

    r = mp_sus.verificar(db, pago)
    assert r["consultable"] is True
    assert r["color"] == "gris"
    assert r["estado_etiqueta"] == "un_estado_nuevo"


def test_verificar_no_toca_la_base(db, armar_empresa, monkeypatch):
    """De solo lectura, y esto lo fija. Si algún día alguien le agrega un
    `pago.anulado = True` cuando MP dice refunded, este test lo frena: esa
    decisión es de una persona, no de una respuesta HTTP."""
    ctx = armar_empresa()
    pago = _pago(db, ctx, monto=19900)
    _con_respuesta(monkeypatch, "refunded")

    mp_sus.verificar(db, pago)
    db.expire_all()
    vuelto = db.get(PagoSuscripcion, pago.id)
    assert vuelto.anulado is False
    assert float(vuelto.monto) == 19900


# ══════════════════════════════════════════════════════════════════════
#  El endpoint
# ══════════════════════════════════════════════════════════════════════

def test_el_endpoint_devuelve_lo_que_dice_mp(client, db, armar_empresa, admin, monkeypatch):
    ctx = armar_empresa()
    pago = _pago(db, ctx)
    db.commit()
    _con_respuesta(monkeypatch, "approved")

    r = client.get(f"/admin/pagos/{pago.id}/verificar-mp", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["acreditado"] is True


def test_un_pago_que_no_existe_da_404(client, admin):
    assert client.get("/admin/pagos/999999/verificar-mp", headers=admin).status_code == 404


def test_sin_ser_superadmin_no_se_puede_consultar(client, db, armar_empresa):
    """Los datos de cobranza del SaaS son de Turnos360, no del negocio."""
    ctx = armar_empresa()
    pago = _pago(db, ctx)
    db.commit()
    assert client.get(f"/admin/pagos/{pago.id}/verificar-mp").status_code in (401, 403)
