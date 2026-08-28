"""Cobro de la CUOTA del SaaS por Mercado Pago (fix-029).

Son DOS Mercado Pago distintos y la mitad de estos tests existen para que no se
mezclen nunca:

  · el MP de cada NEGOCIO cobra la seña de un turno a su cliente final;
  · el MP de TURNOS360 cobra la cuota mensual al negocio.

Un pago de cuota que se cuele por el webhook de señas —o al revés— sería plata
acreditada en la cuenta equivocada.

También se fija lo que más importa para el lanzamiento: **sin token configurado
el circuito entero está APAGADO**. En un staging por VPN los avisos de Mercado
Pago no llegan, y un cobro que entra y nadie acredita es peor que no ofrecer el
botón.
"""

import uuid

import pytest

from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import Empresa, PagoSuscripcion, SuperAdmin
from app.services import mp_suscripcion as mp_sus

from .conftest import token_de

PAGO_ID = "123456789"


@pytest.fixture()
def admin(db) -> dict:
    sa = SuperAdmin(
        nombre="Admin Test",
        email=f"sa-{uuid.uuid4().hex}@turnos360.test",
        hash_clave=hash_clave("clave1234"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


@pytest.fixture()
def mp_prendido(monkeypatch):
    """Enciende el cobro por MP sin salir a la red."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "mp_saas_access_token", "APP_USR-de-prueba")
    monkeypatch.setattr(settings, "mp_saas_webhook_secret", "")
    return settings


# ══════════════════════════════════════════════════════════════════════
#  Apagado por defecto
# ══════════════════════════════════════════════════════════════════════

def test_sin_token_el_cobro_por_mp_esta_apagado(client, armar_empresa):
    ctx = armar_empresa()
    r = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno))
    assert r.status_code == 200
    assert r.json()["cobro"]["mp_checkout"] is False, (
        "Sin token de la cuenta de Turnos360, el frontend NO tiene que ofrecer "
        "pagar con Mercado Pago."
    )


def test_sin_token_pedir_el_link_da_503(client, armar_empresa):
    ctx = armar_empresa()
    r = client.post("/empresa/suscripcion/pagar-mp", headers=token_de(ctx.dueno))
    assert r.status_code == 503


def test_sin_token_el_webhook_no_hace_nada(client, db, armar_empresa):
    """Y contesta 200: si no, Mercado Pago reintenta para siempre."""
    antes = db.query(PagoSuscripcion).count()
    r = client.post(
        f"/publico/mp/webhook-suscripcion?type=payment&data.id={PAGO_ID}"
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert db.query(PagoSuscripcion).count() == antes


def test_con_token_se_ofrece_el_checkout(client, armar_empresa, mp_prendido):
    ctx = armar_empresa()
    r = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno))
    assert r.json()["cobro"]["mp_checkout"] is True


# ══════════════════════════════════════════════════════════════════════
#  El webhook acredita la cuota
# ══════════════════════════════════════════════════════════════════════

def _pago_mp(empresa_id, monto=14990.0, estado="approved"):
    return {
        "id": int(PAGO_ID),
        "status": estado,
        "transaction_amount": monto,
        "external_reference": f"sus:{empresa_id}",
    }


def test_un_pago_aprobado_registra_la_cuota_y_renueva(
    client, db, armar_empresa, monkeypatch, mp_prendido
):
    ctx = armar_empresa()
    vencia = ctx.empresa.suscripcion_vence
    monkeypatch.setattr(
        mp_sus, "consultar_pago", lambda pid: _pago_mp(ctx.empresa.id)
    )

    r = client.post(
        f"/publico/mp/webhook-suscripcion?type=payment&data.id={PAGO_ID}"
    )
    assert r.status_code == 200
    db.expire_all()

    pago = db.query(PagoSuscripcion).filter_by(mp_payment_id=PAGO_ID).one()
    assert pago.empresa_id == ctx.empresa.id
    assert pago.metodo == "mercadopago"
    assert float(pago.monto) == 14990.0
    assert db.get(Empresa, ctx.empresa.id).suscripcion_vence != vencia


def test_la_misma_notificacion_dos_veces_no_renueva_dos_veces(
    client, db, armar_empresa, monkeypatch, mp_prendido
):
    """Mercado Pago reintenta. Sin idempotencia, cada reintento son 30 días más."""
    ctx = armar_empresa()
    monkeypatch.setattr(
        mp_sus, "consultar_pago", lambda pid: _pago_mp(ctx.empresa.id)
    )
    url = f"/publico/mp/webhook-suscripcion?type=payment&data.id={PAGO_ID}"

    client.post(url)
    db.expire_all()
    vence_1 = db.get(Empresa, ctx.empresa.id).suscripcion_vence

    client.post(url)
    client.post(url)
    db.expire_all()

    assert db.query(PagoSuscripcion).filter_by(mp_payment_id=PAGO_ID).count() == 1
    assert db.get(Empresa, ctx.empresa.id).suscripcion_vence == vence_1


def test_un_pago_no_aprobado_no_acredita(
    client, db, armar_empresa, monkeypatch, mp_prendido
):
    ctx = armar_empresa()
    monkeypatch.setattr(
        mp_sus,
        "consultar_pago",
        lambda pid: _pago_mp(ctx.empresa.id, estado="rejected"),
    )
    client.post(f"/publico/mp/webhook-suscripcion?type=payment&data.id={PAGO_ID}")
    db.expire_all()
    assert db.query(PagoSuscripcion).filter_by(mp_payment_id=PAGO_ID).count() == 0


def test_un_pago_inventado_no_acredita(
    client, db, armar_empresa, monkeypatch, mp_prendido
):
    """La API de MP no lo conoce: consultar_pago devuelve None."""
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda pid: None)
    antes = db.query(PagoSuscripcion).count()
    client.post("/publico/mp/webhook-suscripcion?type=payment&data.id=999999999")
    assert db.query(PagoSuscripcion).count() == antes


def test_un_id_no_numerico_muere_antes_de_tocar_la_red(
    client, db, monkeypatch, mp_prendido
):
    """El amplificador de tráfico saliente: mismo blindaje que el de señas."""
    llamadas = []
    monkeypatch.setattr(
        mp_sus, "consultar_pago", lambda pid: llamadas.append(pid) or None
    )
    r = client.post(
        "/publico/mp/webhook-suscripcion?type=payment&data.id=' OR 1=1--"
    )
    assert r.status_code == 200
    assert llamadas == [], "No tiene que salir a la API por un id que no es un número."


# ══════════════════════════════════════════════════════════════════════
#  Que no se mezclen las dos cuentas
# ══════════════════════════════════════════════════════════════════════

def test_un_pago_de_sena_no_entra_como_cuota(
    client, db, armar_empresa, monkeypatch, mp_prendido
):
    """external_reference de una seña es un id de turno pelado, sin "sus:"."""
    armar_empresa()  # una empresa cualquiera en la base
    monkeypatch.setattr(
        mp_sus,
        "consultar_pago",
        lambda pid: {
            "id": int(PAGO_ID),
            "status": "approved",
            "transaction_amount": 5000,
            "external_reference": "42",  # un turno, no una suscripción
        },
    )
    antes = db.query(PagoSuscripcion).count()
    client.post(f"/publico/mp/webhook-suscripcion?type=payment&data.id={PAGO_ID}")
    assert db.query(PagoSuscripcion).count() == antes


def test_una_referencia_a_una_empresa_que_no_existe_no_rompe(
    client, db, monkeypatch, mp_prendido
):
    monkeypatch.setattr(
        mp_sus, "consultar_pago", lambda pid: _pago_mp(999_999_999)
    )
    r = client.post(
        f"/publico/mp/webhook-suscripcion?type=payment&data.id={PAGO_ID}"
    )
    assert r.status_code == 200


def test_la_referencia_se_arma_y_se_lee_igual():
    assert mp_sus.empresa_de_referencia(mp_sus.referencia_de(77)) == 77
    assert mp_sus.empresa_de_referencia("42") is None
    assert mp_sus.empresa_de_referencia(None) is None
    assert mp_sus.empresa_de_referencia("sus:no") is None


# ══════════════════════════════════════════════════════════════════════
#  Aviso de transferencia
# ══════════════════════════════════════════════════════════════════════

def test_avisar_transferencia_no_mueve_el_vencimiento(client, db, armar_empresa):
    """Una transferencia tarda en verse: no se da por cobrada porque alguien lo diga."""
    ctx = armar_empresa()
    vencia = ctx.empresa.suscripcion_vence

    r = client.post(
        "/empresa/suscripcion/aviso-pago",
        headers=token_de(ctx.dueno),
        json={"monto": 14990, "referencia": "Transferencia 0001"},
    )
    assert r.status_code == 200
    assert "24 horas" in r.json()["detalle"]

    db.expire_all()
    assert db.get(Empresa, ctx.empresa.id).suscripcion_vence == vencia


def test_avisar_dos_veces_no_genera_dos_pendientes(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    for _ in range(3):
        client.post(
            "/empresa/suscripcion/aviso-pago",
            headers=token_de(ctx.dueno),
            json={"monto": 14990},
        )
    avisos = client.get("/admin/cobranza/avisos", headers=admin).json()
    mios = [a for a in avisos if a["empresa_id"] == ctx.empresa.id]
    assert len(mios) == 1


def test_el_aviso_aparece_en_la_bandeja_del_admin(client, armar_empresa, admin):
    ctx = armar_empresa()
    client.post(
        "/empresa/suscripcion/aviso-pago",
        headers=token_de(ctx.dueno),
        json={"monto": 14990, "referencia": "op 12345"},
    )
    avisos = client.get("/admin/cobranza/avisos", headers=admin).json()
    mio = [a for a in avisos if a["empresa_id"] == ctx.empresa.id][0]
    assert mio["referencia"] == "op 12345"
    assert mio["empresa_nombre"] == ctx.empresa.nombre


def test_registrar_la_cuota_saca_el_aviso_de_la_bandeja(client, armar_empresa, admin):
    ctx = armar_empresa()
    client.post(
        "/empresa/suscripcion/aviso-pago",
        headers=token_de(ctx.dueno),
        json={"monto": 14990},
    )
    client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 14990, "metodo": "transferencia", "renovar": True},
    )
    avisos = client.get("/admin/cobranza/avisos", headers=admin).json()
    assert [a for a in avisos if a["empresa_id"] == ctx.empresa.id] == []


def test_el_dueno_ve_que_su_aviso_esta_pendiente(client, armar_empresa):
    ctx = armar_empresa()
    r = client.get("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno))
    assert r.json()["pendiente"] is False

    client.post(
        "/empresa/suscripcion/aviso-pago",
        headers=token_de(ctx.dueno),
        json={"monto": 14990},
    )
    r = client.get("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno))
    assert r.json()["pendiente"] is True


def test_solo_el_dueno_avisa_pagos(client, armar_empresa):
    """Avisar un pago es un acto comercial del negocio, no operativo."""
    ctx = armar_empresa()
    r = client.post(
        "/empresa/suscripcion/aviso-pago",
        headers=token_de(ctx.profesional),
        json={"monto": 14990},
    )
    assert r.status_code in (401, 403)

    r = client.post("/empresa/suscripcion/aviso-pago", json={"monto": 14990})
    assert r.status_code == 401
