"""Regresión del fix-028: el panel de admin tiene que dejar rastro y poder volver atrás.

EL CASO QUE LO ORIGINÓ, tal cual lo contó Leandro:
    "Sin querer siento que el botón renovar treinta días, como no me salió
    ningún cartel de que lo confirma, se hizo automáticamente, y yo por ahí
    cometí un error de clic y le regalé los treinta ya, porque encima no puedo
    ver eso para atrás."

Dos agujeros distintos: no había confirmación (eso se arregló en el frontend) y
no había NINGÚN registro de que la fecha se hubiera movido. Sin el registro no
se puede revertir, porque nadie sabe cuál era la fecha anterior.
"""

import datetime as dt
import uuid

import pytest

from app.core.crypto import hash_clave
from app.core.seguridad import crear_token_superadmin
from app.models import Empresa, PagoSuscripcion, SuperAdmin


@pytest.fixture()
def admin(db) -> dict:
    """Un super-admin real en la base + su token."""
    sa = SuperAdmin(
        nombre="Admin Test",
        email=f"sa-{uuid.uuid4().hex}@turnos360.test",
        hash_clave=hash_clave("clave1234"),
    )
    db.add(sa)
    db.flush()
    return {"Authorization": f"Bearer {crear_token_superadmin(sa.id)}"}


def _ajustes(client, empresa_id, admin):
    r = client.get(f"/admin/empresas/{empresa_id}/ajustes", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


# ══════════════════════════════════════════════════════════════════════
#  Queda rastro
# ══════════════════════════════════════════════════════════════════════

def test_renovar_30_dias_queda_registrado(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    vencia = dt.date.today() + dt.timedelta(days=3)
    ctx.empresa.suscripcion_vence = vencia
    db.commit()

    r = client.patch(
        f"/admin/empresas/{ctx.empresa.id}/suscripcion",
        headers=admin,
        json={"renovar_30": True},
    )
    assert r.status_code == 200, r.text

    movs = _ajustes(client, ctx.empresa.id, admin)
    assert len(movs) == 1, "Regalar un mes no dejaba ningún rastro. Ese era el bug."
    assert movs[0]["tipo"] == "renovacion"
    assert movs[0]["vence_antes"] == str(vencia), (
        "Sin la fecha anterior guardada, revertir es adivinar."
    )
    assert movs[0]["hecho_por"], "Hay que saber quién lo hizo."


def test_la_prorroga_queda_registrada_con_los_dias(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    ctx.empresa.suscripcion_vence = dt.date.today() + dt.timedelta(days=5)
    db.commit()

    client.post(
        f"/admin/empresas/{ctx.empresa.id}/prorroga",
        headers=admin,
        json={"dias": 10},
    )
    movs = _ajustes(client, ctx.empresa.id, admin)
    assert movs[0]["tipo"] == "prorroga"
    assert movs[0]["dias"] == 10


def test_registrar_un_pago_queda_registrado(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 14990, "metodo": "transferencia", "renovar": True},
    )
    movs = _ajustes(client, ctx.empresa.id, admin)
    assert movs[0]["tipo"] == "pago"


# ══════════════════════════════════════════════════════════════════════
#  Se puede volver atrás
# ══════════════════════════════════════════════════════════════════════

def test_revertir_devuelve_el_vencimiento_a_como_estaba(client, db, armar_empresa, admin):
    """El arreglo del click equivocado."""
    ctx = armar_empresa()
    vencia = dt.date.today() + dt.timedelta(days=3)
    ctx.empresa.suscripcion_vence = vencia
    db.commit()

    client.patch(
        f"/admin/empresas/{ctx.empresa.id}/suscripcion",
        headers=admin,
        json={"renovar_30": True},
    )
    db.expire_all()
    assert db.get(Empresa, ctx.empresa.id).suscripcion_vence != vencia

    aj = _ajustes(client, ctx.empresa.id, admin)[0]
    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/ajustes/{aj['id']}/revertir",
        headers=admin,
    )
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(Empresa, ctx.empresa.id).suscripcion_vence == vencia


def test_revertir_deja_su_propio_rastro(client, db, armar_empresa, admin):
    """El historial cuenta que se dio y se sacó, no finge que nunca pasó."""
    ctx = armar_empresa()
    ctx.empresa.suscripcion_vence = dt.date.today()
    db.commit()
    client.post(
        f"/admin/empresas/{ctx.empresa.id}/prorroga",
        headers=admin,
        json={"dias": 10},
    )
    aj = _ajustes(client, ctx.empresa.id, admin)[0]
    client.post(
        f"/admin/empresas/{ctx.empresa.id}/ajustes/{aj['id']}/revertir",
        headers=admin,
    )

    movs = _ajustes(client, ctx.empresa.id, admin)
    assert movs[0]["tipo"] == "reversion"
    assert [m for m in movs if m["id"] == aj["id"]][0]["revertido"] is True


def test_revertir_un_pago_lo_anula(client, db, armar_empresa, admin):
    """Si no, queda una cuota cobrada que no cubre ningún período."""
    ctx = armar_empresa()
    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/pagos",
        headers=admin,
        json={"monto": 14990, "metodo": "transferencia", "renovar": True},
    )
    pago_id = r.json()["id"]

    aj = _ajustes(client, ctx.empresa.id, admin)[0]
    client.post(
        f"/admin/empresas/{ctx.empresa.id}/ajustes/{aj['id']}/revertir",
        headers=admin,
    )
    db.expire_all()
    assert db.get(PagoSuscripcion, pago_id).anulado is True


def test_no_se_revierte_dos_veces(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    ctx.empresa.suscripcion_vence = dt.date.today()
    db.commit()
    client.post(
        f"/admin/empresas/{ctx.empresa.id}/prorroga",
        headers=admin,
        json={"dias": 10},
    )
    aj = _ajustes(client, ctx.empresa.id, admin)[0]
    url = f"/admin/empresas/{ctx.empresa.id}/ajustes/{aj['id']}/revertir"
    assert client.post(url, headers=admin).status_code == 200
    assert client.post(url, headers=admin).status_code == 409


def test_no_se_revierte_una_reversion(client, db, armar_empresa, admin):
    ctx = armar_empresa()
    ctx.empresa.suscripcion_vence = dt.date.today()
    db.commit()
    client.post(
        f"/admin/empresas/{ctx.empresa.id}/prorroga",
        headers=admin,
        json={"dias": 10},
    )
    aj = _ajustes(client, ctx.empresa.id, admin)[0]
    client.post(
        f"/admin/empresas/{ctx.empresa.id}/ajustes/{aj['id']}/revertir",
        headers=admin,
    )
    rev = _ajustes(client, ctx.empresa.id, admin)[0]
    assert rev["tipo"] == "reversion"
    r = client.post(
        f"/admin/empresas/{ctx.empresa.id}/ajustes/{rev['id']}/revertir",
        headers=admin,
    )
    assert r.status_code == 409


# ══════════════════════════════════════════════════════════════════════
#  Sigue siendo del super-admin, y de nadie más
# ══════════════════════════════════════════════════════════════════════

def test_el_historial_pide_super_admin(client, armar_empresa, admin):
    ctx = armar_empresa()
    from .conftest import token_de

    r = client.get(f"/admin/empresas/{ctx.empresa.id}/ajustes")
    assert r.status_code == 401

    r = client.get(
        f"/admin/empresas/{ctx.empresa.id}/ajustes", headers=token_de(ctx.dueno)
    )
    assert r.status_code in (401, 403), (
        "El dueño de un negocio no puede ver los movimientos de cobranza."
    )


def test_no_se_revierte_un_ajuste_de_otra_empresa(client, db, armar_empresa, admin):
    a = armar_empresa()
    b = armar_empresa()
    a.empresa.suscripcion_vence = dt.date.today()
    db.commit()
    client.post(
        f"/admin/empresas/{a.empresa.id}/prorroga",
        headers=admin,
        json={"dias": 10},
    )
    aj = _ajustes(client, a.empresa.id, admin)[0]

    r = client.post(
        f"/admin/empresas/{b.empresa.id}/ajustes/{aj['id']}/revertir",
        headers=admin,
    )
    assert r.status_code == 404
