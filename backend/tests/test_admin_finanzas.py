"""Panel del super-admin: cobros, devoluciones, conciliación, caja, cierres,
estadísticas, estado de Mercado Pago, usuarios y auditoría.

Nada sale a la red: las llamadas a Mercado Pago se reemplazan por funciones
de prueba. Ningún test genera un cobro ni una devolución real.
"""

import datetime as dt
import uuid

import pytest
from sqlalchemy import func, select

from app.core.crypto import hash_clave
from app.core.reloj import hoy_de_pared
from app.core.seguridad import crear_token_superadmin
from app.models import (
    AuditoriaAdmin,
    AvisoPago,
    DevolucionSuscripcion,
    EventoMP,
    IntentoPago,
    PagoSuscripcion,
    SuperAdmin,
    Usuario,
)
from app.services import admin_finanzas as fin
from app.services import cobranza
from app.services import mp_suscripcion as mp_sus

from .conftest import token_de

HOY = hoy_de_pared()
AYER = HOY - dt.timedelta(days=1)
WEBHOOK = "/publico/mp/webhook-suscripcion?type=payment&data.id={}"


@pytest.fixture()
def admin(db) -> dict:
    sa = SuperAdmin(nombre="Admin Test", email=f"sa-{uuid.uuid4().hex}@turnos360.test", hash_clave=hash_clave("clave1234"))
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


@pytest.fixture()
def mp_on(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "mp_saas_access_token", "TEST-de-prueba")
    monkeypatch.setattr(settings, "mp_saas_webhook_secret", "")
    return settings


def _empresa(armar_empresa, db, nombre="Barbería Caja"):
    ctx = armar_empresa(nombre)
    ctx.empresa.plan = "pro"
    ctx.empresa.suscripcion_vence = HOY + dt.timedelta(days=5)
    db.commit()
    return ctx


def _pago_manual(db, empresa, monto=10000.0, fecha=AYER):
    p = cobranza.registrar_pago(db, empresa, monto=monto, metodo="transferencia", fecha=fecha,
                                registrado_por="admin@test", actor_tipo="admin")
    db.commit()
    return p


def _pago_mp(db, empresa, pid="7001", monto=19990.0, comision=1000.0, fecha=AYER):
    p = cobranza.registrar_pago(db, empresa, monto=monto, metodo="mercadopago", fecha=fecha,
                                registrado_por="mercadopago", actor_tipo="mercadopago")
    p.mp_payment_id = pid
    p.comision = comision
    p.neto = monto - comision
    db.commit()
    return p


# ── Permisos ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("ruta", [
    "/admin/resumen", "/admin/cobros", "/admin/caja", "/admin/cierres", "/admin/estadisticas",
    "/admin/integraciones/mercadopago", "/admin/planes", "/admin/usuarios", "/admin/cobros/exportar",
])
def test_nada_financiero_sin_ser_super_admin(client, armar_empresa, ruta):
    ctx = armar_empresa()
    assert client.get(ruta).status_code == 401
    assert client.get(ruta, headers=token_de(ctx.dueno)).status_code in (401, 403)


# ── Cobros ────────────────────────────────────────────────────────────

def test_la_lista_une_pagos_transferencias_e_intentos_sin_duplicar(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    _pago_manual(db, ctx.empresa)
    db.add(AvisoPago(empresa_id=ctx.empresa.id, metodo="transferencia", monto=19990, estado="pendiente",
                     referencia="op-123", plan="pro", tipo="renovacion", monto_esperado=19990))
    intento_ok = IntentoPago(empresa_id=ctx.empresa.id, tipo="renovacion", plan="pro", monto=19990, estado="aprobado")
    db.add_all([intento_ok, IntentoPago(empresa_id=ctx.empresa.id, tipo="renovacion", plan="pro", monto=19990, estado="rechazado")])
    db.commit()
    r = client.get("/admin/cobros", params={"empresa_id": ctx.empresa.id}, headers=admin).json()
    estados = sorted(f["estado"] for f in r["filas"])
    assert estados == ["acreditado", "en_revision", "rechazado"]  # el intento aprobado no se repite
    assert r["sumas"]["acreditado"] == 10000 and r["sumas"]["en_revision"] == 19990
    # Lo en revisión no es plata cobrada.
    assert r["sumas"]["acreditado"] != 10000 + 19990


def test_filtros_y_separacion_entre_empresas(client, db, armar_empresa, admin):
    a = _empresa(armar_empresa, db, "Uno")
    b = _empresa(armar_empresa, db, "Dos")
    _pago_manual(db, a.empresa, 1000)
    _pago_mp(db, b.empresa, "7100", 2000, 100)
    solo_a = client.get("/admin/cobros", params={"empresa_id": a.empresa.id}, headers=admin).json()
    assert {f["empresa"] for f in solo_a["filas"]} == {"Uno"}
    mp = client.get("/admin/cobros", params={"metodo": "mercadopago", "buscar": "7100"}, headers=admin).json()
    assert [f["id_proveedor"] for f in mp["filas"]] == ["7100"]
    caro = client.get("/admin/cobros", params={"monto_min": 1500, "empresa_id": b.empresa.id}, headers=admin).json()
    assert len(caro["filas"]) == 1


def test_el_csv_neutraliza_formulas(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db, "=HYPERLINK(\"http://x\")")
    _pago_manual(db, ctx.empresa)
    r = client.get("/admin/cobros/exportar", params={"empresa_id": ctx.empresa.id}, headers=admin)
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    assert "'=HYPERLINK" in r.text
    assert db.scalar(select(func.count(AuditoriaAdmin.id)).where(AuditoriaAdmin.accion == "exportar")) >= 1


# ── Devoluciones ──────────────────────────────────────────────────────

def test_devolucion_parcial_y_despues_total_por_mercado_pago(client, db, armar_empresa, admin, mp_on, monkeypatch):
    ctx = _empresa(armar_empresa, db)
    pago = _pago_mp(db, ctx.empresa, "7200", 20000, 800)
    pedidos = []

    def falso(pid, monto, clave):
        pedidos.append((pid, monto))
        return {"id": 900 + len(pedidos), "status": "approved", "amount": monto}

    monkeypatch.setattr(mp_sus, "devolver", falso)
    r = client.post(f"/admin/pagos/{pago.id}/devolver", json={"monto": 5000, "motivo": "Cobro de más"}, headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["estado"] == "reembolso_parcial" and d["devuelto"] == 5000 and d["devolvible"] == 15000
    assert d["anulado"] is False and pedidos == [("7200", 5000.0)]

    # No se puede devolver más de lo que queda.
    r = client.post(f"/admin/pagos/{pago.id}/devolver", json={"monto": 15001, "motivo": "De más"}, headers=admin)
    assert r.status_code == 409

    r = client.post(f"/admin/pagos/{pago.id}/devolver", json={"monto": 15000, "motivo": "Baja del servicio"}, headers=admin)
    d = r.json()
    assert d["estado"] == "reembolso_total" and d["anulado"] is True
    assert db.scalar(select(func.count(AuditoriaAdmin.id)).where(AuditoriaAdmin.accion == "devolucion")) == 2


def test_devolucion_en_proceso_no_resta_hasta_que_se_aprueba(client, db, armar_empresa, admin, mp_on, monkeypatch):
    ctx = _empresa(armar_empresa, db)
    pago = _pago_mp(db, ctx.empresa, "7300", 10000, 0)
    monkeypatch.setattr(mp_sus, "devolver", lambda pid, m, c: {"id": 555, "status": "in_process"})
    d = client.post(f"/admin/pagos/{pago.id}/devolver", json={"monto": 10000, "motivo": "Pedido del cliente"}, headers=admin).json()
    assert d["estado"] == "reembolso_solicitado" and d["devuelto"] == 0
    caja = client.get("/admin/caja", params={"desde": AYER.isoformat(), "hasta": HOY.isoformat()}, headers=admin).json()
    assert caja["totales"]["devoluciones"] == 0

    monkeypatch.setattr(mp_sus, "consultar_devolucion", lambda pid, rid: {"id": rid, "status": "approved"})
    dev_id = d["devoluciones"][0]["id"]
    d = client.post(f"/admin/devoluciones/{dev_id}/refrescar", headers=admin).json()
    assert d["estado"] == "reembolso_total"
    caja = client.get("/admin/caja", params={"desde": AYER.isoformat(), "hasta": HOY.isoformat()}, headers=admin).json()
    # El pago cuenta como ingreso y la devolución resta UNA vez.
    assert caja["totales"]["cobros"] == 10000 and caja["totales"]["devoluciones"] == 10000
    assert caja["totales"]["neto"] == 0


def test_error_del_proveedor_no_toca_el_pago(client, db, armar_empresa, admin, mp_on, monkeypatch):
    ctx = _empresa(armar_empresa, db)
    pago = _pago_mp(db, ctx.empresa, "7400", 10000, 0)

    def falla(*a):
        raise mp_sus.ErrorMP("Mercado Pago rechazó la operación (400): insufficient_amount.")

    monkeypatch.setattr(mp_sus, "devolver", falla)
    r = client.post(f"/admin/pagos/{pago.id}/devolver", json={"monto": 1000, "motivo": "Prueba de error"}, headers=admin)
    assert r.status_code == 502 and "insufficient_amount" in r.json()["detail"]
    d = client.get(f"/admin/pagos/{pago.id}", headers=admin).json()
    assert d["estado"] == "acreditado" and d["devuelto"] == 0
    assert d["devoluciones"][0]["estado"] == "rechazada" and d["devoluciones"][0]["error"]


def test_la_misma_devolucion_dos_veces_es_una(client, db, armar_empresa, admin, mp_on, monkeypatch):
    ctx = _empresa(armar_empresa, db)
    pago = _pago_mp(db, ctx.empresa, "7500", 10000, 0)
    llamadas = []
    monkeypatch.setattr(mp_sus, "devolver", lambda pid, m, c: llamadas.append(c) or {"id": 1, "status": "approved"})
    cuerpo = {"monto": 1000, "motivo": "Doble clic", "clave": "clave-unica-1"}
    client.post(f"/admin/pagos/{pago.id}/devolver", json=cuerpo, headers=admin)
    client.post(f"/admin/pagos/{pago.id}/devolver", json=cuerpo, headers=admin)
    assert len(llamadas) == 1
    assert db.scalar(select(func.count(DevolucionSuscripcion.id)).where(DevolucionSuscripcion.pago_id == pago.id)) == 1


def test_devolucion_manual_de_transferencia(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    pago = _pago_manual(db, ctx.empresa, 10000)
    r = client.post(f"/admin/pagos/{pago.id}/devolver", json={"monto": 4000, "motivo": "Pagó dos veces", "confirmada": True}, headers=admin)
    assert r.status_code == 400  # sin referencia no se da por hecha
    d = client.post(f"/admin/pagos/{pago.id}/devolver", json={"monto": 4000, "motivo": "Pagó dos veces"}, headers=admin).json()
    assert d["estado"] == "reembolso_solicitado"
    dev_id = d["devoluciones"][-1]["id"]
    d = client.post(f"/admin/devoluciones/{dev_id}/confirmar", json={"referencia": "TRF-778"}, headers=admin).json()
    assert d["estado"] == "reembolso_parcial" and d["devuelto"] == 4000


def test_webhook_sincroniza_devoluciones_hechas_en_mp(client, db, armar_empresa, mp_on, monkeypatch):
    ctx = _empresa(armar_empresa, db)
    pago = _pago_mp(db, ctx.empresa, "7600", 10000, 0)
    datos = {"id": 7600, "status": "approved", "refunds": [{"id": 31, "amount": 2500, "status": "approved"}]}
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda pid: datos)
    client.post(WEBHOOK.format("7600"), json={"action": "payment.updated"})
    db.expire_all()
    dev = db.scalar(select(DevolucionSuscripcion).where(DevolucionSuscripcion.mp_refund_id == "31"))
    assert dev is not None and dev.origen == "mercadopago" and dev.estado == "aprobada"
    assert db.get(PagoSuscripcion, pago.id).anulado is False  # parcial: el pago sigue

    datos["status"] = "refunded"
    datos["refunds"].append({"id": 32, "amount": 7500, "status": "approved"})
    client.post(WEBHOOK.format("7600"), json={"action": "payment.updated"})
    db.expire_all()
    assert db.get(PagoSuscripcion, pago.id).anulado is True
    caja = fin.caja(db, AYER, HOY)
    assert caja["totales"]["cobros"] == 10000 and caja["totales"]["devoluciones"] == 10000


# ── Webhook: eventos, comisión, idempotencia, orden ───────────────────

def test_webhook_registra_eventos_comision_y_no_duplica(client, db, armar_empresa, mp_on, monkeypatch):
    ctx = _empresa(armar_empresa, db)
    intento = IntentoPago(empresa_id=ctx.empresa.id, tipo="renovacion", plan="pro", monto=19990, metodo="mercadopago")
    db.add(intento)
    db.commit()
    ref = mp_sus.referencia_de(ctx.empresa.id, "pro", intento.id)
    estado = {"s": "pending"}

    def consultar(pid):
        return {"id": int(pid), "status": estado["s"], "transaction_amount": 19990, "currency_id": "ARS",
                "external_reference": ref, "fee_details": [{"amount": 999.5}],
                "transaction_details": {"net_received_amount": 18990.5}}

    monkeypatch.setattr(mp_sus, "consultar_pago", consultar)
    client.post(WEBHOOK.format("7700"))           # primero llega «pendiente»
    db.expire_all()
    assert db.get(IntentoPago, intento.id).estado == "pendiente"
    estado["s"] = "approved"
    for _ in range(3):                              # después el aprobado, repetido
        assert client.post(WEBHOOK.format("7700")).status_code == 200
    db.expire_all()
    pagos = list(db.scalars(select(PagoSuscripcion).where(PagoSuscripcion.mp_payment_id == "7700")))
    assert len(pagos) == 1 and float(pagos[0].comision) == 999.5 and float(pagos[0].neto) == 18990.5
    assert db.scalar(select(func.count(EventoMP.id)).where(EventoMP.recurso_id == "7700")) == 4
    est = fin.estado_mp(db)
    assert est["configurado"] and est["entorno"] == "pruebas" and est["ultimo_procesado"] is not None


def test_estado_mp_sin_configurar_dice_que_falta(db):
    est = fin.estado_mp(db)
    if not est["configurado"]:
        assert any("MP_SAAS_ACCESS_TOKEN" in f for f in est["falta_comprobar"])
        assert est["comprobado"] is False


# ── Anulaciones ───────────────────────────────────────────────────────

def test_anular_un_pago_mal_cargado_conserva_el_registro(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    vence_antes = ctx.empresa.suscripcion_vence
    pago = _pago_manual(db, ctx.empresa, 10000, HOY)
    assert client.post(f"/admin/pagos/{pago.id}/anular", json={"motivo": "x"}, headers=admin).status_code == 422
    d = client.post(f"/admin/pagos/{pago.id}/anular", json={"motivo": "Se cargó en la empresa equivocada"}, headers=admin).json()
    assert d["estado"] == "anulado" and d["anulado_motivo"].startswith("Se cargó")
    db.expire_all()
    assert db.get(PagoSuscripcion, pago.id) is not None
    db.refresh(ctx.empresa)
    assert ctx.empresa.suscripcion_vence == vence_antes
    assert fin.caja(db, HOY, HOY)["totales"]["cobros"] == 0


def test_un_pago_de_mercado_pago_no_se_anula_se_devuelve(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    pago = _pago_mp(db, ctx.empresa, "7800")
    r = client.post(f"/admin/pagos/{pago.id}/anular", json={"motivo": "Intento de anular"}, headers=admin)
    assert r.status_code == 409


def test_anular_un_cobro_pendiente(client, db, armar_empresa, admin, mp_on, monkeypatch):
    ctx = _empresa(armar_empresa, db)
    iniciado = IntentoPago(empresa_id=ctx.empresa.id, tipo="renovacion", plan="pro", monto=100, estado="iniciado")
    pendiente = IntentoPago(empresa_id=ctx.empresa.id, tipo="renovacion", plan="pro", monto=100, estado="pendiente", mp_payment_id="7900")
    aprobado = IntentoPago(empresa_id=ctx.empresa.id, tipo="renovacion", plan="pro", monto=100, estado="aprobado")
    db.add_all([iniciado, pendiente, aprobado])
    db.commit()
    monkeypatch.setattr(mp_sus, "cancelar_pago", lambda pid: {"id": pid, "status": "cancelled"})
    assert client.post(f"/admin/intentos/{iniciado.id}/anular", json={"motivo": "Lo pidió el cliente"}, headers=admin).json()["estado"] == "cancelado"
    assert client.post(f"/admin/intentos/{pendiente.id}/anular", json={"motivo": "Lo pidió el cliente"}, headers=admin).json()["estado"] == "cancelado"
    assert client.post(f"/admin/intentos/{aprobado.id}/anular", json={"motivo": "Lo pidió el cliente"}, headers=admin).status_code == 409


# ── Caja, conciliación y cierres ──────────────────────────────────────

def test_caja_separa_registrado_de_conciliado(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    _pago_manual(db, ctx.empresa, 10000, AYER - dt.timedelta(days=3))  # antes del período
    t = _pago_manual(db, ctx.empresa, 10000, AYER)
    _pago_mp(db, ctx.empresa, "8000", 19990, 1000, AYER)
    client.post(f"/admin/pagos/{t.id}/conciliar", json={"conciliado": True, "referencia": "BCO-1"}, headers=admin)
    c = client.get("/admin/caja", params={"desde": AYER.isoformat(), "hasta": AYER.isoformat()}, headers=admin).json()
    tot = c["totales"]
    assert tot["cobros"] == 29990 and tot["comisiones"] == 1000 and tot["neto"] == 28990
    assert tot["transferencias_verificadas"] == 10000 and tot["mercadopago"] == 19990
    assert tot["conciliado"] == 10000 and tot["sin_conciliar"] == {"cantidad": 1, "monto": 19990}
    assert c["saldo_inicial"] >= 10000 and c["saldo_final"] == c["saldo_inicial"] + 28990
    assert c["es_calculado"] is True


def test_cierre_preparar_confirmar_reabrir_sin_duplicados(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    _pago_manual(db, ctx.empresa, 10000, AYER)
    periodo = {"desde": (AYER - dt.timedelta(days=6)).isoformat(), "hasta": AYER.isoformat()}
    r = client.post("/admin/cierres", json={**periodo, "observaciones": "Semana"}, headers=admin)
    assert r.status_code == 200, r.text
    cierre = r.json()
    assert cierre["estado"] == "borrador" and cierre["totales"]["cobros"] >= 10000
    assert client.post("/admin/cierres", json=periodo, headers=admin).status_code == 409
    assert client.post("/admin/cierres", json={"desde": HOY.isoformat(), "hasta": HOY.isoformat()}, headers=admin).status_code == 400

    c = client.post(f"/admin/cierres/{cierre['id']}/confirmar", json={}, headers=admin).json()
    assert c["estado"] == "cerrado" and c["cerrado_por"]
    # Un pago cargado después en ese período: el cierre no cambia, la caja
    # muestra la diferencia.
    _pago_manual(db, ctx.empresa, 500, AYER)
    caja = client.get("/admin/caja", params=periodo, headers=admin).json()
    assert caja["diferencias_con_cierre"]["cobros"] == 500
    assert client.post(f"/admin/cierres/{cierre['id']}/reabrir", json={"motivo": "no"}, headers=admin).status_code == 422
    c = client.post(f"/admin/cierres/{cierre['id']}/reabrir", json={"motivo": "Faltaba un pago"}, headers=admin).json()
    assert c["estado"] == "reabierto" and c["motivo_reapertura"] == "Faltaba un pago"
    acciones = set(db.scalars(select(AuditoriaAdmin.accion).where(AuditoriaAdmin.accion.like("cierre_%"))))
    assert {"cierre_preparado", "cierre_confirmado", "cierre_reabierto"} <= acciones


# ── Estadísticas ──────────────────────────────────────────────────────

def test_estadisticas_por_mes_y_comparacion(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    _pago_manual(db, ctx.empresa, 10000, AYER)
    r = client.get("/admin/estadisticas", params={"granularidad": "semana", "desde": (AYER - dt.timedelta(days=13)).isoformat(),
                                                  "hasta": AYER.isoformat()}, headers=admin)
    assert r.status_code == 200
    d = r.json()
    assert d["total"]["bruto"] >= 10000 and d["serie"] and "bruto" in d["definiciones"]
    assert client.get("/admin/estadisticas", params={"granularidad": "año"}, headers=admin).status_code == 400
    csv = client.get("/admin/estadisticas/exportar", params={"granularidad": "mes"}, headers=admin)
    assert csv.status_code == 200 and "Bruto" in csv.text


def test_resumen_general(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    _pago_manual(db, ctx.empresa, 10000, HOY)
    d = client.get("/admin/resumen", headers=admin).json()
    assert d["empresas"]["total"] >= 1 and d["periodo"]["acreditado"] >= 10000
    assert "serie_semanal" in d and isinstance(d["alertas"], list)


# ── Usuarios y accesos ────────────────────────────────────────────────

def test_restablecer_clave_no_devuelve_el_link_y_queda_auditado(client, db, armar_empresa, admin, monkeypatch):
    from app.core import cola
    from app.tasks import emails

    enviados = []
    monkeypatch.setattr(cola, "encolar", lambda tarea, *a, **k: enviados.append((tarea.name, a)) or cola.Resultado.ENCOLADA)
    ctx = _empresa(armar_empresa, db)
    version = ctx.profesional.token_version or 0
    r = client.post(f"/admin/usuarios/{ctx.profesional.id}/restablecer", json={"cerrar_sesiones": True}, headers=admin)
    assert r.status_code == 200, r.text
    assert "restablecer" not in r.text and "token" not in r.text.lower()
    db.expire_all()
    u = db.get(Usuario, ctx.profesional.id)
    assert u.reset_token_hash and u.token_version == version + 1
    assert enviados and enviados[0][0] == emails.enviar_reset_password.name and enviados[0][1][2] is True
    assert db.scalar(select(AuditoriaAdmin).where(AuditoriaAdmin.accion == "restablecer_clave")) is not None


def test_no_se_restablece_un_usuario_desactivado(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    ctx.profesional.activo = False
    db.commit()
    assert client.post(f"/admin/usuarios/{ctx.profesional.id}/restablecer", json={}, headers=admin).status_code == 409


def test_desactivar_un_acceso_corta_sesiones_y_se_audita(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    h = token_de(ctx.profesional)
    assert client.get("/auth/me", headers=h).status_code == 200
    r = client.post(f"/admin/usuarios/{ctx.profesional.id}/acceso", json={"activo": False, "motivo": "Dejó de trabajar"}, headers=admin)
    assert r.json()["activo"] is False
    assert client.get("/auth/me", headers=h).status_code == 401
    lista = client.get("/admin/usuarios", params={"empresa_id": ctx.empresa.id}, headers=admin).json()
    assert {f["email"] for f in lista["filas"]} == {ctx.dueno.email, ctx.profesional.email}
    assert db.scalar(select(AuditoriaAdmin).where(AuditoriaAdmin.accion == "acceso_usuario")) is not None


def test_la_auditoria_se_filtra(client, db, armar_empresa, admin):
    ctx = _empresa(armar_empresa, db)
    pago = _pago_manual(db, ctx.empresa)
    client.post(f"/admin/pagos/{pago.id}/conciliar", json={"conciliado": True}, headers=admin)
    filas = client.get("/admin/auditoria", params={"accion": "conciliar", "desde": HOY.isoformat()}, headers=admin).json()
    assert filas and all(f["accion"] == "conciliar" for f in filas)


def test_planes_tiene_el_catalogo_y_los_conteos(client, admin):
    d = client.get("/admin/planes", headers=admin).json()
    codigos = {p["codigo"] for p in d}
    assert {"pro", "multi"} <= codigos
    assert all("empresas" in p and "precio" in p for p in d)
