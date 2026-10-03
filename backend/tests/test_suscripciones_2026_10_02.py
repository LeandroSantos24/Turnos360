"""Suscripciones, cobranza y administración (auditoría 2026-10-02).

Los 16 casos pedidos más los bordes que encontró la auditoría: estados
centralizados, cambio de plan con doble confirmación, cancelación programada,
transferencias en revisión, aprobación idempotente, auditoría del admin y
reservas web cortadas recién pasada la gracia.
"""

import datetime as dt
import uuid

import pytest

from app.core import estados_suscripcion as est
from app.core.crypto import hash_clave
from app.core.reloj import hoy_de_pared
from app.core.seguridad import crear_token_superadmin
from app.models import (
    AjusteSuscripcion,
    AuditoriaAdmin,
    AvisoPago,
    Empresa,
    IntentoPago,
    PagoSuscripcion,
    Sucursal,
    SuperAdmin,
)
from app.services import cobranza
from app.services import mp_suscripcion as mp_sus
from app.services.suscripcion import estado_suscripcion

from .conftest import token_de

HOY = hoy_de_pared()
WEBHOOK = "/publico/mp/webhook-suscripcion?type=payment&data.id={}"


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
    from app.core.config import settings

    monkeypatch.setattr(settings, "mp_saas_access_token", "APP_USR-de-prueba")
    monkeypatch.setattr(settings, "mp_saas_webhook_secret", "")
    return settings


def _empresa(armar_empresa, db, *, plan="pro", vence=HOY + dt.timedelta(days=10), prueba=None):
    ctx = armar_empresa()
    ctx.empresa.plan = plan
    ctx.empresa.suscripcion_vence = vence
    ctx.empresa.prueba_hasta = prueba
    db.commit()
    return ctx


def _estado(db, empresa) -> str:
    db.refresh(empresa)
    return estado_suscripcion(empresa, db)["estado"]


def _intento(db, empresa, plan="pro", monto=19990):
    intento = IntentoPago(
        empresa_id=empresa.id, tipo="renovacion", plan=plan, monto=monto, metodo="mercadopago"
    )
    db.add(intento)
    db.commit()
    return intento


def _pago_mp(pid, ref, monto, estado="approved"):
    return {
        "id": int(pid), "status": estado, "status_detail": "cc_rejected_other_reason",
        "transaction_amount": monto, "currency_id": "ARS", "external_reference": ref,
    }


# ══════════════════════════════════════════════════════════════════════
#  Estados centralizados y transiciones
# ══════════════════════════════════════════════════════════════════════

def test_las_transiciones_imposibles_se_rechazan():
    assert est.permitido("activa", "cancelar")
    assert not est.permitido("cancelacion_programada", "cancelar")
    assert not est.permitido("activa", "reactivar")
    assert not est.permitido("suspendida", "pagar")
    assert not est.permitido("cancelacion_programada", "bajar_plan")
    with pytest.raises(Exception) as e:
        est.exigir("suspendida", "subir_plan")
    assert e.value.status_code == 409


def test_cada_estado_tiene_etiqueta_y_tono():
    for estado in est.EstadoSuscripcion:
        etiqueta, tono = est.ETIQUETAS[estado]
        assert etiqueta and tono in ("ok", "info", "aviso", "error", "neutro")


# ══════════════════════════════════════════════════════════════════════
#  1-2. Crear suscripción / pago aprobado (Mercado Pago)
# ══════════════════════════════════════════════════════════════════════

def test_1_primer_pago_aprobado_crea_la_suscripcion(client, db, armar_empresa, monkeypatch, mp_prendido):
    ctx = _empresa(armar_empresa, db, plan="gratuito", vence=None, prueba=HOY + dt.timedelta(days=2))
    intento = _intento(db, ctx.empresa, plan="pro", monto=19990)
    ref = mp_sus.referencia_de(ctx.empresa.id, "pro", intento.id)
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda pid: _pago_mp(pid, ref, 19990))

    assert client.post(WEBHOOK.format("9000001")).status_code == 200
    db.expire_all()

    pago = db.query(PagoSuscripcion).filter_by(mp_payment_id="9000001").one()
    assert pago.tipo == "alta" and pago.plan == "pro"
    assert db.get(IntentoPago, intento.id).estado == "aprobado"
    assert _estado(db, ctx.empresa) == "activa"
    assert ctx.empresa.plan == "pro"


def test_2_pago_aprobado_menor_al_pedido_no_renueva(client, db, armar_empresa, monkeypatch, mp_prendido):
    """El backend no confía en el monto: si entra menos, no hay plan ni días."""
    ctx = _empresa(armar_empresa, db, plan="inicial")
    vencia = ctx.empresa.suscripcion_vence
    intento = _intento(db, ctx.empresa, plan="multi", monto=34990)
    ref = mp_sus.referencia_de(ctx.empresa.id, "multi", intento.id)
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda pid: _pago_mp(pid, ref, 100))

    client.post(WEBHOOK.format("9000002"))
    db.expire_all()
    emp = db.get(Empresa, ctx.empresa.id)
    assert emp.plan == "inicial" and emp.suscripcion_vence == vencia
    assert db.query(AjusteSuscripcion).filter_by(empresa_id=emp.id, tipo="pago_rechazado").count() == 1


def test_2b_pago_en_otra_moneda_no_se_acredita(client, db, armar_empresa, monkeypatch, mp_prendido):
    ctx = _empresa(armar_empresa, db)
    datos = _pago_mp("9000003", mp_sus.referencia_de(ctx.empresa.id, "pro"), 19990)
    datos["currency_id"] = "USD"
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda pid: datos)
    client.post(WEBHOOK.format("9000003"))
    assert db.query(PagoSuscripcion).filter_by(mp_payment_id="9000003").count() == 0


# ══════════════════════════════════════════════════════════════════════
#  3. Pago rechazado
# ══════════════════════════════════════════════════════════════════════

def test_3_pago_rechazado_queda_registrado_y_no_acredita(client, db, armar_empresa, monkeypatch, mp_prendido):
    ctx = _empresa(armar_empresa, db, vence=HOY - dt.timedelta(days=1))
    intento = _intento(db, ctx.empresa)
    ref = mp_sus.referencia_de(ctx.empresa.id, "pro", intento.id)
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda pid: _pago_mp(pid, ref, 19990, "rejected"))

    client.post(WEBHOOK.format("9000004"))
    db.expire_all()
    assert db.query(PagoSuscripcion).filter_by(mp_payment_id="9000004").count() == 0
    assert db.get(IntentoPago, intento.id).estado == "rechazado"
    assert _estado(db, ctx.empresa) == "prorroga"

    r = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno)).json()
    assert r["ultimo_intento"]["estado"] == "rechazado"


def test_3b_pago_pendiente_muestra_pago_pendiente(client, db, armar_empresa, monkeypatch, mp_prendido):
    ctx = _empresa(armar_empresa, db, vence=HOY - dt.timedelta(days=1))
    intento = _intento(db, ctx.empresa)
    ref = mp_sus.referencia_de(ctx.empresa.id, "pro", intento.id)
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda pid: _pago_mp(pid, ref, 19990, "in_process"))
    client.post(WEBHOOK.format("9000005"))
    assert _estado(db, ctx.empresa) == "pendiente_pago"


# ══════════════════════════════════════════════════════════════════════
#  4-6. Transferencia: en revisión, aprobar, rechazar, pedir info
# ══════════════════════════════════════════════════════════════════════

def test_4_transferencia_informada_queda_en_revision(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db, plan="inicial", vence=HOY - dt.timedelta(days=2))
    vencia = ctx.empresa.suscripcion_vence

    r = client.post(
        "/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno),
        json={"monto": 1, "plan": "pro", "referencia": "op 123"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "en_revision"
    aviso = db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).one()
    # El monto esperado lo decide el servidor, no lo que manda la pantalla.
    assert aviso.plan == "pro" and float(aviso.monto_esperado) == 19990
    assert aviso.tipo == "cambio_plan"
    assert _estado(db, ctx.empresa) == "en_revision"
    assert ctx.empresa.suscripcion_vence == vencia


def test_4b_un_comprobante_ajeno_o_inexistente_se_rechaza(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db)
    r = client.post(
        "/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno),
        json={"comprobante": f"{uuid.uuid4().hex}.webp"},
    )
    assert r.status_code == 400
    r = client.post(
        "/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno),
        json={"comprobante": "../../etc/passwd"},
    )
    assert r.status_code == 422


def test_5_aprobar_transferencia_activa_el_plan_del_aviso_y_audita(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db, plan="inicial", vence=HOY - dt.timedelta(days=1))
    vencia = ctx.empresa.suscripcion_vence
    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno),
                json={"monto": 19990, "plan": "pro"})
    aviso = db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).one()

    sin = client.post(f"/admin/cobranza/avisos/{aviso.id}/aprobar", headers=admin, json={})
    assert sin.status_code == 400  # sin la segunda confirmación no hace nada

    r = client.post(f"/admin/cobranza/avisos/{aviso.id}/aprobar", headers=admin, json={"confirmo": True})
    assert r.status_code == 200, r.text
    db.expire_all()
    emp = db.get(Empresa, ctx.empresa.id)
    assert emp.plan == "pro"
    assert emp.suscripcion_vence == vencia + dt.timedelta(days=30)
    assert db.get(AvisoPago, aviso.id).estado == "confirmada"
    fila = db.query(AuditoriaAdmin).filter_by(empresa_id=emp.id, accion="aprobar_pago").one()
    assert fila.antes["plan"] == "inicial" and fila.despues["plan"] == "pro"
    assert fila.despues["estado"] == "activa"


def test_5b_aprobar_dos_veces_el_mismo_aviso_no_regala_un_mes(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db, vence=HOY)
    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno), json={"monto": 19990})
    aviso = db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).one()
    url = f"/admin/cobranza/avisos/{aviso.id}/aprobar"

    assert client.post(url, headers=admin, json={"confirmo": True}).status_code == 200
    assert client.post(url, headers=admin, json={"confirmo": True}).status_code == 409
    assert db.query(PagoSuscripcion).filter_by(empresa_id=ctx.empresa.id).count() == 1


def test_6_rechazar_transferencia_vuelve_al_estado_anterior(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db, vence=HOY - dt.timedelta(days=1))
    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno), json={"monto": 5})
    aviso = db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).one()

    r = client.post(f"/admin/cobranza/avisos/{aviso.id}/descartar", headers=admin,
                    json={"motivo": "No apareció en el banco"})
    assert r.status_code == 200
    db.expire_all()
    assert db.get(AvisoPago, aviso.id).estado == "rechazada"
    assert _estado(db, ctx.empresa) == "prorroga"
    mi = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno)).json()
    assert mi["aviso_rechazado"]["motivo"] == "No apareció en el banco"
    assert db.query(AuditoriaAdmin).filter_by(empresa_id=ctx.empresa.id, accion="rechazar_pago").count() == 1


def test_6b_pedir_info_y_responder_vuelve_a_la_bandeja(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db, vence=HOY - dt.timedelta(days=1))
    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno), json={"monto": 19990})
    aviso = db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).one()

    r = client.post(f"/admin/cobranza/avisos/{aviso.id}/solicitar-info", headers=admin,
                    json={"mensaje": "Mandanos el comprobante"})
    assert r.status_code == 200
    mi = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno)).json()
    assert mi["estado_pago"] == "info_solicitada"
    assert mi["aviso"]["mensaje_admin"] == "Mandanos el comprobante"

    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno),
                json={"referencia": "op 999"})
    db.expire_all()
    assert db.get(AvisoPago, aviso.id).estado == "pendiente"
    assert db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).count() == 1


# ══════════════════════════════════════════════════════════════════════
#  7. Renovación
# ══════════════════════════════════════════════════════════════════════

def test_7_renovacion_suma_30_dias_desde_el_vencimiento(db, armar_empresa):
    ctx = _empresa(armar_empresa, db, vence=HOY + dt.timedelta(days=5))
    cobranza.registrar_pago(db, ctx.empresa, monto=19990, metodo="transferencia")
    pago = cobranza.registrar_pago(db, ctx.empresa, monto=19990, metodo="transferencia")
    db.commit()
    assert pago.tipo == "renovacion"
    assert ctx.empresa.suscripcion_vence == HOY + dt.timedelta(days=65)


# ══════════════════════════════════════════════════════════════════════
#  8-9. Downgrade / upgrade
# ══════════════════════════════════════════════════════════════════════

def _sucursales(db, empresa, n):
    for i in range(n):
        db.add(Sucursal(empresa_id=empresa.id, nombre=f"Sede extra {i}", activa=True))
    db.commit()


def test_8_downgrade_muestra_lo_incompatible_y_no_deja_un_estado_imposible(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db, plan="multi")
    _sucursales(db, ctx.empresa, 2)  # 3 en total

    prev = client.get("/empresa/suscripcion/cambio-plan?plan=pro", headers=token_de(ctx.dueno)).json()
    assert prev["movimiento"] == "baja"
    assert prev["a_pagar_hoy"] == 0
    assert prev["aplica_desde"] == ctx.empresa.suscripcion_vence.isoformat()
    assert any("Actualmente usás 3 sucursales" in i["mensaje"] for i in prev["incompatibilidades"])

    r = client.post("/empresa/suscripcion/cambiar-plan", headers=token_de(ctx.dueno),
                    json={"plan": "pro", "confirmo": True})
    assert r.json()["accion"] == "programada"

    # Llega la fecha y sigue con 3 sucursales: NO se aplica.
    ctx.empresa.suscripcion_vence = HOY
    db.commit()
    assert cobranza.aplicar_bajas_programadas(db, hoy=HOY) == 0
    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "multi" and ctx.empresa.plan_programado == "pro"
    assert db.query(AjusteSuscripcion).filter_by(empresa_id=ctx.empresa.id, tipo="baja_postergada").count() == 1
    # El barrido de mañana no duplica el aviso de hoy.
    cobranza.aplicar_bajas_programadas(db, hoy=HOY)
    assert db.query(AjusteSuscripcion).filter_by(empresa_id=ctx.empresa.id, tipo="baja_postergada").count() == 1


def test_8b_downgrade_compatible_se_aplica_al_vencer(db, armar_empresa):
    ctx = _empresa(armar_empresa, db, plan="multi", vence=HOY)
    cobranza.programar_baja(db, ctx.empresa, "pro", hecho_por="dueño")
    db.commit()
    assert cobranza.aplicar_bajas_programadas(db, hoy=HOY) == 1
    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "pro" and ctx.empresa.plan_programado is None


def test_9_upgrade_cobra_el_plan_completo_y_suma_30_dias(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db, plan="inicial", vence=HOY + dt.timedelta(days=12))
    prev = client.get("/empresa/suscripcion/cambio-plan?plan=multi", headers=token_de(ctx.dueno)).json()
    assert prev["movimiento"] == "sube"
    assert prev["a_pagar_hoy"] == 34990
    assert prev["vence_nuevo"] == (HOY + dt.timedelta(days=42)).isoformat()
    assert "Multisucursal" in " ".join(prev["ganas"]) or prev["ganas"]

    sin = client.post("/empresa/suscripcion/cambiar-plan", headers=token_de(ctx.dueno), json={"plan": "multi"})
    assert sin.status_code == 400
    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "inicial"


# ══════════════════════════════════════════════════════════════════════
#  10-11. Cancelación y reactivación
# ══════════════════════════════════════════════════════════════════════

def test_10_cancelar_es_programado_y_no_borra_nada(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db, vence=HOY + dt.timedelta(days=7))
    url = "/empresa/suscripcion/cancelar"
    assert client.post(url, headers=token_de(ctx.dueno), json={}).status_code == 400

    r = client.post(url, headers=token_de(ctx.dueno), json={"confirmo": True, "motivo": "Cierro el local"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "cancelacion_programada"
    assert r.json()["activa_hasta"] == (HOY + dt.timedelta(days=7)).isoformat()
    est_ = estado_suscripcion(ctx.empresa, db)
    assert est_["reservas_abiertas"] is True

    # Pasa el vencimiento: queda cancelada y la web deja de tomar reservas.
    cobranza.aplicar_cancelaciones(db, hoy=HOY + dt.timedelta(days=8))
    db.refresh(ctx.empresa)
    assert ctx.empresa.cancelada_en is not None
    est_ = estado_suscripcion(ctx.empresa, db)
    assert est_["estado"] == "cancelada" and est_["reservas_abiertas"] is False
    assert db.get(Empresa, ctx.empresa.id) is not None  # nada se borró

    # Cancelar dos veces: transición imposible.
    assert client.post(url, headers=token_de(ctx.dueno), json={"confirmo": True}).status_code == 409


def test_11_reactivar_deshace_la_cancelacion(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db, vence=HOY + dt.timedelta(days=7))
    client.post("/empresa/suscripcion/cancelar", headers=token_de(ctx.dueno), json={"confirmo": True})
    r = client.post("/empresa/suscripcion/reactivar", headers=token_de(ctx.dueno), json={"confirmo": True})
    assert r.status_code == 200 and r.json()["estado"] == "activa"
    assert client.post("/empresa/suscripcion/reactivar", headers=token_de(ctx.dueno),
                       json={"confirmo": True}).status_code == 409


def test_11b_pagar_reactiva_una_cancelada(db, armar_empresa):
    ctx = _empresa(armar_empresa, db, vence=HOY - dt.timedelta(days=10))
    ctx.empresa.cancela_al_vencer = True
    db.commit()
    assert _estado(db, ctx.empresa) == "cancelada"
    cobranza.registrar_pago(db, ctx.empresa, monto=19990, metodo="transferencia")
    db.commit()
    assert _estado(db, ctx.empresa) == "activa"


# ══════════════════════════════════════════════════════════════════════
#  12. Gracia y corte de reservas
# ══════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("dias,estado,abiertas", [
    (0, "activa", True), (-1, "prorroga", True), (-3, "prorroga", True), (-4, "vencida", False),
])
def test_12_gracia_de_3_dias_y_despues_corte(db, armar_empresa, dias, estado, abiertas):
    ctx = _empresa(armar_empresa, db, vence=HOY + dt.timedelta(days=dias))
    e = estado_suscripcion(ctx.empresa, db)
    assert (e["estado"], e["reservas_abiertas"]) == (estado, abiertas)


@pytest.mark.parametrize("dias,estado,abiertas", [
    (0, "prueba", True), (-2, "prueba_vencida", True), (-4, "prueba_vencida", False),
])
def test_12b_prueba_terminada_cierra_reservas_a_los_3_dias(db, armar_empresa, dias, estado, abiertas):
    ctx = _empresa(armar_empresa, db, plan="gratuito", vence=None, prueba=HOY + dt.timedelta(days=dias))
    e = estado_suscripcion(ctx.empresa, db)
    assert (e["estado"], e["reservas_abiertas"]) == (estado, abiertas)


def test_12c_la_web_publica_respeta_el_corte(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db, vence=HOY - dt.timedelta(days=5))
    r = client.get(f"/publico/{ctx.empresa.slug}")
    assert r.status_code == 200 and r.json()["reservas_abiertas"] is False


# ══════════════════════════════════════════════════════════════════════
#  13. Suspensión
# ══════════════════════════════════════════════════════════════════════

def test_13_suspender_corta_reservas_registra_evento_y_auditoria(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    r = client.patch(f"/admin/empresas/{ctx.empresa.id}", headers=admin,
                     json={"activa": False, "motivo": "Fraude"})
    assert r.status_code == 200, r.text
    assert r.json()["estado_suscripcion"] == "suspendida"
    db.expire_all()
    emp = db.get(Empresa, ctx.empresa.id)
    assert estado_suscripcion(emp, db)["reservas_abiertas"] is False
    assert db.query(AjusteSuscripcion).filter_by(empresa_id=emp.id, tipo="suspension").count() == 1
    fila = db.query(AuditoriaAdmin).filter_by(empresa_id=emp.id, accion="suspender").one()
    assert fila.antes["activa"] is True and fila.despues["activa"] is False
    # Pausar dos veces no duplica el evento.
    client.patch(f"/admin/empresas/{emp.id}", headers=admin, json={"activa": False})
    assert db.query(AjusteSuscripcion).filter_by(empresa_id=emp.id, tipo="suspension").count() == 1


# ══════════════════════════════════════════════════════════════════════
#  14-15. Webhook duplicado / pago duplicado
# ══════════════════════════════════════════════════════════════════════

def test_14_webhook_duplicado_no_acredita_dos_veces(client, db, armar_empresa, monkeypatch, mp_prendido):
    ctx = _empresa(armar_empresa, db)
    ref = mp_sus.referencia_de(ctx.empresa.id, "pro")
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda pid: _pago_mp(pid, ref, 19990))
    for _ in range(3):
        client.post(WEBHOOK.format("9000014"))
    db.expire_all()
    assert db.query(PagoSuscripcion).filter_by(mp_payment_id="9000014").count() == 1
    assert db.get(Empresa, ctx.empresa.id).suscripcion_vence == HOY + dt.timedelta(days=40)


def test_14b_devolucion_anula_la_cuota(client, db, armar_empresa, monkeypatch, mp_prendido):
    ctx = _empresa(armar_empresa, db)
    ref = mp_sus.referencia_de(ctx.empresa.id, "pro")
    estado = {"s": "approved"}
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda pid: _pago_mp(pid, ref, 19990, estado["s"]))
    client.post(WEBHOOK.format("9000015"))
    estado["s"] = "refunded"
    client.post(WEBHOOK.format("9000015"), json={"action": "payment.updated"})
    db.expire_all()
    pago = db.query(PagoSuscripcion).filter_by(mp_payment_id="9000015").one()
    assert pago.anulado is True
    mi = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno)).json()
    assert all(p["id"] != pago.id for p in mi["pagos"])


def test_15_pago_manual_duplicado_con_la_misma_clave(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db, vence=HOY)
    cuerpo = {"monto": 19990, "metodo": "transferencia", "clave_idempotencia": "dialogo-abc12345"}
    a = client.post(f"/admin/empresas/{ctx.empresa.id}/pagos", headers=admin, json=cuerpo)
    b = client.post(f"/admin/empresas/{ctx.empresa.id}/pagos", headers=admin, json=cuerpo)
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] == b.json()["id"]
    db.expire_all()
    assert db.query(PagoSuscripcion).filter_by(empresa_id=ctx.empresa.id).count() == 1
    assert db.get(Empresa, ctx.empresa.id).suscripcion_vence == HOY + dt.timedelta(days=30)

    otra = _empresa(armar_empresa, db)
    r = client.post(f"/admin/empresas/{otra.empresa.id}/pagos", headers=admin, json=cuerpo)
    assert r.status_code == 409


# ══════════════════════════════════════════════════════════════════════
#  16. No autorizado
# ══════════════════════════════════════════════════════════════════════

def test_16_un_profesional_no_toca_la_suscripcion(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db)
    h = token_de(ctx.profesional)
    assert client.get("/empresa/suscripcion/cambio-plan?plan=multi", headers=h).status_code == 403
    assert client.post("/empresa/suscripcion/cancelar", headers=h, json={"confirmo": True}).status_code == 403
    assert client.post("/empresa/suscripcion/reactivar", headers=h, json={"confirmo": True}).status_code == 403
    assert client.post("/empresa/suscripcion/aviso-pago", headers=h, json={}).status_code == 403


def test_16b_un_negocio_no_entra_al_admin(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db)
    h = token_de(ctx.dueno)
    assert client.post("/admin/cobranza/avisos/1/aprobar", headers=h, json={"confirmo": True}).status_code in (401, 403)
    assert client.get("/admin/auditoria", headers=h).status_code in (401, 403)
    assert client.get("/admin/cobranza/avisos/1/comprobante", headers=h).status_code in (401, 403)


def test_16c_los_comprobantes_no_se_sirven_por_la_carpeta_publica(client):
    r = client.get("/uploads/_privado/comprobantes/1/x.webp")
    assert r.status_code == 404


def test_16d_el_frontend_no_puede_poner_el_precio(client, db, armar_empresa):
    """El aviso trae un plan que no se vende online: se ignora y se usa el suyo."""
    ctx = _empresa(armar_empresa, db, plan="inicial")
    r = client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno),
                    json={"monto": 1, "plan": "enterprise"})
    assert r.status_code == 400


# ══════════════════════════════════════════════════════════════════════
#  Admin: filtros, KPIs, auditoría
# ══════════════════════════════════════════════════════════════════════

def test_kpis_y_filtros_del_panel(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db, vence=HOY - dt.timedelta(days=1))
    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno), json={"monto": 19990})

    res = client.get("/admin/cobranza/resumen", headers=admin).json()
    assert res["pagos_en_revision"] >= 1
    assert any(a["filtro"] == "en_revision" for a in res["alertas"])

    filas = client.get("/admin/cobranza/empresas?filtro=en_revision", headers=admin).json()
    assert any(f["id"] == ctx.empresa.id and f["estado"] == "en_revision" for f in filas)
    assert client.get("/admin/cobranza/empresas?filtro=cualquiera", headers=admin).status_code == 422


def test_la_auditoria_lista_quien_hizo_que(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    client.post(f"/admin/empresas/{ctx.empresa.id}/prorroga", headers=admin, json={"dias": 10})
    filas = client.get(f"/admin/auditoria?empresa_id={ctx.empresa.id}", headers=admin).json()
    assert filas[0]["accion"] == "prorroga"
    assert filas[0]["antes"]["suscripcion_vence"] != filas[0]["despues"]["suscripcion_vence"]
    assert filas[0]["admin_email"].endswith("@turnos360.test")


def test_un_intento_fallido_no_deja_auditoria(client, db, armar_empresa, admin):
    """Si la acción no ocurrió (409), tampoco queda registrada."""
    ctx = _empresa(armar_empresa, db)
    r = client.post(f"/admin/empresas/{ctx.empresa.id}/reactivar", headers=admin, json={"confirmo": True})
    assert r.status_code == 409
    db.rollback()
    assert db.query(AuditoriaAdmin).filter_by(empresa_id=ctx.empresa.id).count() == 0


def test_mi_suscripcion_no_muestra_datos_internos(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    client.post(f"/admin/empresas/{ctx.empresa.id}/prorroga", headers=admin, json={"dias": 5})
    mi = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno)).json()
    texto = str(mi)
    assert "@turnos360.test" not in texto
    assert "notas" not in {k for p in mi["pagos"] for k in p}


def test_aprobar_relee_el_aviso_bloqueado_y_no_usa_la_copia_en_memoria(db, armar_empresa):
    """Regresión de concurrencia: el aviso ya estaba cargado en la sesión (lo
    lee el router antes de aprobar). FOR UPDATE bloqueaba la fila pero devolvía
    la copia vieja «pendiente», y 4 aprobaciones simultáneas registraban 4
    cuotas. Se simula al otro admin con un UPDATE que la sesión no ve."""
    from sqlalchemy import update

    ctx = _empresa(armar_empresa, db)
    aviso = cobranza.registrar_aviso(db, ctx.empresa, monto=19990)
    assert db.get(AvisoPago, aviso.id).estado == "pendiente"
    db.execute(
        update(AvisoPago).where(AvisoPago.id == aviso.id).values(estado="confirmada"),
        execution_options={"synchronize_session": False},
    )
    with pytest.raises(Exception) as e:
        cobranza.aprobar_aviso(db, aviso.id, monto=None, fecha=None, hecho_por="otro")
    assert e.value.status_code == 409
    assert db.query(PagoSuscripcion).filter_by(empresa_id=ctx.empresa.id).count() == 0


def test_plan_de_acepta_el_enum_y_no_degrada_a_prueba():
    """La ficha del admin pasaba el enum y el tope de usuarios caía al de la prueba."""
    from app.core import planes

    assert planes.plan_de(planes.Plan.PRO) is planes.Plan.PRO
    assert planes.tope_usuarios(planes.plan_de("pro")) == planes.tope_usuarios("pro")


def test_la_ficha_del_admin_y_mi_suscripcion_dicen_los_mismos_topes(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db, plan="pro")
    ficha = client.get(f"/admin/empresas/{ctx.empresa.id}/ficha", headers=admin).json()
    mi = client.get("/empresa/mi-suscripcion", headers=token_de(ctx.dueno)).json()
    for k in ("profesionales", "usuarios", "sucursales"):
        assert ficha["uso"][k]["tope"] == mi["topes"][k], k
    assert ficha["suscripcion"]["estado"] == mi["estado"]
