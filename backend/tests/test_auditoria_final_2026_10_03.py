"""Auditoría final pre-producción (2026-10-03).

Escenarios que la auditoría encontró abiertos o sin prueba:

- Pagar un plan más chico que lo que se usa (bypass de la baja).
- Débito automático que devolvía la empresa a su plan viejo.
- Devoluciones de MP que llegan sin «action» (IPN por query string).
- Webhooks fuera de orden.
- Comprobantes de otra empresa, archivos que no son imagen.
- Atomicidad de «aprobar pago».
"""

import datetime as dt
import io
import uuid

import pytest
from PIL import Image

from app.core import planes
from app.core.config import settings
from app.core.crypto import hash_clave
from app.core.reloj import hoy_de_pared
from app.core.seguridad import crear_token_superadmin
from app.models import (
    AjusteSuscripcion,
    AuditoriaAdmin,
    AvisoPago,
    DebitoAutomatico,
    Empresa,
    IntentoPago,
    PagoSuscripcion,
    Sucursal,
    SuperAdmin,
    Usuario,
)
from app.models.enums import RolUsuario
from app.services import cobranza, mp_debito
from app.services import mp_suscripcion as mp_sus

from .conftest import token_de

HOY = hoy_de_pared()
WEBHOOK = "/publico/mp/webhook-suscripcion?type=payment&data.id={}"


@pytest.fixture()
def admin(db) -> dict:
    sa = SuperAdmin(nombre="Admin", email=f"sa-{uuid.uuid4().hex}@turnos360.test",
                    hash_clave=hash_clave("clave1234"))
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


@pytest.fixture()
def mp_prendido(monkeypatch):
    monkeypatch.setattr(settings, "mp_saas_access_token", "APP_USR-de-prueba")
    monkeypatch.setattr(settings, "mp_saas_webhook_secret", "")


def _empresa(armar_empresa, db, plan="pro", vence=HOY + dt.timedelta(days=10)):
    ctx = armar_empresa()
    ctx.empresa.plan = plan
    ctx.empresa.suscripcion_vence = vence
    db.commit()
    return ctx


def _sucursales(db, empresa, n):
    for i in range(n):
        db.add(Sucursal(empresa_id=empresa.id, nombre=f"Sede {i}", activa=True))
    db.commit()


def _pago(pid, ref, monto, estado="approved"):
    return {"id": int(pid), "status": estado, "transaction_amount": monto,
            "currency_id": "ARS", "external_reference": ref}


# ══════════════════════════════════════════════════════════════════════
#  H/G. Bajar de plan pagando directo: no se puede saltear la regla
# ══════════════════════════════════════════════════════════════════════

def test_H_avisar_pago_de_un_plan_mas_chico_con_sucursales_de_mas_da_409(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db, plan="multi")
    _sucursales(db, ctx.empresa, 2)  # 3 en total
    r = client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno),
                    json={"monto": 13900, "plan": "inicial"})
    assert r.status_code == 409
    assert "3 sucursales" in r.json()["detail"]
    assert db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).count() == 0


def test_H_pagar_por_mp_un_plan_mas_chico_con_sucursales_de_mas_da_409(client, db, armar_empresa, mp_prendido):
    ctx = _empresa(armar_empresa, db, plan="multi")
    _sucursales(db, ctx.empresa, 2)
    r = client.post("/empresa/suscripcion/pagar-mp?plan=inicial", headers=token_de(ctx.dueno))
    assert r.status_code == 409
    assert db.query(IntentoPago).filter_by(empresa_id=ctx.empresa.id).count() == 0


def test_H_si_igual_entra_la_plata_no_aplica_el_plan_imposible(db, armar_empresa):
    """Carrera: el pago ya entró. Se registra y renueva, pero no baja de plan."""
    ctx = _empresa(armar_empresa, db, plan="multi")
    _sucursales(db, ctx.empresa, 2)
    cobranza.registrar_pago(db, ctx.empresa, monto=13900, metodo="mercadopago", plan="inicial")
    db.commit()
    assert ctx.empresa.plan == "multi"
    assert cobranza.incompatibilidades(db, ctx.empresa, ctx.empresa.plan) == []
    assert db.query(AjusteSuscripcion).filter_by(
        empresa_id=ctx.empresa.id, tipo="baja_postergada").count() == 1


def test_G_bajar_con_usuarios_de_mas_queda_programada_y_no_se_aplica(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db, plan="pro")
    for i in range(3):  # dueño + profesional + 3 = 5 > 4 de Inicial
        db.add(Usuario(empresa_id=ctx.empresa.id, sucursal_id=ctx.dueno.sucursal_id,
                       nombre=f"Extra {i}", email=f"x{i}-{uuid.uuid4().hex[:6]}@example.com",
                       hash_clave=hash_clave("clave1234"), rol=RolUsuario.RECEPCION))
    db.commit()
    prev = client.get("/empresa/suscripcion/cambio-plan?plan=inicial", headers=token_de(ctx.dueno)).json()
    assert any(i["recurso"] == "usuarios" for i in prev["incompatibilidades"])
    r = client.post("/empresa/suscripcion/cambiar-plan", headers=token_de(ctx.dueno),
                    json={"plan": "inicial", "confirmo": True})
    assert r.json()["accion"] == "programada"
    ctx.empresa.suscripcion_vence = HOY
    db.commit()
    assert cobranza.aplicar_bajas_programadas(db, hoy=HOY) == 0
    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "pro"


# ══════════════════════════════════════════════════════════════════════
#  D/L. Webhooks fuera de orden y devoluciones
# ══════════════════════════════════════════════════════════════════════

def test_D_aviso_de_aprobado_que_llega_cuando_mp_ya_lo_devolvio_no_acredita(client, db, armar_empresa, monkeypatch, mp_prendido):
    """Se consulta SIEMPRE el estado actual en MP: el orden de llegada no importa."""
    ctx = _empresa(armar_empresa, db)
    ref = mp_sus.referencia_de(ctx.empresa.id, "pro")
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda pid: _pago(pid, ref, 19990, "refunded"))
    client.post(WEBHOOK.format("8100001"), json={"action": "payment.created"})
    assert db.query(PagoSuscripcion).filter_by(mp_payment_id="8100001").count() == 0


def test_D_pendiente_despues_aprobado_despues_reintento_acredita_una_vez(client, db, armar_empresa, monkeypatch, mp_prendido):
    ctx = _empresa(armar_empresa, db)
    ref = mp_sus.referencia_de(ctx.empresa.id, "pro")
    estado = {"s": "pending"}
    llamadas = []

    def consultar(pid):
        llamadas.append(pid)
        return _pago(pid, ref, 19990, estado["s"])

    monkeypatch.setattr(mp_sus, "consultar_pago", consultar)
    client.post(WEBHOOK.format("8100002"), json={"action": "payment.created"})
    estado["s"] = "approved"
    client.post(WEBHOOK.format("8100002"), json={"action": "payment.updated"})
    n = len(llamadas)
    client.post(WEBHOOK.format("8100002"), json={"action": "payment.created"})  # reintento
    assert len(llamadas) == n, "un reintento de payment.created no sale a la red"
    db.expire_all()
    assert db.query(PagoSuscripcion).filter_by(mp_payment_id="8100002").count() == 1
    assert db.get(Empresa, ctx.empresa.id).suscripcion_vence == HOY + dt.timedelta(days=40)


def test_L_devolucion_avisada_sin_action_tambien_anula(client, db, armar_empresa, monkeypatch, mp_prendido, admin):
    ctx = _empresa(armar_empresa, db)
    ref = mp_sus.referencia_de(ctx.empresa.id, "pro")
    estado = {"s": "approved"}
    monkeypatch.setattr(mp_sus, "consultar_pago", lambda pid: _pago(pid, ref, 19990, estado["s"]))
    client.post(WEBHOOK.format("8100003"))
    estado["s"] = "charged_back"
    client.post("/publico/mp/webhook-suscripcion?topic=payment&id=8100003")  # IPN, sin body
    db.expire_all()
    assert db.query(PagoSuscripcion).filter_by(mp_payment_id="8100003").one().anulado is True
    res = client.get("/admin/cobranza/resumen", headers=admin).json()
    assert res["pagos_devueltos"] >= 1
    assert any("devuelto" in a["texto"] for a in res["alertas"])


# ══════════════════════════════════════════════════════════════════════
#  M. Cambio de plan con débito automático
# ══════════════════════════════════════════════════════════════════════

def _debito(db, empresa, plan):
    fila = DebitoAutomatico(empresa_id=empresa.id, preapproval_id=uuid.uuid4().hex,
                            estado=mp_debito.ACTIVO, plan=plan,
                            monto=planes.GRILLA[planes.plan_de(plan)].precio)
    db.add(fila)
    db.commit()
    return fila


def _cobro(fila, monto=None):
    return {"id": 1, "preapproval_id": fila.preapproval_id, "currency_id": "ARS",
            "transaction_amount": monto if monto is not None else float(fila.monto),
            "payment": {"id": int(uuid.uuid4().int % 10**9), "status": "approved"}}


def test_M_el_debito_desfasado_no_devuelve_la_empresa_a_su_plan_viejo(db, armar_empresa, monkeypatch, mp_prendido):
    ctx = _empresa(armar_empresa, db, plan="multi")  # ya pasó a Multi por otro medio
    fila = _debito(db, ctx.empresa, "pro")           # el débito quedó en Pro
    puts = []
    monkeypatch.setattr(mp_debito, "esta_activo", lambda: True)
    monkeypatch.setattr(mp_debito.httpx, "put", lambda *a, **k: puts.append(k) or type(
        "R", (), {"raise_for_status": lambda self: None})())
    monkeypatch.setattr(mp_debito, "consultar_cobro", lambda _id: _cobro(fila))
    mp_debito.acreditar_cobro(db, "999")
    db.refresh(ctx.empresa)
    assert ctx.empresa.plan == "multi"
    assert puts and puts[0]["json"]["auto_recurring"]["transaction_amount"] == 34990
    db.refresh(fila)
    assert fila.plan == "multi"


def test_M_aprobar_transferencia_de_cambio_de_plan_ajusta_el_debito(client, db, armar_empresa, admin, monkeypatch):
    ctx = _empresa(armar_empresa, db, plan="pro")
    fila = _debito(db, ctx.empresa, "pro")
    puts = []
    monkeypatch.setattr(mp_debito, "esta_activo", lambda: True)
    monkeypatch.setattr(mp_debito.httpx, "put", lambda *a, **k: puts.append(k) or type(
        "R", (), {"raise_for_status": lambda self: None})())
    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno),
                json={"monto": 34990, "plan": "multi"})
    aviso = db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).one()
    r = client.post(f"/admin/cobranza/avisos/{aviso.id}/aprobar", headers=admin, json={"confirmo": True})
    assert r.status_code == 200
    db.refresh(fila)
    assert fila.plan == "multi" and float(fila.monto) == 34990
    assert puts


# ══════════════════════════════════════════════════════════════════════
#  Atomicidad: aprobar pago = pago + suscripción + aviso + auditoría, o nada
# ══════════════════════════════════════════════════════════════════════

def test_aprobar_pago_es_atomico(client, db, armar_empresa, admin, monkeypatch):
    ctx = _empresa(armar_empresa, db, vence=HOY)
    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno), json={"monto": 19990})
    aviso = db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).one()

    def explota(*a, **k):
        raise RuntimeError("falla a mitad de camino")

    monkeypatch.setattr(cobranza, "registrar_ajuste", explota)
    c2 = client.__class__(client.app, raise_server_exceptions=False)
    r = c2.post(f"/admin/cobranza/avisos/{aviso.id}/aprobar", headers=admin, json={"confirmo": True})
    assert r.status_code == 500
    db.rollback()
    db.expire_all()
    assert db.query(PagoSuscripcion).filter_by(empresa_id=ctx.empresa.id).count() == 0
    assert db.get(AvisoPago, aviso.id).estado == "pendiente"
    assert db.get(Empresa, ctx.empresa.id).suscripcion_vence == HOY
    assert db.query(AuditoriaAdmin).filter_by(empresa_id=ctx.empresa.id).count() == 0
    assert "falla a mitad" not in r.text  # sin detalles internos al cliente


# ══════════════════════════════════════════════════════════════════════
#  F. Comprobantes: privados y por empresa
# ══════════════════════════════════════════════════════════════════════

def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_F_el_comprobante_de_otra_empresa_no_se_puede_usar(client, db, armar_empresa, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    a = _empresa(armar_empresa, db)
    b = _empresa(armar_empresa, db)
    r = client.post("/subidas/comprobante", headers=token_de(a.dueno),
                    files={"archivo": ("c.png", _png(), "image/png")})
    assert r.status_code == 200
    ident = r.json()["id"]
    r = client.post("/empresa/suscripcion/aviso-pago", headers=token_de(b.dueno),
                    json={"comprobante": ident})
    assert r.status_code == 400
    # El archivo vive bajo la carpeta privada de A, no en la pública.
    assert (tmp_path / "_privado" / "comprobantes" / str(a.empresa.id) / ident).is_file()


def test_F_un_archivo_que_no_es_imagen_se_rechaza(client, db, armar_empresa, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    a = _empresa(armar_empresa, db)
    r = client.post("/subidas/comprobante", headers=token_de(a.dueno),
                    files={"archivo": ("c.png", b"%PDF-1.4 no soy imagen", "image/png")})
    assert r.status_code in (400, 415, 422)


def test_F_ver_un_comprobante_queda_auditado(client, db, armar_empresa, admin, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    a = _empresa(armar_empresa, db)
    ident = client.post("/subidas/comprobante", headers=token_de(a.dueno),
                        files={"archivo": ("c.png", _png(), "image/png")}).json()["id"]
    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(a.dueno),
                json={"monto": 19990, "comprobante": ident})
    aviso = db.query(AvisoPago).filter_by(empresa_id=a.empresa.id).one()
    r = client.get(f"/admin/cobranza/avisos/{aviso.id}/comprobante", headers=admin)
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    assert "no-store" in r.headers["cache-control"]
    assert db.query(AuditoriaAdmin).filter_by(empresa_id=a.empresa.id, accion="ver_comprobante").count() == 1
    # El dueño (ni de esa ni de otra empresa) no entra por la ruta del admin.
    assert client.get(f"/admin/cobranza/avisos/{aviso.id}/comprobante",
                      headers=token_de(a.dueno)).status_code in (401, 403)


# ══════════════════════════════════════════════════════════════════════
#  Acceso sin pagar: un aviso falso no reabre la web para siempre
# ══════════════════════════════════════════════════════════════════════

def test_un_aviso_en_revision_sostiene_la_web_solo_unos_dias(client, db, armar_empresa):
    from app.services.suscripcion import DIAS_REVISION, estado_suscripcion

    ctx = _empresa(armar_empresa, db, vence=HOY - dt.timedelta(days=20))
    assert estado_suscripcion(ctx.empresa, db)["reservas_abiertas"] is False
    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno), json={"monto": 1})
    assert estado_suscripcion(ctx.empresa, db)["reservas_abiertas"] is True
    aviso = db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).one()
    aviso.creado_en = aviso.creado_en - dt.timedelta(days=DIAS_REVISION + 1)
    db.commit()
    e = estado_suscripcion(ctx.empresa, db)
    assert e["estado"] == "en_revision" and e["reservas_abiertas"] is False


def test_despues_de_un_rechazo_un_aviso_nuevo_no_reabre_la_web(client, db, armar_empresa, admin):
    from app.services.suscripcion import estado_suscripcion

    ctx = _empresa(armar_empresa, db, vence=HOY - dt.timedelta(days=20))
    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno), json={"monto": 1})
    aviso = db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).one()
    client.post(f"/admin/cobranza/avisos/{aviso.id}/descartar", headers=admin, json={"motivo": "No apareció"})
    client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno), json={"monto": 1})
    db.expire_all()
    assert estado_suscripcion(db.get(Empresa, ctx.empresa.id), db)["reservas_abiertas"] is False


def test_I_cancelar_con_debito_que_mp_no_corta_no_cancela_nada(client, db, armar_empresa, monkeypatch):
    """Una suscripción «cancelada» que MP sigue cobrando es el peor error posible."""
    ctx = _empresa(armar_empresa, db)
    _debito(db, ctx.empresa, "pro")
    monkeypatch.setattr(mp_debito, "cancelar", lambda *a, **k: False)
    r = client.post("/empresa/suscripcion/cancelar", headers=token_de(ctx.dueno), json={"confirmo": True})
    assert r.status_code == 502
    db.refresh(ctx.empresa)
    assert ctx.empresa.cancela_al_vencer is False


def test_I_cancelar_con_debito_lo_corta_primero(client, db, armar_empresa, monkeypatch):
    ctx = _empresa(armar_empresa, db)
    _debito(db, ctx.empresa, "pro")
    cortados = []
    monkeypatch.setattr(mp_debito, "cancelar", lambda db_, eid, quien: cortados.append(eid) or True)
    r = client.post("/empresa/suscripcion/cancelar", headers=token_de(ctx.dueno), json={"confirmo": True})
    assert r.status_code == 200 and cortados == [ctx.empresa.id]


def test_la_base_no_admite_dos_avisos_abiertos_de_la_misma_empresa(db, armar_empresa):
    from sqlalchemy.exc import IntegrityError

    ctx = _empresa(armar_empresa, db)
    db.add(AvisoPago(empresa_id=ctx.empresa.id, metodo="transferencia", estado="pendiente"))
    db.flush()
    db.add(AvisoPago(empresa_id=ctx.empresa.id, metodo="transferencia", estado="info_solicitada"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_avisar_dos_veces_actualiza_el_mismo_aviso(client, db, armar_empresa):
    ctx = _empresa(armar_empresa, db)
    for ref in ("op 1", "op 2"):
        assert client.post("/empresa/suscripcion/aviso-pago", headers=token_de(ctx.dueno),
                           json={"monto": 19990, "referencia": ref}).status_code == 200
    avisos = db.query(AvisoPago).filter_by(empresa_id=ctx.empresa.id).all()
    assert len(avisos) == 1 and avisos[0].referencia == "op 2"
